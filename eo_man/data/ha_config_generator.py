from datetime import datetime

from homeassistant.const import CONF_ID, CONF_DEVICES, CONF_NAME

from ..controller.app_bus import AppBus, AppBusEventType

from .app_info import ApplicationInfo as AppInfo
from .data_manager import DataManager
from .device import Device
from .const import *
from . import data_helper

class HomeAssistantConfigurationGenerator():

    LOCAL_SENDER_OFFSET_ID = '00-00-B0-00'

    def __init__(self, app_bus:AppBus, data_manager:DataManager):
        self.app_bus = app_bus
        self.data_manager = data_manager

    def get_description(self) -> str:
        return f"""
# DESCRIPTION:
#
# This is an automatically generated Home Assistant Configuration for the Eltako Integration (https://github.com/grimmpp/home-assistant-eltako)
# Generated at {datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")} and by: 'EnOcean Device Manager':
{AppInfo.get_app_info_as_str(prefix='# ')}#
# Hints:
# * The auto-generation considers all devices which are marked with 'Export to HA' = True. 
# * Decentralized devices are entered into the list under devices for every gateway. If you are using more than one gateway you probably want to have those only once listed. Please remove "dupplicated" entries.
# * FAM14 gatways can be easily exchanged by FGW14-USB gateways. You just need to change the value of 'device_type' from 'fam14' to 'fgw14usb'.
# * 'id' of the gateways are random and are just counted up. You can simply change them if needed. Just ensure that they are unique and not specified more than once. 
#
"""

    def get_gateway_by(self, gw_d:Device) -> GatewayDeviceType:
        gw_type = None
        for t in GatewayDeviceType:
            if GATEWAY_DISPLAY_NAMES[t.value].lower() in gw_d.device_type.lower():
                return t.value
        return None

    def perform_tests(self) -> str:
        device_list = [d for d in self.data_manager.devices.values() if not d.is_gateway() and d.use_in_ha]

        try:
            self.test_unique_sender_ids(device_list)
            return None
        except Exception as e:
            return str(e)

    def test_unique_sender_ids(self, device_list:list[Device]):
        sender_ids = {}
        for d in device_list:
            if 'sender' in d.additional_fields and 'id' in d.additional_fields['sender']:
                sender_id = d.additional_fields['sender']['id']
                if int(sender_id, 16) < 1 or int(sender_id, 16) > 127:
                    raise Exception(f"sender id '{sender_id}' of device '{d.external_id}' is no valid number between 1 and 127.")
                if sender_id in sender_ids:
                    raise Exception(f"sender id '{sender_id}' is assigned more than once for at least device '{sender_ids[sender_id].external_id}' and '{d.external_id}'.")
                
                sender_ids[sender_id] = d

    def generate_ha_config(self, device_list:list[Device]) -> str:
        ha_platforms = set([str(d.ha_platform) for d in device_list if d.ha_platform is not None])
        gateways = [d for d in device_list if d.is_gateway() and d.use_in_ha]
        devices = [d for d in device_list if not d.is_gateway() and d.use_in_ha]

        out = self.get_description()
        out += "\n"
        out += f"{DOMAIN}:\n"
        out += f"  {CONF_GERNERAL_SETTINGS}:\n"
        out += f"    {CONF_FAST_STATUS_CHANGE}: False\n"
        out += f"    {CONF_SHOW_DEV_ID_IN_DEV_NAME}: False\n"
        out += f"\n"
        
        global_gw_id = 0
        # add fam14 gateways
        for gw_d in gateways:
            global_gw_id += 1
            out += f"  {CONF_GATEWAY}:\n"
            out += f"  - {CONF_ID}: {global_gw_id}\n"

            gw_fam14 = GatewayDeviceType.EltakoFAM14.value
            gw_fgw14usb = GatewayDeviceType.EltakoFGW14USB.value
            
            # gw_type = self.get_gateway_by(gw_d)
            out += f"    {CONF_DEVICE_TYPE}: {gw_d.device_type}   # you can simply change {gw_fam14} to {gw_fgw14usb}\n"
            out += f"    {CONF_BASE_ID}: {gw_d.base_id}\n"
            out += f"    # {CONF_COMMENT}: {gw_d.comment}\n"
            if gw_d.device_type == GatewayDeviceType.LAN:
                out += f"    {CONF_GATEWAY_ADDRESS}: {gw_d.additional_fields['address']}\n"
            out += f"    {CONF_DEVICES}:\n"

            for platform in ha_platforms:
                if platform != '':
                    out += f"      {platform}:\n"
                    for device in devices:
                        if device.ha_platform == platform:
                            # add devices
                            out += self.config_section_from_device_to_string(gw_d, device, True, 0) + "\n\n"
        # logs
        out += "\n"
        out += "logger:\n"
        out += "  default: info\n"
        out += "  logs:\n"
        out += f"    {DOMAIN}: info\n"

        return out



    def config_section_from_device_to_string(self, gateway:Device, device:Device, is_list:bool, space_count:int=0) -> str:
        out = ""
        spaces = space_count*" " + "        "

        # add user comment
        if device.comment:
            out += spaces + f"# {device.comment}\n"
        
        # list related devices for comment
        rel_devs = []
        for d in self.data_manager.get_related_devices(device.external_id):
            rel_devs.append( f"{d.name} (Type: {d.device_type}, Adr: {d.address})" )
        if len(rel_devs):
            out += spaces + f"# Related devices: {', '.join(rel_devs)}\n"
            
        info = data_helper.find_device_info_by_device_type(device.device_type)
        if info and 'PCT14-key-function' in info:
            kf = info['PCT14-key-function']
            fg = info['PCT14-function-group']
            out += spaces[:-2] + f"  # Use 'Write HA senders to devices' button or enter manually sender id in PCT14 into function group {fg} with function {kf} \n"    
        adr = device.address if gateway.is_wired_gateway() and gateway.base_id == device.base_id else device.external_id
        out += spaces[:-2] + f"- {CONF_ID}: {adr.strip()}\n"
        out += spaces[:-2] + f"  {CONF_NAME}: {device.name}\n"
        out += spaces[:-2] + f"  {CONF_EEP}: {device.eep}\n"

        out += self.export_additional_fields(gateway, device.additional_fields, space_count)
        
        return out
    

    def export_additional_fields(self, gateway:Device, additional_fields:dict, space_count:int=0, parent_key:str=None) -> str:
        out = ""
        spaces = space_count*" " + "        "
        for key in additional_fields.keys():
            value = additional_fields[key]
            if parent_key in ['sender'] and key == 'id':
                if gateway.is_wired_gateway(): sender_offset_id = self.LOCAL_SENDER_OFFSET_ID
                else: sender_offset_id = gateway.base_id
                value = data_helper.a2s( int("0x"+value[-2:], base=16) + data_helper.a2i(sender_offset_id) )
            if isinstance(value, str) or isinstance(value, int):
                if key not in [CONF_COMMENT, CONF_REGISTERED_IN]:
                    if isinstance(value, str) and '?' in value:
                        value += " # <= NEED TO BE COMPLETED!!!"
                    out += f"{spaces}{key}: {value}\n"
            elif isinstance(value, dict):
                out += f"{spaces}{key}: \n"
                out += self.export_additional_fields(gateway, value, space_count+2, key)
        return out
    

    def save_as_yaml_to_file(self, filename:str):
        
        devices = self.data_manager.devices.values()

        config_str = self.generate_ha_config(devices)

        with open(filename, 'w', encoding="utf-8") as f:
            print(config_str, file=f)
