import json

import yaml
from controller import AppController, ControllerEventType
from termcolor import colored
import asyncio
import logging

import os

from data.filter import DataFilter
os.environ.setdefault('SKIPP_IMPORT_HOME_ASSISTANT', "True")
import sys
# caution: path[0] is reserved for script path (or '' in REPL)
# sys.path.insert(1, 'C:\\Users\\automation\\Documents\\home-assistant-eltako')
# from custom_components.eltako.const import *
from const import *

from homeassistant.const import CONF_ID, CONF_DEVICE, CONF_DEVICES, CONF_NAME, CONF_PLATFORM, CONF_TYPE, CONF_DEVICE_CLASS, CONF_TEMPERATURE_UNIT, UnitOfTemperature, Platform
from eltakobus.device import BusObject, FAM14, SensorInfo, KeyFunction
from eltakobus.message import *
from eltakobus.eep import *
from eltakobus.device import SensorInfo, KeyFunction
from eltakobus.util import b2s, AddressExpression

from data.data_helper import *
from data.device import Device 

class DataManager():
    """"""

    device_list:dict={}

    def __init__(self, controller:AppController):
        self.controller = controller
        self.controller.add_event_handler(ControllerEventType.SERIAL_CALLBACK, self._serial_callback_handler)
        self.controller.add_event_handler(ControllerEventType.ASYNC_DEVICE_DETECTED, self._async_device_detected_handler)
        self.controller.add_event_handler(ControllerEventType.LOAD_FILE, self._reset)

        self.eltako = {}
        for p in [CONF_UNKNOWN, Platform.BINARY_SENSOR, Platform.LIGHT, Platform.SENSOR, Platform.SWITCH, Platform.COVER, Platform.CLIMATE]:
            self.eltako[p] = []

        self.detected_sensors = {}
        self.sender_base_address = 0x0000B000
        self.export_logger = False
        self.fam14_device_amapping = {}
        self.fam14_base_id = '00-00-00-00'

        self.collected_sensor_list:[SensorInfo] = []
        self.devices:dict[str:Device] = {}
        self.data_fitlers:dict[str:DataFilter] = {}


    def add_filter(self, filter:DataFilter) -> None:
        self.data_fitlers[filter.name] = filter

    def remove_filter(self, filter:DataFilter) -> None:
        if filter.name in self.data_fitlers.keys():
            del self.data_fitlers[filter.name]

    def _reset(self, data):
        self.devices = {}

    def load_devices(self, devices:dict):
        for key in devices.keys():
            device:Device = devices[key]
            self.devices[key] = device
            if device.is_bus_device():
                self.controller.fire_event(ControllerEventType.UPDATE_DEVICE_REPRESENTATION, device)
            else:
                self.controller.fire_event(ControllerEventType.UPDATE_SENSOR_REPRESENTATION, device)

    def _serial_callback_handler(self, message:EltakoMessage):
        # self.add_sensor_from_wireless_telegram(message)
        if type(message) in [RPSMessage, Regular1BSMessage, Regular4BSMessage]:
            if int.from_bytes(message.address, "big") > 0X0000FFFF:
                a = b2s(message.address)
                if a not in self.devices:
                    decentralized_device = Device.get_decentralized_device_by_telegram(message)
                    self.devices[a] = decentralized_device
                    self.controller.fire_event(ControllerEventType.UPDATE_SENSOR_REPRESENTATION, decentralized_device)


    async def _async_device_detected_handler(self, data):
        for channel in range(1, data['device'].size+1):
            bd:Device = await Device.async_get_bus_device_by_natvice_bus_object(data['device'], data['fam14'], channel)
            
            update = data['force_overwrite']
            update |= bd.external_id not in self.devices
            update |= bd.external_id in self.devices and self.devices[bd.external_id].device_type is None 
            update |= bd.external_id in self.devices and self.devices[bd.external_id].device_type == ''
            update |= bd.external_id in self.devices and self.devices[bd.external_id].device_type == 'unknown'

            if update:
                self.devices[bd.external_id] = bd
                self.controller.fire_event(ControllerEventType.UPDATE_DEVICE_REPRESENTATION, bd)

                for si in bd.memory_entries:
                    _bd:Device = await Device.async_get_decentralized_device_by_sensor_info(si, data['device'], data['fam14'], channel)
                    if _bd.external_id not in self.devices or not self.devices[_bd.external_id].bus_device:
                        self.devices[_bd.external_id] = _bd
                        self.controller.fire_event(ControllerEventType.UPDATE_SENSOR_REPRESENTATION, _bd)


    def get_device_by_id(self, device_id:str):
        for d in self.devices.values():
            if d.external_id == device_id:
                return d
            
        return None
    
    def get_sensors_configured_in_a_device(self, device:Device) -> [Device]:
        """returns all sensors configured in a device"""
        sensors = []

        # if bus device selected
        for m in device.memory_entries:
            #for device with many addresses check if channel fits
            if device.channel == m.channel:

                # if sensor has global address
                if m.sensor_id_str in self.devices:
                    sensors.append(self.devices[m.sensor_id_str])

                else:
                    m_ext_id = add_addresses(m.sensor_id_str, device.base_id)
                    if m_ext_id in self.devices:
                        sensors.append(self.devices[m_ext_id])

        return sensors
    
    
    def get_devices_containing_sensor_in_config(self, sensor:Device) ->[Device]:
        """returns all devices which contain the given sensor in its config"""
        devices = []

        # if sensor selected
        for d in self.devices.values():
            for m in d.memory_entries:
                if sensor.address == m.sensor_id_str:
                    if d.channel == m.channel:
                        # sensor with global id
                        if m.sensor_id_str == sensor.external_id:
                            devices.append(d)
                        # sensor with local bus id
                        elif d.base_id == sensor.base_id:
                            devices.append(d)
        return devices


    def get_related_devices(self, device_external_id:str) -> [Device]:
        """returns a list of all devices in which a sensor is entered or sensors which are configured inside an device."""

        device:Device = self.devices[device_external_id]
        
        devices = []
        devices.extend( self.get_sensors_configured_in_a_device(device) )
        devices.extend( self.get_devices_containing_sensor_in_config(device) )
        return devices

    def get_detected_sensor_by_id(self, id:str) -> dict:
        if id not in self.detected_sensors.keys():
            self.detected_sensors[id] = {
                CONF_ID: id
            }

        return self.detected_sensors[id]
    
    def find_sensors(self, dev_id:int, in_func_group: int) -> [SensorInfo]:
        result = []
        for s in self.collected_sensor_list: 
            if int.from_bytes(s.dev_adr, "big") == dev_id and s.in_func_group == in_func_group:
                result.append(s)
        return result
    
    def find_sensor(self, dev_id:int, in_func_group: int) -> SensorInfo:
        l = self.find_sensors(dev_id, in_func_group)
        if len(l) > 0:
            return l[0]
        return None

    def find_device_info(self, name):
        for i in EEP_MAPPING:
            if i['hw-type'] == name:
                return i
        return None
    
    def add_or_get_sensor(self, sensor_id:str, device_id:str, dev_type:str) -> dict:
        sensor = None
        if sensor_id not in self.detected_sensors.keys():
            
            log_msg = f"Add sensor: address: {sensor_id} from device {device_id} and device type: {dev_type}"
            logging.info(colored(log_msg, 'yellow'))
            self.controller.fire_event(ControllerEventType.LOG_MESSAGE, {'msg': log_msg, 'color': 'yellow'})

            sensor = { 
                CONF_ID: sensor_id,
                CONF_PLATFORM: CONF_UNKNOWN,
                CONF_EEP: CONF_UNKNOWN,
                CONF_REGISTERED_IN: [] 
            }
            self.detected_sensors[sensor_id] = sensor
        else:
            sensor = self.detected_sensors[sensor_id]

        if device_id is not None:
            sensor[CONF_REGISTERED_IN].append(f"{device_id} ({dev_type})")

        return sensor


    def add_detected_sensors_to_eltako_config(self):
        for s in self.detected_sensors.values():
            self.eltako[ s[CONF_PLATFORM] ].append( s )


    def add_sensors(self, sensors: [SensorInfo], base_id:int=None) -> [dict]:
        self.collected_sensor_list.extend( sensors )
        result = []

        for s in sensors:
            # if self.filter_out_base_address(s.sensor_id):
            _s = self.add_or_get_sensor(s.sensor_id_str, s.dev_adr_str, s.dev_type)
            _s[CONF_COMMENT] = KeyFunction(s.key_func).name
            _s[CONF_EEP] = self.get_eep_from_key_function_name(s.key_func)
            _s[CONF_NAME] = CONF_UNKNOWN

            if int.from_bytes(s.sensor_id, "big") <= 0xFFFF:
                _s[CONF_BASE_ID] = self.a2s( base_id )
                _s[CONF_EXTERNAL_ID] = self.a2s( base_id + int.from_bytes(s.sensor_id, "big") )
            elif int.from_bytes(s.sensor_id, "big") > 0xFFFF:
                _s[CONF_EXTERNAL_ID] = s.sensor_id_str

            # configured in device
            if CONF_CONFIGURED_IN_DEVICES not in _s:
                _s[CONF_CONFIGURED_IN_DEVICES] = {}
            ext_device_id = self.a2s(s.dev_id + s.channel-1 + base_id)
            memory_line_key = f"{ext_device_id}_{s.memory_line}"
            if memory_line_key not in _s[CONF_CONFIGURED_IN_DEVICES]:
                _s[CONF_CONFIGURED_IN_DEVICES][memory_line_key] = {
                        CONF_DEVICE_ID: s.sensor_id_str,
                        CONF_ID: s.sensor_id_str, 
                        CONF_MEMORY_LINE: s.memory_line,
                        CONF_SENSOR_KEY: s.key,
                        CONF_SENSOR_KEY_FUNCTION: s.key_func
                    }

            if s.key_func in KeyFunction.get_switch_sensor_list():
                _s[CONF_PLATFORM] = Platform.BINARY_SENSOR
                _s[CONF_EEP] = F6_02_01.eep_string
                _s[CONF_NAME] = "Switch"
            elif s.key_func in KeyFunction.get_contect_sensor_list():
                _s[CONF_PLATFORM] = Platform.BINARY_SENSOR
                _s[CONF_EEP] = D5_00_01.eep_string
                _s[CONF_DEVICE_CLASS] = "Window"
                _s[CONF_NAME] = "Contact"
                _s[CONF_INVERT_SIGNAL] = False
            result.append(_s)

            self.controller.fire_event(ControllerEventType.UPDATE_SENSOR_REPRESENTATION, _s)
        
        return result
                    

    def filter_out_base_address(self, sensor_id:bytes) -> bool:
        sensor_id_int = int.from_bytes(sensor_id, "big")
        return self.sender_base_address > sensor_id_int or self.sender_base_address+128 < sensor_id_int

    def get_eep_from_key_function_name(self, kf: KeyFunction) -> str:
        pos = KeyFunction(kf).name.find('EEP_')
        if pos > -1:
            substr = KeyFunction(kf).name[pos+4:pos+4+8]
            return substr
        return CONF_UNKNOWN

    async def filter_memory_entities_by_dev_id(self, sensors:[SensorInfo], dev_id:int) -> [SensorInfo]:
        result = []
        for s in sensors:
            s_dev_id = s.dev_id + s.channel-1
            if s_dev_id == dev_id:
                result.append(s)
        return result

    def update_device(self, device: Device) -> None:
        self.devices[device.external_id] = device

        if device.is_bus_device():
            self.controller.fire_event(ControllerEventType.UPDATE_DEVICE_REPRESENTATION, device)
        else:
            self.controller.fire_event(ControllerEventType.UPDATE_SENSOR_REPRESENTATION, device)

    async def add_device(self, device: BusObject, fam14: FAM14):
        device_type = type(device).__name__
        info = self.find_device_info(device_type)

        fam14_base_id_str:str = await fam14.get_base_id()
        # detects base if of FAM14
        if isinstance(device, FAM14):
            
            if fam14_base_id_str not in self.fam14_device_amapping.keys():
                self.fam14_device_amapping[fam14_base_id_str] = {}

                log_msg = f"Add device {type(fam14).__name__}: base_id: {fam14_base_id_str}, name: FAM14"
                logging.info(colored(log_msg,'yellow'))
                self.controller.fire_event(ControllerEventType.LOG_MESSAGE, {'msg': log_msg, 'color': 'yellow'})
                data = {
                    'fam14_base_id': fam14_base_id_str,
                    CONF_DEVICE: {
                        CONF_ID: self.a2s( device.address ),
                        CONF_EXTERNAL_ID: fam14_base_id_str
                    }
                }
                self.controller.fire_event(ControllerEventType.UPDATE_DEVICE_REPRESENTATION, data)

        # add actuators
        if info != None:
            base_id:int = int.from_bytes(AddressExpression.parse( fam14_base_id_str )[0], "big") 
            
            memory_entries = await device.get_all_sensors()
            
            for i in range(0,info['address_count']):

                dev_id_str:str = a2s( device.address+i )
                dev_ext_id_str:str = a2s( base_id + device.address+i )
                dev_obj = {
                    CONF_ID: dev_id_str,
                    CONF_EXTERNAL_ID: dev_ext_id_str,
                    CONF_EEP: f"{info[CONF_EEP]}",
                    CONF_NAME: f"{device_type} - {device.address+i}",
                }

                if 'sender_eep' in info: #info[CONF_TYPE] in ['light', 'switch', 'cover']:
                    dev_obj['sender'] = {
                        CONF_ID: f"{self.a2s( self.sender_base_address+device.address+i )}",
                        CONF_EEP: f"{info['sender_eep']}",
                    }
                
                if info[CONF_TYPE] == Platform.COVER:
                    dev_obj[CONF_DEVICE_CLASS] = 'shutter'
                    dev_obj[CONF_TIME_CLOSES] = 25
                    dev_obj[CONF_TIME_OPENS] = 25

                if info[CONF_TYPE] == Platform.CLIMATE:
                    dev_obj[CONF_TEMPERATURE_UNIT] = f"'{UnitOfTemperature.KELVIN}'"
                    dev_obj[CONF_MIN_TARGET_TEMPERATURE] = 16
                    dev_obj[CONF_MAX_TARGET_TEMPERATURE] = 25
                    thermostat = self.find_sensor(device.address, in_func_group=1)
                    if thermostat:
                        dev_obj[CONF_ROOM_THERMOSTAT] = {}
                        dev_obj[CONF_ROOM_THERMOSTAT][CONF_ID] = b2s(thermostat.sensor_id)
                        dev_obj[CONF_ROOM_THERMOSTAT][CONF_EEP] = A5_10_06.eep_string   #TODO: derive EEP from switch/sensor function

                        # add thermostat into sensor 
                        sensor = self.add_or_get_sensor(b2s(thermostat.sensor_id), dev_id_str, device_type)
                        sensor[CONF_PLATFORM] = Platform.SENSOR
                        sensor[CONF_EEP] = A5_10_06.eep_string
                        sensor[CONF_NAME] = "Temperature Sensor and Controller"
                    # #TODO: cooling_mode
                        
                dev_obj[CONF_MEMORY_ENTRIES] = await self.filter_memory_entities_by_dev_id(memory_entries, device.address+i)

                self.eltako[info[CONF_TYPE]].append(dev_obj)
                fam14_base_id = await fam14.get_base_id()
                self.fam14_device_amapping[fam14_base_id][dev_obj[CONF_EXTERNAL_ID]] = dev_obj
                
                log_msg = f"Add device {info[CONF_TYPE]}: id: {dev_obj[CONF_ID]}, eep: {dev_obj[CONF_EEP]}, name: {dev_obj[CONF_NAME]}"
                logging.info(colored(log_msg,'yellow'))
                self.controller.fire_event(ControllerEventType.LOG_MESSAGE, {'msg': log_msg, 'color': 'yellow'})

                self.controller.fire_event(ControllerEventType.UPDATE_DEVICE_REPRESENTATION, {'fam14_base_id': fam14_base_id, CONF_DEVICE: dev_obj})

            self.add_sensors(memory_entries, base_id )
    

    def guess_sensor_type_by_address(self, msg:ESP2Message)->str:
        if type(msg) == Regular1BSMessage:
            try:
                data = b"\xa5\x5a" + msg.body[:-1]+ (sum(msg.body[:-1]) % 256).to_bytes(2, 'big')
                _msg = Regular1BSMessage.parse(data)
                min_address = b'\x00\x00\x10\x01'
                max_address = b'\x00\x00\x14\x89'
                if min_address <= _msg.address and _msg.address <= max_address:
                    return "FTS14EM switch"
            except:
                pass
        
        if type(msg) == RPSMessage:
            if b'\xFE\xDB\x00\x00' < msg.address:
                return "Wall Switch /Rocker Switch"

        if type(msg) == Regular4BSMessage:
            return "Multi-Sensor ? "

        return "???"

    def add_sensor_from_wireless_telegram(self, msg: ESP2Message):
        if type(msg) in SENSOR_MESSAGE_TYPES:
            logging.debug(msg)
            if hasattr(msg, 'outgoing'):
                address = b2s(msg.address)
                info = ORG_MAPPING[msg.org]
                
                if address not in self.detected_sensors.keys():

                    sensor_type = self.guess_sensor_type_by_address(msg)
                    msg_type = type(msg).__name__
                    comment = f"Sensor Type: {sensor_type}, Derived from Msg Type: {msg_type}"

                    sensor = self.add_or_get_sensor(address, None, None)
                    if CONF_EEP not in sensor:
                        sensor[CONF_EEP] = info[CONF_EEP]
                    if CONF_NAME not in sensor:
                        sensor[CONF_NAME] = f"{info[CONF_NAME]} {address}"
                    if CONF_COMMENT not in sensor:
                        sensor[CONF_COMMENT] = comment

                    if info[CONF_TYPE] == Platform.BINARY_SENSOR:
                        sensor[CONF_DEVICE_CLASS] = 'window / door / smoke / motion / ?'

                    self.controller.fire_event(ControllerEventType.UPDATE_SENSOR_REPRESENTATION, sensor)

                elif int.from_bytes(msg.address, "big") < 0xFF:
                    pass
                    # unknow actuator on bus

    def generate_ha_config(self) -> str:
        ha_platforms = set([str(d.ha_platform) for d in self.devices.values() if d.ha_platform is not None])
        fam14s = [d for d in self.devices.values() if d.is_fam14() and d.use_in_ha]
        devices = [d for d in self.devices.values() if not d.is_fam14() and d.use_in_ha]

        out = f"{DOMAIN}:\n"
        out += f"  {CONF_GERNERAL_SETTINGS}:\n"
        out += f"    {CONF_FAST_STATUS_CHANGE}: False\n"
        out += f"    {CONF_SHOW_DEV_ID_IN_DEV_NAME}: False\n"
        out += f"\n"
        
        fam14_id = 0
        # add fam14 gateways
        for d in fam14s:
            fam14:Device = d
            fam14_id += 1
            out += f"  {CONF_GATEWAY}:\n"
            out += f"  - {CONF_ID}: {fam14_id}\n"
            gw_fam14 = GatewayDeviceType.GatewayEltakoFAM14.value
            gw_fgw14usb = GatewayDeviceType.GatewayEltakoFGW14USB.value
            out += f"    {CONF_DEVICE_TYPE}: {gw_fam14}   # you can simply change {gw_fam14} to {gw_fgw14usb}\n"
            out += f"    {CONF_BASE_ID}: {fam14.external_id}\n"
            out += f"    # {CONF_COMMENT}: {fam14.comment}\n"
            out += f"    {CONF_DEVICES}:\n"

            for platform in ha_platforms:
                out += f"      {platform}:\n"
                for _d in [d for d in devices if d.ha_platform == platform]:
                    device:Device = _d
                    # devices
                    if device.base_id == fam14.external_id:
                        out += self.config_section_from_device_to_string(device, True, 0) + "\n\n"
                    elif 'sensor' in platform:
                        out += self.config_section_from_device_to_string(device, True, 0) + "\n\n"
        # logs
        out += "logger:\n"
        out += "  default: info\n"
        out += "  logs:\n"
        out += f"    {DOMAIN}: info\n"

        return out



    def config_section_from_device_to_string(self, device:Device, is_list:bool, space_count:int=0) -> str:
        out = ""
        spaces = space_count*" " + "        "

        if device.comment:
            out += spaces + f"# {device.comment}\n"
        
        rel_devs = [f"{d.name} (Type: {d.device_type}, Adr: {d.address})" for d in self.get_related_devices(device.external_id)]
        if len(rel_devs):
            out += spaces + f"# Related devices: {', '.join(rel_devs)}\n"
            
        info = find_device_info_by_device_type(device.device_type)
        if info and 'PCT14-key-function' in info:
            kf = info['PCT14-key-function']
            fg = info['PCT14-function-group']
            out += spaces[:-2] + f"  # Use 'Write HA senders to devices' button or enter manually sender id in PCT14 into function group {fg} with function {kf} \n"    
        out += spaces[:-2] + f"- {CONF_ID}: {device.address}\n"
        out += spaces[:-2] + f"  {CONF_NAME}: {device.name}\n"
        out += spaces[:-2] + f"  {CONF_EEP}: {device.eep}\n"

        out += self.export_additional_fields(device.additional_fields, space_count)
        
        return out
    
    def export_additional_fields(self, additional_fields:dict, space_count:int=0) -> str:
        out = ""
        spaces = space_count*" " + "        "
        for key in additional_fields.keys():
            value = additional_fields[key]
            if isinstance(value, str) or isinstance(value, int):
                if key not in [CONF_COMMENT, CONF_REGISTERED_IN]:
                    if isinstance(value, str) and '?' in value:
                        value += " # <= NEED TO BE COMPLETED!!!"
                    out += f"{spaces}{key}: {value}\n"
            elif isinstance(value, dict):
                out += f"{spaces}{key}: \n"
                out += self.export_additional_fields(value, space_count+2)
        return out
    
    def save_as_yaml_to_flie(self, filename:str):
        logging.info(colored(f"\nStore config into {filename}", 'red', attrs=['bold']))
        
        config_str = self.generate_config()

        with open(filename, 'w', encoding="utf-8") as f:
            print(config_str, file=f)