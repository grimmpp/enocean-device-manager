from typing import Dict, List

from zeroconf import Zeroconf, ServiceBrowser, ServiceInfo

import socket

from .app_bus import AppBus, AppBusEventType
from ..data.const import GatewayDeviceType, get_gateway_type_by_name
from ..data import data_helper 

class LanServiceDetector:

    def __init__(self, app_bus: AppBus, update_callback) -> None:
        
        self.app_bus = app_bus
        self._update_callback = update_callback
        self.service_reg_lan_gw = {}
        self.service_reg_virt_lan_gw = {}
        self._start_service_discovery()


    def find_mdns_service_by_ip_address(self, address:str):
        service_list:List[Dict] = {}
        service_list.update(self.service_reg_lan_gw)
        service_list.update(self.service_reg_virt_lan_gw)

        for s in service_list.values():
            dns_name = f"{s['hostname'][:-1]}:{s['port']}"
            ip_address = f"{s['address']}:{s['port']}"
            if dns_name == address or ip_address == address:
                return s['name']
                
        return None

    def __del__(self):
        self.zeroconf.close()    

    def add_service(self, zeroconf: Zeroconf, type, name):
        try:
            info:ServiceInfo = zeroconf.get_service_info(type, name)
            obj = {'name': name, 'type': type, 'address': socket.inet_ntoa(info.addresses[0]), 'port': info.port, 'hostname': info.server}
            msg = f"Detected Network Service: {name}, type: {type}, address: {obj['address']}, port: {obj['address']}, hostname: {obj['address']}"
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'log-level': 'INFO', 'color': 'grey'})
            
            for mdns_name in data_helper.MDNS_SERVICE_2_GW_TYPE_MAPPING:
                if mdns_name in name:
                    gw_type: GatewayDeviceType = data_helper.MDNS_SERVICE_2_GW_TYPE_MAPPING[mdns_name]
                    if gw_type == GatewayDeviceType.LAN:
                        self.service_reg_lan_gw[name] = obj
                        break
                    elif gw_type == GatewayDeviceType.LAN_ESP2:
                        self.service_reg_virt_lan_gw[name] = obj
                        break

        except:
            pass

        self._update_callback()

    def remove_service(self, zeroconf, type, name):
        if name in self.service_reg_lan_gw:
            del self.service_reg_lan_gw[name]
        if name in self.service_reg_virt_lan_gw:
            del self.service_reg_virt_lan_gw[name]

        self._update_callback()

    def update_service(self, zeroconf, type, name):
        self._update_callback()

    def _start_service_discovery(self):
        self.zeroconf = Zeroconf()
        for mdns_type in data_helper.KNOWN_MDNS_SERVICES.values():
            ServiceBrowser(self.zeroconf, mdns_type, self)

    def get_virtual_network_gateway_service_endpoints(self):
        return [f"{s['hostname'][:-1]}:{s['port']}"  for s in self.service_reg_virt_lan_gw.values()]
    
    def get_lan_gateway_endpoints(self):
        return [f"{s['address']}:{s['port']}"  for s in self.service_reg_lan_gw.values()]