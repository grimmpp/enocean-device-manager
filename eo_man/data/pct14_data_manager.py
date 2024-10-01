import xmltodict
import json

from eltakobus.device import *
from eltakobus.util import AddressExpression

from .. import LOGGER
from . import data_helper

from .ha_config_generator import HomeAssistantConfigurationGenerator
from .const import GatewayDeviceType
from .device import Device
from .data_helper import b2s, a2s, a2i, add_addresses, find_device_info_by_device_type

class PCT14DataManager:

    @classmethod
    async def get_devices_from_pct14(cls, filename:str) -> dict:
        devices = {}

        pct14_import = {}
        with open(filename, 'r') as file:
            import_data = xmltodict.parse(file.read())
            pct14_import = import_data['exchange']

        # detect fam14 first
        fam14_device:Device = await cls._create_fam14_device( pct14_import['rootdevice'] )
        devices[fam14_device.external_id] = fam14_device

        for d in pct14_import['devices']['device']:

            dev_size = int(d['header']['addressrange']['#text'])
            for i in range(1, dev_size+1):

                device = await cls._create_device(d, fam14_device, channel=i)
                devices[device.external_id] = device

                for si in device.memory_entries:
                    s:Device = Device.get_decentralized_device_by_sensor_info(si)
                    devices[s.external_id] = s

                    if device.is_ftd14():                    
                        s2:Device = Device.get_decentralized_device_by_sensor_info(si, device.additional_fields['second base id'])
                        devices[s2.external_id] = s2

        return devices


    @classmethod
    async def write_sender_ids_into_existing_pct14_export(cls, source_filename:str, target_filename:str, devices:dict[str,Device], base_id:str):

        with open(source_filename) as xml_file:
            data_dict = xmltodict.parse(xml_file.read())

        fam14_device:Device = await cls._create_fam14_device( data_dict['exchange']['rootdevice'] )
        
        # iterate through PCT14 devices 
        for d in data_dict['exchange']['devices']['device']:

            # interate through device channels
            dev_size = int(d['header']['addressrange']['#text'])
            hw_info = find_device_info_by_device_type(d['name']['#text'])
            if hw_info == {} or 'PCT14-key-function' not in hw_info: 
                print(f"No HW Type fond for: {d['name']['#text']}")
                continue
            function_id = hw_info['PCT14-key-function']

            for i in range(1, dev_size+1):

                # check if device is in eo_man
                external_id = cls._get_external_id(fam14_device, i, d)
                if external_id in devices:
                    _d = devices[external_id]
                    if 'sender' in _d.additional_fields and not cls._is_device_registered(_d, d, i, base_id, function_id):
                        # check if HA sender is registered
                        cls._add_ha_sender_id_into_pct14_xml(base_id, d, d['data']['rangeofid']['entry'], _d)
                    else:
                        LOGGER.debug(f"PCT14 Export Extender: device {_d.name} ('{_d.external_id}' already registered in actuator {d['name']['#text']})")

        # Convert the modified dictionary back to XML
        new_xml = xmltodict.unparse(data_dict, pretty=True)

        # Write the updated XML back to a file
        with open(target_filename, 'w') as xml_file:
            xml_file.write(new_xml)
        LOGGER.debug(f"PCT14 Export Extender: process completed.")

    @classmethod
    def _add_ha_sender_id_into_pct14_xml(cls, base_id, xml_device, xml_entries, device: Device):
        index_range = data_helper.find_device_class_by_name(xml_device['name']['#text']).sensor_address_range
        free_index = -1
        for i in index_range:
            free_index = i
            for n in xml_entries:
                if int(n['entry_number']) == i:
                    free_index = -1
                    break
            if free_index > -1:
                break
            
        sender_id = device.additional_fields['sender']['id']
        if free_index > -1:
            xml_entries.append({
                'entry_number': free_index,
                'entry_id': cls._get_sender_id(base_id, sender_id),
                'entry_function': device.key_function,
                'entry_button': 0,
                'entry_channel': device.channel,
                'entry_value': 0
            })
            LOGGER.debug(f"PCT14 Export Extender: Added sender id '{sender_id}' to PCT14 export for device {device.name} '{device.external_id}'.")
        else:
            LOGGER.warning(f"PCT14 Export Extender:  Cannot add sender id '{sender_id}' entry into device  {device.name} '{device.external_id}'.")

    @classmethod
    def _get_sender_id(cls, base_id: str, sender_id:str):
        sender_offset_id = base_id
        str_id = data_helper.a2s( int(sender_id, base=16) + data_helper.a2i(sender_offset_id) )
        int_id = int(''.join(str_id.split('-')[::-1]), base=16)
        return int_id
            

    @classmethod
    def _is_device_registered(cls, device:Device, pct14_device, channel:int, base_id:str, function_id:int):
        if not isinstance(pct14_device['data']['rangeofid']['entry'], list):
            return False
        
        ha_id = add_addresses(base_id, '00-00-00-'+device.additional_fields['sender']['id'])

        for e in pct14_device['data']['rangeofid']['entry']:

            is_registered = int(e['entry_channel']) & (2**(channel-1)) 
            is_registered = is_registered and (int(e['entry_function']) == function_id)
            is_registered = is_registered and (b2s(cls._convert_sensor_id_to_bytes(e['entry_id'])) == ha_id)
            if is_registered:
                return True
        return False

    @classmethod 
    def _get_external_id(cls, fam14:Device, channel:int, xm_device:dict) -> str:
        id = int(xm_device['header']['address']['#text']) + channel - 1
        return add_addresses(fam14.base_id, a2s(id))

    @classmethod
    async def _create_device(cls, import_obj, fam14:Device, channel:int=1):
        bd = Device()
        bd.additional_fields = {}
        id = int(import_obj['header']['address']['#text']) + channel - 1
        bd.address = a2s( id )
        bd.channel = channel
        bd.dev_size = int(import_obj['header']['addressrange']['#text'])
        bd.use_in_ha = True
        bd.base_id = fam14.base_id
        bd.device_type = import_obj['name']['#text']
        if 'FAM14' in bd.device_type: bd.device_type = GatewayDeviceType.EltakoFAM14.value
        if 'FGW14' in bd.device_type: bd.device_type = GatewayDeviceType.EltakoFGW14USB.value
        if 'FTD14' in bd.device_type: bd.device_type = GatewayDeviceType.EltakoFTD14.value
        int_version = int(import_obj['header']['versionofsoftware']['#text'])
        hex_version = format(int_version, 'X')
        bd.version = f"{hex_version[0]}.{hex_version[1]}"
        bd.key_function = ''
        bd.comment = import_obj['description'].get('#text', '')
        if isinstance(import_obj['channels']['channel'], list):
            for c in import_obj['channels']['channel']:
                if int(c['@channelnumber']) == channel and len(c['@description']) > 0:
                    bd.comment += f" - {c['@description']}"
        else:
            c = import_obj['channels']['channel']
            if int(c['@channelnumber']) == channel and len(c['@description']) > 0:
                    bd.comment += f" - {c['@description']}"

        bd.bus_device = True
        bd.external_id = cls._get_external_id(fam14, channel, import_obj)

        if 'entry' in import_obj['data']['rangeofid']:
            bd.memory_entries = cls._get_sensors_from_xml(bd, import_obj['data']['rangeofid']['entry'])
        else:
            bd.memory_entries = []

        # print(f"{bd.device_type} {bd.address}")
        # print_memory_entires( bd.memory_entries)
        # print("\n")
        bd.name = f"{bd.device_type.upper()} - {bd.address}"
        if bd.comment not in [None, '']:
            bd.name = f"{bd.device_type.upper()} - {bd.comment}"
        else:
            if bd.dev_size > 1:
                bd.name += f" ({bd.channel}/{bd.dev_size})"

        Device.set_suggest_ha_config(bd)

        return bd

    @classmethod
    def _convert_xml_baseid(cls, xml_baseid):
        numbers = []
        for i in range(0,4):
            number = format(int(xml_baseid['baseid_byte_'+str(i)]),'X')
            if len(number) == 1: number = '0'+number
            numbers.append(number)
        return '-'.join(numbers)

        # return f"{}-{format(int(xml_baseid['baseid_byte_1']),'2X')}-{format(int(xml_baseid['baseid_byte_2']),'2X')}-{format(int(xml_baseid['baseid_byte_3']),'2X')}"

    @classmethod
    async def _create_fam14_device(cls, import_obj):
        bd = Device()
        bd.additional_fields = {}
        xml_baseid = import_obj['rootdevicedata']['baseid']
        bd.address = cls._convert_xml_baseid(xml_baseid)
        bd.channel = 1
        bd.dev_size = int(import_obj['header']['addressrange']['#text'])
        bd.use_in_ha = True
        bd.base_id = bd.address
        bd.device_type = FAM14
        bd.device_type = GatewayDeviceType.EltakoFAM14.value

        bd.version = "" #TODO: '.'.join(map(str,device.version))
        bd.key_function = ''
        bd.comment = import_obj['description']['#text']
        bd.bus_device = True
        bd.external_id = bd.base_id

        bd.memory_entries = []
        if bd.comment not in [None, '']:
            bd.name = f"{bd.device_type} - {bd.comment}"
        else:
            bd.name = f"{bd.device_type} - {bd.address}"
        
        Device.set_suggest_ha_config(bd)

        return bd
    

    @classmethod
    def _convert_sensor_id_to_bytes(cls, id:str):
        hex_rep = format(int(id), 'X')
        if len(hex_rep) % 2 == 1:
            hex_rep = "0"+hex_rep
        hex_rep = [hex_rep[i:i+2] for i in range(0, len(hex_rep), 2)]
        hex_rep = hex_rep[::-1]
        hex_string = '-'.join(hex_rep)
        return AddressExpression.parse(hex_string)[0]


    @classmethod
    def _get_sensors_from_xml(cls, device:Device, sensors) -> list[SensorInfo]:
        return [cls._get_sensor_from_xml(device, s) for s in sensors]

    @classmethod
    def _get_sensor_from_xml(cls, device:Device, sensor) -> list[SensorInfo]:

        hw_info = find_device_info_by_device_type(device.device_type)
        if hw_info:
            hw_info = hw_info['hw-type']
        else:
            hw_info = None

        return SensorInfo(
                dev_type = hw_info,
                sensor_id = cls._convert_sensor_id_to_bytes(sensor['entry_id']),
                dev_adr = a2i(device.address).to_bytes(4, byteorder = 'big'),
                key = int(sensor['entry_button']),
                dev_id = device.address,
                key_func = int(sensor['entry_function']),
                channel = int(sensor['entry_channel']),
                in_func_group=None,
                memory_line = int(sensor['entry_number'])
                )