import xmltodict
import json

from eltakobus.device import FAM14, SensorInfo
from eltakobus.util import AddressExpression

from .const import GatewayDeviceType
from .device import Device
from .data_helper import a2s, a2i, add_addresses, find_device_info_by_device_type

class PCT14DataManager:

    @classmethod
    async def get_devices_from_pct14(cls, filename:str) -> dict:
        devices = {}

        pct14_import = {}
        with open(filename, 'r') as file:
            import_data = xmltodict.parse(file.read())
            pct14_import = import_data['exchange']


        fam14_device:Device = await cls._create_fam14_device( pct14_import['rootdevice'] )
        devices[fam14_device.external_id] = fam14_device

        for d in pct14_import['devices']['device']:
            device = await cls._create_device(d, fam14_device)
            devices[device.external_id] = device

            for si in device.memory_entries:
                s:Device = Device.get_decentralized_device_by_sensor_info(si)
                devices[s.external_id] = s

                if device.is_ftd14():                    
                    s2:Device = Device.get_decentralized_device_by_sensor_info(si, device.additional_fields['second base id'])
                    devices[s2.external_id] = s2

        return devices


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
        bd.bus_device = True
        bd.external_id = add_addresses(fam14.base_id, a2s(id))

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
        return f"{format(int(xml_baseid['baseid_byte_0']),'X')}-{format(int(xml_baseid['baseid_byte_1']),'X')}-{format(int(xml_baseid['baseid_byte_2']),'X')}-{format(int(xml_baseid['baseid_byte_3']),'X')}"

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