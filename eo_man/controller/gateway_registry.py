from typing import Dict, List
import threading
import asyncio

from ..data.const import GatewayDeviceType as GDT, GATEWAY_DISPLAY_NAMES as GDN

from .app_bus import AppBus, AppBusEventType

from .serial_port_detector import SerialPortDetector
from .lan_service_detector import LanServiceDetector

class GatewayRegistry:

    def __init__(self, app_bus: AppBus) -> None:
        
        self.serial_port_detector = SerialPortDetector(app_bus)
        self.lan_service_detector = LanServiceDetector(app_bus, self._update_lan_gateway_entries)

        self.endpoint_list:Dict[str, List[str]] = {}

        self._is_running = threading.Event()
        self._is_running.clear()

        self.app_bus = app_bus
        self.app_bus.add_event_handler(AppBusEventType.REQUEST_SERVICE_ENDPOINT_DETECTION, self._process_update_service_endpoints)


    def find_mdns_service_by_ip_address(self, address:str):
        return self.lan_service_detector.find_mdns_service_by_ip_address(address)
    

    def _update_lan_gateway_entries(self):
        self.endpoint_list[GDT.LAN.value] = self.lan_service_detector.get_lan_gateway_endpoints()
        self.endpoint_list[GDT.LAN_ESP2.value] = self.lan_service_detector.get_virtual_network_gateway_service_endpoints()

        self.app_bus.fire_event(AppBusEventType.SERVICE_ENDPOINTS_UPDATES, self.endpoint_list)


    async def async_update_service_endpoint_list(self, force_reload:bool=True) -> None:
            
        if not force_reload and len(self.endpoint_list) > 0:
            await self.app_bus.async_fire_event(AppBusEventType.SERVICE_ENDPOINTS_UPDATES, self.endpoint_list)
            
        else:
            self.endpoint_list:Dict[str, List[str]] = await self.serial_port_detector.async_get_gateway2serial_port_mapping()
            self.endpoint_list[GDT.LAN.value] = self.lan_service_detector.get_lan_gateway_endpoints()
            self.endpoint_list[GDT.LAN_ESP2.value] = self.lan_service_detector.get_virtual_network_gateway_service_endpoints()
            
            # put all service together in section all as well
            self.endpoint_list['all'] = []
            for k in self.endpoint_list:
                if k != 'all':
                    self.endpoint_list['all'].extend(self.endpoint_list[k])

            await self.app_bus.async_fire_event(AppBusEventType.SERVICE_ENDPOINTS_UPDATES, self.endpoint_list)


    async def _process_update_service_endpoints(self, force_update:bool=False):
        def process(force_update:bool=False):
            self._is_running.set()
            asyncio.run(self.async_update_service_endpoint_list(force_update))
            self._is_running.clear()

        if not self._is_running.is_set():
            t = threading.Thread(target=process, name="Thread-async_update_service_endpoint_list", args=(force_update,))
            t.daemon = True
            t.start()
