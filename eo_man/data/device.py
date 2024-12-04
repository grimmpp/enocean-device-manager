import copy
from eltakobus.device import SensorInfo, KeyFunction
from eltakobus.util import b2s, AddressExpression
from eltakobus.device import BusObject, FAM14, FTD14
from eltakobus.message import *
from eltakobus.eep import *

from homeassistant.const import CONF_ID, CONF_DEVICE, CONF_DEVICES, CONF_NAME, CONF_PLATFORM, CONF_TYPE, CONF_DEVICE_CLASS, CONF_TEMPERATURE_UNIT, UnitOfTemperature, Platform

from .data_helper import *
from .const import *

class Device():
    """Data representation of a device"""
    
    def __init__(self, 
                 address:str=None, 
                 bus_device:bool=False,
                 dev_size:int=1,
                 channel:int=1, 
                 external_id:str=None, 
                 device_type:str=None, 
                 version:str=None, 
                 name:str=None, 
                 comment:str=None, 
                 base_id:str=None, 
                 use_in_ha:bool=False,
                 memory_entries:list[SensorInfo]=[]):
        
        self.address:str = address
        self.bus_device:bool = bus_device
        self.channel:int = channel
        self.dev_size:int = dev_size
        self.external_id:str = external_id
        self.device_type:str = device_type
        self.version:str = version
        self.name:str = name
        self.comment:str = comment
        self.base_id:str = base_id
        self.use_in_ha:bool = use_in_ha
        self.memory_entries:list[SensorInfo] = memory_entries

        self.ha_platform:Platform=None
        self.key_function:str=None
        self.eep:str=None

        self.static_info:dict={}
        self.additional_fields:dict={}


    def is_fam14(self) -> bool:
        return self.device_type is not None and (FAM14.__name__ in self.device_type or self.device_type == GatewayDeviceType.EltakoFAM14.value)

    def is_fam_usb(self) -> bool:
        return self.device_type is not None and ('FAM-USB' in self.device_type or 'FAM_USB' in self.device_type or self.device_type == GatewayDeviceType.EltakoFAMUSB.value)
    
    def is_fgw14_usb(self) -> bool:
        return self.device_type is not None and ('FGW14_USB' in self.device_type or self.device_type == GatewayDeviceType.EltakoFGW14USB.value)

    def is_usb300(self) -> bool:
        return self.device_type is not None and ('USB300' in self.device_type or self.device_type == GatewayDeviceType.USB300.value)
    
    def is_lan_gw(self) -> bool:
        return self.device_type is not None and ('lan' in self.device_type or self.device_type in [GatewayDeviceType.LAN.value, GatewayDeviceType.LAN_ESP2.value])

    def is_ftd14(self) -> bool:
        return self.device_type == GatewayDeviceType.EltakoFTD14.value
    
    def is_EUL_Wifi_gw(self) -> bool:
        return self.device_type == GatewayDeviceType.EUL_LAN.value or self.is_mdns_service('EUL')
    
    def is_mgw(self) -> bool:
        return self.device_type == GatewayDeviceType.MGW_LAN.value or self.is_mdns_service('SmartConn')
    
    def is_virtual_home_assistant_gw(self) -> bool:
        return self.device_type == GatewayDeviceType.VirtualNetworkAdapter.value or self.is_mdns_service('Virtual-Network-Gateway-Adapter')

    def is_mdns_service(self, service_name) -> bool:
        if 'mdns_service' in self.additional_fields and self.additional_fields['mdns_service'] is not None:
            return service_name in self.additional_fields['mdns_service']
        return False

    def is_gateway(self) -> bool:
        return self.is_wired_gateway() or self.is_wireless_transceiver()
    
    def is_wired_gateway(self) -> bool:
        return self.is_fam14() or self.is_fgw14_usb() or self.is_mgw()

    def is_wireless_transceiver(self) -> bool:
        return self.is_usb300() or self.is_fam_usb() or self.is_lan_gw() or (self.device_type is not None and 'Wireless Transceiver' in self.device_type) or self.is_EUL_Wifi_gw()
    
    def is_bus_device(self) -> bool:
        return self.bus_device
        # return self.address.startswith('00-00-00-')            

    @classmethod
    def merge_devices(cls, device1, device2):
        d1:Device = device1
        d2:Device = device2

        if d1.external_id != d2.external_id: return None

        d1.address = d2.address
        d1.channel = d2.channel
        d1.dev_size = d2.dev_size
        d1.device_type = d2.device_type
        d1.version = d2.version
        if d1.name == 'unknown': d1.name = d2.name
        if d1.comment is None or d1.comment == '': d1.comment = d2.comment
        d1.base_id = d2.base_id
        d1.memory_entries = d2.memory_entries
        if not d1.bus_device: d1.bus_device = d2.bus_device
        if d1.key_function is None or d1.key_function == '': d1.key_function = d2.key_function
        d1.use_in_ha = d2.use_in_ha
        d1.eep = d2.eep

        for k,v in d2.additional_fields.items():
            if k not in d1.additional_fields:
                d1.additional_fields[k] = v

    @classmethod
    async def async_get_bus_device_by_natvice_bus_object(cls, device: BusObject, base_id: str, channel:int=1):
        bd = Device()
        bd.additional_fields = {}
        id = device.address + channel -1
        bd.address = a2s( id )
        bd.channel = channel
        bd.dev_size = device.size
        bd.use_in_ha = True
        bd.base_id = base_id
        bd.device_type = type(device).__name__
        if bd.device_type == 'FAM14': bd.device_type = GatewayDeviceType.EltakoFAM14.value
        if bd.device_type == 'FGW14_USB': bd.device_type = GatewayDeviceType.EltakoFGW14USB.value
        if bd.device_type == 'FTD14': bd.device_type = GatewayDeviceType.EltakoFTD14.value
        bd.version = '.'.join(map(str,device.version))
        bd.key_function = ''
        bd.comment = ''
        bd.bus_device = True
        if isinstance(device, FAM14):
            bd.external_id = bd.base_id
        elif isinstance(device, FTD14):
            # bd.base_id = await device.get_base_id()    # TODO: needs to have different base id
            bd.external_id = add_addresses(bd.address, base_id)
        else:
            bd.external_id = add_addresses(bd.address, base_id)
        bd.memory_entries = [m for m in (await device.get_all_sensors()) if b2s(m.dev_adr) == bd.address]
        # print(f"{bd.device_type} {bd.address}")
        # print_memory_entires( bd.memory_entries)
        # print("\n")
        bd.name = f"{bd.device_type.upper()} {bd.address}"
        if bd.is_fam14():
            bd.name = f"{bd.device_type.upper()} ({bd.external_id})"
        # if bd.is_ftd14():
        #     ftd_base_id = await device.get_base_id()
        #     bd.additional_fields['second base id'] = ftd_base_id
        #     bd.name += f" ({ftd_base_id})"
        
        if bd.dev_size > 1:
            bd.name += f" ({bd.channel}/{bd.dev_size})"

        Device.set_suggest_ha_config(bd)

        if bd.device_type == BusObject.__name__:
            bd.device_type = "unknown"
            bd.name = f"unknown device  {bd.address}"

        return bd
    
    @classmethod
    def get_feature_as_device(cls, device):
        feature = None

        info = find_device_info_by_device_type(device.device_type+"-feature")
        if len(info) > 0:
            feature:Device = copy.deepcopy(device)
            feature.additional_fields = {}
            feature.device_type = device.device_type+"-feature"
            feature.address = device.address + " "
            feature.external_id = device.external_id + " "

            Device.set_suggest_ha_config(feature, use_in_ha=True)
            
        return feature
            

    @classmethod
    def init_sender_fields(cls, device, overwrite:bool=False): 
        if device.additional_fields is None:
            device.additional_fields = {}

    
    @classmethod
    def set_suggest_ha_config(cls, device, use_in_ha:bool=False):
        id = int.from_bytes( AddressExpression.parse(device.address)[0], 'big')
        
        if device.device_type not in ('', 'unknown', None):
            info:dict = find_device_info_by_device_type(device.device_type)
        elif device.eep not in ('', 'unknown', None):
            info:dict = find_device_info_by_eep(device.eep)
        else:
            return

        if info is not None:
            device.use_in_ha = (device.device_type != BusObject.__name__) or use_in_ha
            device.ha_platform = info.get(CONF_TYPE, device.ha_platform)
            device.eep = info.get(CONF_EEP, device.eep)
            if device.comment == '' or is_device_description(info.get('description', '')):
                device.comment = info.get('description', device.comment)

            if info.get('sender_eep', None):
                device.additional_fields['sender'] = {
                    CONF_ID:  a2s( a2i(device.address) % 128 )[-2:],
                    CONF_EEP: info.get('sender_eep')
                }
            else:
                if 'sender' in device.additional_fields: del device.additional_fields['sender']

            if info.get(CONF_TYPE, None) == Platform.COVER:
                device.additional_fields[CONF_DEVICE_CLASS] = 'shutter'
                device.additional_fields[CONF_TIME_CLOSES] = 25
                device.additional_fields[CONF_TIME_OPENS] = 25
            else:
                if CONF_DEVICE_CLASS in device.additional_fields:   del device.additional_fields[CONF_DEVICE_CLASS]
                if CONF_TIME_CLOSES in device.additional_fields:    del device.additional_fields[CONF_TIME_CLOSES]
                if CONF_TIME_OPENS in device.additional_fields:     del device.additional_fields[CONF_TIME_OPENS]

            if info.get(CONF_TYPE, None) == Platform.CLIMATE:
                device.additional_fields[CONF_TEMPERATURE_UNIT] = f"'{UnitOfTemperature.KELVIN}'"
                device.additional_fields[CONF_MIN_TARGET_TEMPERATURE] = 16
                device.additional_fields[CONF_MAX_TARGET_TEMPERATURE] = 25
                thermostat = BusObjectHelper.find_sensor(device.memory_entries, device.address, device.channel, in_func_group=1)
                if thermostat:
                    device.additional_fields[CONF_ROOM_THERMOSTAT] = {}
                    device.additional_fields[CONF_ROOM_THERMOSTAT][CONF_ID] = b2s(thermostat.sensor_id)
                    device.additional_fields[CONF_ROOM_THERMOSTAT][CONF_EEP] = A5_10_06.eep_string   #TODO: derive EEP from switch/sensor function
                else:
                    if CONF_ROOM_THERMOSTAT in device.additional_fields: del device.additional_fields[CONF_ROOM_THERMOSTAT]
                #TODO: cooling_mode
            else:
                if CONF_TEMPERATURE_UNIT in device.additional_fields:       del device.additional_fields[CONF_TEMPERATURE_UNIT]
                if CONF_MIN_TARGET_TEMPERATURE in device.additional_fields: del device.additional_fields[CONF_MIN_TARGET_TEMPERATURE]
                if CONF_MAX_TARGET_TEMPERATURE in device.additional_fields: del device.additional_fields[CONF_MAX_TARGET_TEMPERATURE]
                if CONF_ROOM_THERMOSTAT in device.additional_fields:        del device.additional_fields[CONF_ROOM_THERMOSTAT]

            if info.get(CONF_METER_TARIFFS, None):
                device.additional_fields[CONF_METER_TARIFFS] = info.get(CONF_METER_TARIFFS)
            elif device.eep in [A5_12_01.eep_string, A5_12_02.eep_string, A5_12_03.eep_string]:
                device.additional_fields[CONF_METER_TARIFFS] = '[1]'
            else:
                if CONF_METER_TARIFFS in device.additional_fields: del device.additional_fields[CONF_METER_TARIFFS]
    
    @classmethod
    def get_decentralized_device_by_telegram(cls, msg: RPSMessage):
        bd = Device()
        bd.address = b2s( msg.address )
        bd.bus_device = False
        bd.base_id = '00-00-00-00'
        bd.device_type = 'unknown'
        bd.version = 'unknown'
        bd.comment = ''
        if int.from_bytes( msg.address, "big") > 0x0000FFFF:
            bd.external_id = b2s( msg.address )
        else:
            bd.external_id = 'unknown'
        bd.name = 'unknown'
        return bd
    
    @classmethod
    def get_centralized_device_by_telegram(cls, msg: RPSMessage, base_id:str, external_id:str):
        bd = Device()
        bd.bus_device = True
        bd.address = b2s( msg.address )
        bd.base_id = base_id
        bd.external_id = external_id
        bd.device_type = 'unknown'
        bd.version = 'unknown'
        bd.comment = ''
        bd.name = 'unknown'
        return bd
    
    @classmethod
    async def async_get_decentralized_device_by_sensor_info(cls, sensor_info:SensorInfo, fam14: FAM14):
        return cls.get_decentralized_device_by_sensor_info(sensor_info, (await fam14.get_base_id()) )
    
    @classmethod 
    def get_decentralized_device_by_sensor_info(cls, sensor_info:SensorInfo, base_id:str='00-00-00-00'):
        bd = Device()
        bd.address = sensor_info.sensor_id_str
        bd.comment = ''
        bd.key_function = KeyFunction(sensor_info.key_func).name
        bd.eep = get_eep_from_key_function_name(sensor_info.key_func)
        bd.name = f"{get_name_from_key_function_name(sensor_info.key_func)} {sensor_info.sensor_id_str}"
        # found sensor by EEP in KeyFunction
        if bd.eep and bd.name:
            bd.use_in_ha = True
            bd.device_type = 'Sensor'
            bd.ha_platform = Platform.SENSOR
        # buttons but ignore virtual buttons from HA
        elif 'PUSH_BUTTON' in KeyFunction(sensor_info.key_func).name and not sensor_info.sensor_id_str.startswith('00-00-'):
            bd.use_in_ha = True
            bd.device_type = 'Button'
            bd.ha_platform = Platform.BINARY_SENSOR
            bd.eep = F6_02_01.eep_string
            bd.name = f"Button {sensor_info.sensor_id_str}"
        # is from FTS14EM
        elif int.from_bytes(sensor_info.sensor_id, "big") < 0x1500:
            bd.use_in_ha = True
            bd.device_type = 'FTS14EM Button'
            bd.ha_platform = Platform.BINARY_SENSOR
            bd.eep = F6_02_01.eep_string
            bd.name = 'FTS14EM Button ' + sensor_info.sensor_id_str
        elif bd.address.startswith('00-00-B') or 'FROM_CONTROLLER' in bd.key_function:
            bd.use_in_ha = False
            bd.device_type = 'Smart Home'
            bd.ha_platform = ''
            bd.eep = ''
            bd.name = 'HA Controller ' + sensor_info.sensor_id_str
        elif 'WEATHER_STATION' in bd.key_function:
            bd.use_in_ha = True
            bd.device_type = 'Weather Station'
            bd.ha_platform = Platform.SENSOR
            bd.eep = 'A5-04-02'
            bd.name = 'Weather Station ' + sensor_info.sensor_id_str

        if sensor_info.sensor_id_str.startswith('00-00-'):
            bd.external_id = a2s( int.from_bytes(sensor_info.sensor_id, "big") + int.from_bytes(AddressExpression.parse(base_id)[0], 'big') )
            bd.base_id = base_id
        else:
            bd.external_id = sensor_info.sensor_id_str
            bd.base_id = '00-00-00-00'
        bd.version = 'unknown'
        return bd