from datetime import datetime

from homeassistant.const import CONF_ID, CONF_DEVICES, CONF_NAME

from ..controller.app_bus import AppBus, AppBusEventType

from .app_info import ApplicationInfo as AppInfo
from .data_manager import DataManager
from .device import Device
from .const import *
from . import data_helper

class HomeAssistantConfigurationGenerator():

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
        

    def generate_ha_config(self, device_list:list[Device]) -> str:
        ha_platforms = set([str(d.ha_platform) for d in device_list if d.ha_platform is not None])
        fam14s = [d for d in device_list if d.is_fam14() and d.use_in_ha]
        devices = [d for d in device_list if not d.is_fam14() and d.use_in_ha]

        out = self.get_description()
        out += "\n"
        out += f"{DOMAIN}:\n"
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
    
    def save_as_yaml_to_file(self, filename:str):
        msg = f"Export Home Assistant configuration into {filename}"
        self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'color': 'red', 'log-level': 'INFO'})
        
        config_str = self.generate_ha_config(
            self.data_manager.devices.values()
        )

        with open(filename, 'w', encoding="utf-8") as f:
            print(config_str, file=f)

        msg = f"Export finished!"
        self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'color': 'grey', 'log-level': 'DEBUG'})