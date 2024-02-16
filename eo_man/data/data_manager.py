import os
from termcolor import colored
import logging

from ..controller.app_bus import AppBus, AppBusEventType
from . import data_helper 
from .device import Device 
from .application_data import ApplicationData
from .filter import DataFilter
from .const import *
from homeassistant.const import CONF_ID, CONF_DEVICES, CONF_NAME

from eltakobus.util import AddressExpression, b2s
from eltakobus.eep import EEP
from eltakobus.message import RPSMessage, Regular1BSMessage, Regular4BSMessage, EltakoMessage, EltakoWrappedRPS,EltakoWrapped4BS

class DataManager():
    """Manages EnOcean Devices"""

    def __init__(self, app_bus:AppBus):
        self.app_bus = app_bus
        self.app_bus.add_event_handler(AppBusEventType.SERIAL_CALLBACK, self._serial_callback_handler)
        self.app_bus.add_event_handler(AppBusEventType.ASYNC_DEVICE_DETECTED, self._async_device_detected_handler)
        self.app_bus.add_event_handler(AppBusEventType.LOAD_FILE, self._reset)
        self.app_bus.add_event_handler(AppBusEventType.SET_DATA_TABLE_FILTER, self.set_current_data_filter_handler)
        self.app_bus.add_event_handler(AppBusEventType.REMOVED_DATA_TABLE_FILTER, self.remove_current_data_filter_handler)
        
        self.application_version = data_helper.get_application_version()
        self.devices:dict[str:Device] = {}
        self.data_fitlers:dict[str:DataFilter] = {}
        self.selected_data_filter_name:DataFilter = None


    def set_current_data_filter_handler(self, filter:DataFilter):
        if filter is not None:
            self.selected_data_filter_name = filter.name
        else:
            self.selected_data_filter_name = None


    def remove_current_data_filter_handler(self, filter:DataFilter):
        if self.selected_data_filter_name is not None and self.selected_data_filter_name == filter.name:
            self.selected_data_filter_name = None


    def add_filter(self, filter:DataFilter) -> None:
        self.data_fitlers[filter.name] = filter

        self.app_bus.fire_event(AppBusEventType.ADDED_DATA_TABLE_FILTER, filter)


    def remove_filter(self, filter:DataFilter) -> None:
        if filter.name in self.data_fitlers.keys():
            del self.data_fitlers[filter.name]

        self.app_bus.fire_event(AppBusEventType.REMOVED_DATA_TABLE_FILTER, filter)


    def _reset(self, data):
        self.devices = {}


    def load_data_filters(self, filters:list[DataFilter]):
        for f in filters.values():
            self.add_filter(f)


    def load_devices(self, devices:dict[str:Device]):
        # load FAM14 first because of dependencies
        d_list =  [d.external_id for d in devices.values() if d.is_fam14()] 
        d_list += [d.external_id for d in devices.values() if not d.is_fam14()] 
        for key in d_list:
            device:Device = devices[key]
            self.devices[key] = device
            if device.is_bus_device():
                self.app_bus.fire_event(AppBusEventType.UPDATE_DEVICE_REPRESENTATION, device)
            else:
                self.app_bus.fire_event(AppBusEventType.UPDATE_SENSOR_REPRESENTATION, device)


    def load_application_data_from_file(self, filename:str):
        # if filename.endswith('.eodm'):
        #     app_data:ApplicationData = ApplicationData.read_from_file(filename)
        # elif filename.endswith('.yaml'):
        #     app_data:ApplicationData = ApplicationData.read_from_yaml_file(filename)
        app_data:ApplicationData = ApplicationData.read_from_yaml_file(filename)
        
        self.load_data_filters(app_data.data_filters)
        self.selected_data_filter_name = app_data.selected_data_filter_name
        if self.selected_data_filter_name is None or self.selected_data_filter_name == '': 
            self.app_bus.fire_event(AppBusEventType.SET_DATA_TABLE_FILTER, None)
        elif self.selected_data_filter_name not in self.data_fitlers.keys():
            self.app_bus.fire_event(AppBusEventType.SET_DATA_TABLE_FILTER, None)
        else:
            self.app_bus.fire_event(AppBusEventType.SET_DATA_TABLE_FILTER, self.data_fitlers[self.selected_data_filter_name])

        self.load_devices(app_data.devices)
        return app_data


    def write_application_data_to_file(self, filename:str):
        app_data = ApplicationData()
        app_data.application_version = self.application_version
        app_data.data_filters = self.data_fitlers
        app_data.devices = self.devices
        app_data.selected_data_filter_name = self.selected_data_filter_name

        # if filename.endswith('.eodm'):
        #     ApplicationData.write_to_file(filename, app_data)
        # elif filename.endswith('.yaml'):
        #     ApplicationData.write_to_yaml_file(filename, app_data)
        # else:
        #     raise Exception('unknow file type')
        ApplicationData.write_to_yaml_file(filename, app_data)


    def _serial_callback_handler(self, data:dict):
        message:EltakoMessage = data['msg']
        current_base_id:str = data['base_id']

        # self.add_sensor_from_wireless_telegram(message)
        if type(message) in [EltakoWrappedRPS,EltakoWrapped4BS, RPSMessage, Regular1BSMessage, Regular4BSMessage]:
            if int.from_bytes(message.address, "big") > 0X000000FF:
                a = b2s(message.address)
                if a not in self.devices:
                    decentralized_device = Device.get_decentralized_device_by_telegram(message)
                    self.devices[a] = decentralized_device
                    self.app_bus.fire_event(AppBusEventType.UPDATE_SENSOR_REPRESENTATION, decentralized_device)
            elif current_base_id:
                external_id = data_helper.a2s( int.from_bytes(AddressExpression.parse(current_base_id)[0], 'big') +  int.from_bytes(message.address, 'big') )
                if external_id not in self.devices:
                    centralized_device = Device.get_centralized_device_by_telegram(message, current_base_id, external_id)
                    self.devices[centralized_device] = centralized_device
                    self.app_bus.fire_event(AppBusEventType.UPDATE_DEVICE_REPRESENTATION, centralized_device)


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
                self.app_bus.fire_event(AppBusEventType.UPDATE_DEVICE_REPRESENTATION, bd)

                for si in bd.memory_entries:
                    _bd:Device = await Device.async_get_decentralized_device_by_sensor_info(si, data['device'], data['fam14'], channel)
                    if _bd.external_id not in self.devices or not self.devices[_bd.external_id].bus_device:
                        self.devices[_bd.external_id] = _bd
                        self.app_bus.fire_event(AppBusEventType.UPDATE_SENSOR_REPRESENTATION, _bd)

                # if a new gateway was detected check if there are already devices detected which should be moved as child nodes under the newly detected gateway.
                if bd.is_fam14():
                    await self._find_and_update_devices_belonging_to_gateway(bd.base_id)


    async def _find_and_update_devices_belonging_to_gateway(self, base_id:str):
        """Check all devices which are not detected as bus device (decentral/wireless device) if it belong to a gateway."""
        base_id_int = int.from_bytes( AddressExpression.parse(base_id)[0], 'big' )
        for d in self.devices.values():
            if not d.bus_device and d.base_id == '00-00-00-00':
                adr_int = int.from_bytes( AddressExpression.parse(d.address)[0], 'big' )
                if 0 < (adr_int - base_id_int) and (adr_int - base_id_int) < 0xFF:
                    d.address = data_helper.a2s(adr_int - base_id_int)
                    d.bus_device = True
                    d.base_id = base_id

                    self.app_bus.fire_event(AppBusEventType.UPDATE_DEVICE_REPRESENTATION, d)


    def get_device_by_id(self, device_id:str):
        for d in self.devices.values():
            if d.external_id == device_id:
                return d
            
        return None
    
    def get_sensors_configured_in_a_device(self, device:Device) -> list[Device]:
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
                    m_ext_id = data_helper.add_addresses(m.sensor_id_str, device.base_id)
                    if m_ext_id in self.devices:
                        sensors.append(self.devices[m_ext_id])

        return sensors
    
    
    def get_devices_containing_sensor_in_config(self, sensor:Device) ->list[Device]:
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


    def get_related_devices(self, device_external_id:str) -> list[Device]:
        """returns a list of all devices in which a sensor is entered or sensors which are configured inside an device."""
        if device_external_id is None or device_external_id == '' or device_external_id == 'Distributed Devices':
            return []

        device:Device = self.devices[device_external_id]
        
        devices = []
        devices.extend( self.get_sensors_configured_in_a_device(device) )
        devices.extend( self.get_devices_containing_sensor_in_config(device) )
        return devices

  

    def update_device(self, device: Device) -> None:
        self.devices[device.external_id] = device

        if device.is_bus_device():
            self.app_bus.fire_event(AppBusEventType.UPDATE_DEVICE_REPRESENTATION, device)
        else:
            self.app_bus.fire_event(AppBusEventType.UPDATE_SENSOR_REPRESENTATION, device)


    def find_device_by_local_address(self, address:str, base_id:str) -> Device:
        local_adr = int.from_bytes(AddressExpression.parse(address)[0], "big")
        base_adr = int.from_bytes(AddressExpression.parse(base_id)[0], "big")

        if (local_adr + base_adr) > 0xFFFFFFFF:
            return None

        ext_id = data_helper.a2s(local_adr + base_adr)
        if ext_id in self.devices:
            return self.devices[ext_id]
        
        return None


    def get_values_from_message_to_string(self, message:EltakoMessage, base_id:str=None) -> str:
        # get ext id
        ext_id_str = b2s(message.address)
        if ext_id_str.startswith('00-00-00-') and base_id is not None:
            device:Device = self.find_device_by_local_address(ext_id_str, base_id)
            if device is None: 
                return None, None
            else:
                ext_id_str = device.external_id

        if ext_id_str in self.devices:
            device = self.devices[ext_id_str]
            try:
                eep:EEP = EEP.find(device.eep)
                properties_as_str = []
                for k, v in eep.decode_message(message).__dict__.items():
                    properties_as_str.append(f"{str(k)[1:] if str(k).startswith('_') else str(k)}: {str(v)}")

                return eep, ', '.join(properties_as_str)
            except:
                pass
        return None, None


    