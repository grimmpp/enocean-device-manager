from ..controller.app_bus import AppBus, AppBusEventType
from . import data_helper 
from .device import Device 
from .application_data import ApplicationData
from .filter import DataFilter
from .const import *
from .app_info import ApplicationInfo as AppInfo
from .recorded_message import RecordedMessage
from .message_history import MessageHistoryEntry

from eltakobus.util import AddressExpression, b2s
from eltakobus.eep import EEP
from eltakobus.message import *

class DataManager():
    """Manages EnOcean Devices"""

    def __init__(self, app_bus:AppBus):
        self.app_bus = app_bus
        self.app_bus.add_event_handler(AppBusEventType.SERIAL_CALLBACK, self._serial_callback_handler)
        self.app_bus.add_event_handler(AppBusEventType.ASYNC_DEVICE_DETECTED, self._async_device_detected_handler)
        self.app_bus.add_event_handler(AppBusEventType.LOAD_FILE, self._reset)
        self.app_bus.add_event_handler(AppBusEventType.SET_DATA_TABLE_FILTER, self.set_current_data_filter_handler)
        self.app_bus.add_event_handler(AppBusEventType.REMOVED_DATA_TABLE_FILTER, self.remove_current_data_filter_handler)
        self.app_bus.add_event_handler(AppBusEventType.ASYNC_TRANSCEIVER_DETECTED, self._async_transceiver_detected)
        self.app_bus.add_event_handler(AppBusEventType.SEND_MESSAGE_TEMPLATE_LIST_UPDATED, self.on_update_send_message_template_list)

        # devices
        self.devices:dict[str:Device] = {}

        # filter
        self.data_fitlers:dict[str:DataFilter] = {}
        self.selected_data_filter_name:DataFilter = None

        # recorded messages
        self.recoreded_messages:list[RecordedMessage] = []

        # message history
        self.send_message_template_list:list[MessageHistoryEntry] = None


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

        self.send_message_template_list = app_data.send_message_template_list

        self.recoreded_messages = app_data.recoreded_messages
        self.load_devices(app_data.devices)
        return app_data


    def write_application_data_to_file(self, filename:str):
        app_data = ApplicationData()
        app_data.application_version = AppInfo.get_version()
        app_data.data_filters = self.data_fitlers
        app_data.devices = self.devices
        app_data.selected_data_filter_name = self.selected_data_filter_name
        app_data.recoreded_messages = self.recoreded_messages
        app_data.send_message_template_list = self.send_message_template_list

        ApplicationData.write_to_yaml_file(filename, app_data)


    def _serial_callback_handler(self, data:dict):
        message:EltakoMessage = data['msg']
        current_base_id:str = data['base_id']
        gateway_id:str = data['gateway_id']

        if type(message) in [EltakoWrappedRPS,EltakoWrapped4BS, RPSMessage, Regular1BSMessage, Regular4BSMessage, TeachIn4BSMessage2]:
            # for decentral devices
            if int.from_bytes(message.address, "big") > 0X0000FFFF:
                dev_address = b2s(message.address)
                # add message to list
                self.recoreded_messages.append(RecordedMessage(message, dev_address, gateway_id))
                # if device unknown add device to list
                if dev_address not in self.devices:
                    decentralized_device = Device.get_decentralized_device_by_telegram(message)
                    self.devices[dev_address] = decentralized_device
                    self.app_bus.fire_event(AppBusEventType.UPDATE_SENSOR_REPRESENTATION, decentralized_device)

                # set eep if not available
                if type(message) == TeachIn4BSMessage2:
                    if self.devices[dev_address].eep in ('', 'unknown', None):
                        self.devices[dev_address].eep = b2s(message.profile)
                        Device.set_suggest_ha_config(self.devices[dev_address])
                        self.app_bus.fire_event(AppBusEventType.UPDATE_SENSOR_REPRESENTATION, self.devices[dev_address])

            
            # for bus devices
            elif current_base_id:
                external_id = data_helper.a2s( int.from_bytes(AddressExpression.parse(current_base_id)[0], 'big') +  int.from_bytes(message.address, 'big') )
                # add message to list
                self.recoreded_messages.append(RecordedMessage(message, external_id, gateway_id))
                # if device unknown add device to list
                if external_id not in self.devices:
                    centralized_device = Device.get_centralized_device_by_telegram(message, current_base_id, external_id)
                    self.devices[centralized_device.external_id] = centralized_device
                    self.app_bus.fire_event(AppBusEventType.UPDATE_DEVICE_REPRESENTATION, centralized_device)

            


    async def _async_transceiver_detected(self, data):
        base_id = data['base_id']
        if data.get('type', None) is not None:
            gw_device = Device(address=base_id,
                             bus_device=False,
                             external_id=base_id,
                             base_id=base_id,
                             name=f"{data['type'].value} ({base_id})",
                             device_type=data['type'].value,
                             use_in_ha=True,
                             )
            
            if gw_device.external_id not in self.devices:
                self.devices[gw_device.external_id] = gw_device
                
            elif data['api_version'] and data['tcm_version']:
                gw_device.version = f"api: {data['api_version']}, tcm: {data['tcm_version']}"

            if data['type'] in [GatewayDeviceType.LAN, GatewayDeviceType.LAN_ESP2]:
                gw_device.additional_fields['address'] = data['address']

            if 'mdns_service' in data and data['mdns_service'] is not None:
                gw_device.additional_fields['mdns_service'] = data['mdns_service']

            self.app_bus.fire_event(AppBusEventType.UPDATE_SENSOR_REPRESENTATION, gw_device)
                



    async def _async_device_detected_handler(self, data):
        for channel in range(1, data['device'].size+1):
            bd:Device = await Device.async_get_bus_device_by_natvice_bus_object(data['device'], data['base_id'], channel)
            
            update = data['force_overwrite']
            update |= bd.external_id not in self.devices
            update |= bd.external_id in self.devices and self.devices[bd.external_id].device_type is None 
            update |= bd.external_id in self.devices and self.devices[bd.external_id].device_type == ''
            update |= bd.external_id in self.devices and self.devices[bd.external_id].device_type == 'unknown'

            if update:
                self.devices[bd.external_id] = bd
                self.app_bus.fire_event(AppBusEventType.UPDATE_DEVICE_REPRESENTATION, bd)

            for si in bd.memory_entries:
                _bd:Device = Device.get_decentralized_device_by_sensor_info(si, data['base_id'])

                if _bd.external_id not in self.devices or update or not self.devices[_bd.external_id].bus_device:
                    self.devices[_bd.external_id] = _bd
                    self.app_bus.fire_event(AppBusEventType.UPDATE_SENSOR_REPRESENTATION, _bd)

                # add device a second time with base id of FTD14
                if bd.is_ftd14():                    
                    _bd:Device = Device.get_decentralized_device_by_sensor_info(si, bd.additional_fields['second base id'])
                
                    if _bd.external_id not in self.devices or update or not self.devices[_bd.external_id].bus_device:
                        self.devices[_bd.external_id] = _bd
                        self.app_bus.fire_event(AppBusEventType.UPDATE_SENSOR_REPRESENTATION, _bd)
                
            # add features of device as own entity/device
            feature = Device.get_feature_as_device(bd)
            if feature is not None and (feature.external_id not in self.devices or update): 
                self.devices[feature.external_id] = feature
                self.app_bus.fire_event(AppBusEventType.UPDATE_DEVICE_REPRESENTATION, feature)

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
        try:
            eep = None
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
                    eep:EEP = data_helper.find_eep_by_name(device.eep)
                    return eep, ', '.join(data_helper.get_values_for_eep(eep, message))
                except:
                    pass
        except:
            pass
        return eep, None
    

    def on_update_send_message_template_list(self, data:list[str]):
        self.send_message_template_list = data
    