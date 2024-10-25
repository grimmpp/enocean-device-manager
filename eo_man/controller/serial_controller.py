from enum import Enum
from serial import rs485
from typing import Iterator
from termcolor import colored
import logging
import threading
import socket

import serial.tools.list_ports

from eltakobus import *
from eltakobus.device import *
from eltakobus.locking import buslocked, UNLOCKED
from eltakobus.message import Regular4BSMessage

from esp2_gateway_adapter.esp3_serial_com import ESP3SerialCommunicator
from esp2_gateway_adapter.esp3_tcp_com import TCP2SerialCommunicator, detect_lan_gateways
from esp2_gateway_adapter.esp2_tcp_com import ESP2TCP2SerialCommunicator

from ..data.const import GatewayDeviceType, get_gateway_type_by_name
from ..data import data_helper
from ..data.const import GatewayDeviceType as GDT, GATEWAY_DISPLAY_NAMES as GDN

from .gateway_registry import GatewayRegistry

from .app_bus import AppBusEventType, AppBus

class SerialController():

    USB_VENDOR_ID = 0x0403

    def __init__(self, app_bus:AppBus, gw_registry: GatewayRegistry) -> None:
        self.app_bus = app_bus
        self._serial_bus = None
        self.connected_gateway_type = None
        self.connected_mdns_service = ''
        self.current_base_id:str = None
        self.current_device_type:GatewayDeviceType = None
        self.gateway_id:str = None

        self.gw_registry:GatewayRegistry = gw_registry
        
        self.received_bus_device_discovery:Dict[str,List[EltakoDiscoveryReply]] = {}
        self.current_discovery_reply = None
        self.received_bus_device_memory:Dict[str,List[EltakoMemoryResponse]] = {}

        self.app_bus.add_event_handler(AppBusEventType.WINDOW_CLOSED, self.on_window_closed)
    
    
    
    def on_window_closed(self, data) -> None:
        self.kill_serial_connection_before_exit()


    def is_connected_gateway_device_bus(self):
        return self.connected_gateway_type.startswith('FAM14') or self.connected_gateway_type.startswith('FGW14-USB')

    
    def is_serial_connection_active(self) -> bool:
        return self._serial_bus is not None and self._serial_bus.is_active()


    def is_fam14_connection_active(self) -> bool:
        return self.is_serial_connection_active() and self._serial_bus.suppress_echo


    def _received_serial_event(self, message: ESP2Message) -> None:
        try:
            self.process_base_id_and_version_info(message)

            self.process_discovery_message(message)

            # log received message
            self.app_bus.fire_event(AppBusEventType.SERIAL_CALLBACK, {'msg': message, 
                                                                    'base_id': self.current_base_id,
                                                                    'gateway_id': self.gateway_id})
            
        except Exception as e:
            logging.exception(e)
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': e, 'log-level': 'ERROR', 'color': 'red'})
            

    def process_base_id_and_version_info(self, message: ESP2Message):
        # receive base id
        if message.body[:2] == b'\x8b\x98':
            self.current_base_id = b2s(message.body[2:6])
            device_type_index = message.body[6]
            # for virtual network gateway check which gateway is really sending
            if device_type_index > 0:
                gw_type = GDT.get_by_index(device_type_index-1)
                self.current_device_type = gw_type

            data = {
                'type': self.current_device_type, 
                'mdns_service': self.connected_mdns_service,
                'base_id': self.current_base_id, 
                'gateway_id': self.current_base_id,
                'tcm_version': '', 
                'api_version': ''
            }

            if hasattr(self._serial_bus, 'host') and hasattr(self._serial_bus, 'port'):
                data['address'] = f"{self._serial_bus._host}:{self._serial_bus._port}"

            self.app_bus.fire_event(AppBusEventType.ASYNC_TRANSCEIVER_DETECTED, data)

        # receive software version 
        if message.body[:2] == b'\x8b\x8c':
            tcm_sw_v = '.'.join(str(n) for n in message.body[2:6])
            api_v = '.'.join(str(n) for n in message.body[6:10])

            data = {
                'type': self.current_device_type, 
                'mdns_service': self.connected_mdns_service,
                'base_id': self.current_base_id, 
                'gateway_id': self.current_base_id,
                'tcm_version': tcm_sw_v, 
                'api_version': api_v
            }

            if hasattr(self._serial_bus, 'host') and hasattr(self._serial_bus, 'port'):
                data['address'] = f"{self._serial_bus._host}:{self._serial_bus._port}"

            self.app_bus.fire_event(AppBusEventType.ASYNC_TRANSCEIVER_DETECTED, data)
        
    def process_discovery_message(self, message: EltakoDiscoveryReply):
        
        if isinstance(message, EltakoDiscoveryReply):
            self.current_discovery_reply = message
            if self.current_base_id not in self.received_bus_device_discovery:
                self.received_bus_device_discovery[self.current_base_id] = []
            self.received_bus_device_discovery[self.current_base_id].append( message )
            
            dev = None
            for o in sorted_known_objects:
                if message.model[0:2] in o.discovery_names and (o.size is None or o.size == message.reported_size):
                    dev = o(message)
                    break
            if dev is None:
                dev = BusObject(message)
            
            async def get_all_sensors(): return []
            dev.get_all_sensors = get_all_sensors

            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Found device: {dev}", 'color':'grey'})
            self.app_bus.fire_event(AppBusEventType.DEVICE_SCAN_STATUS, 'DEVICE_DETECTED')
            self.app_bus.fire_event(AppBusEventType.ASYNC_DEVICE_DETECTED, {'device': dev, 'base_id': self.current_base_id, 'force_overwrite': False})


    def process_memory_response(self, message: EltakoMemoryResponse):
        if self.current_discovery_reply and isinstance(message, EltakoMemoryResponse):
            if self.current_discovery_reply not in self.received_bus_device_memory:
                self.received_bus_device_memory[self.current_discovery_reply] = []
            self.received_bus_device_memory[self.current_discovery_reply].append( message )
            
            if message.row == self.current_discovery_reply.memory_size-1:
                
                dev = None
                for o in sorted_known_objects:
                    if self.current_discovery_reply.model[0:2] in o.discovery_names and (o.size is None or o.size == self.current_discovery_reply.reported_size):
                        dev = o(self.current_discovery_reply)
                        break
                if dev is None:
                    dev = BusObject(self.current_discovery_reply)
                dev.memory = [r.value for r in self.received_bus_device_memory[self.current_discovery_reply]]
                
                self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Found device: {dev}", 'color':'grey'})
                self.app_bus.fire_event(AppBusEventType.DEVICE_SCAN_STATUS, 'DEVICE_DETECTED')
                asyncio.run( self.app_bus.fire_event(AppBusEventType.ASYNC_DEVICE_DETECTED, {'device': dev, 'base_id': self.current_base_id, 'force_overwrite': True}) )


    def connection_status_handler(self, connected: bool):
        self.app_bus.fire_event(AppBusEventType.CONNECTION_STATUS_CHANGE, {'connected': connected})


    def establish_serial_connection(self, serial_port:str, device_type:str) -> None:
        baudrate:int=57600
        delay_message:float=.1
        self.current_device_type = get_gateway_type_by_name(device_type)
        self.connected_mdns_service = None
        if device_type == GDN[GDT.EltakoFAMUSB]:
            baudrate = 9600
        elif device_type == GDN[GDT.EltakoFAM14]:
            delay_message = 0.001

        try:
            if not self.is_serial_connection_active():
                if device_type == GDN[GDT.LAN]:
                    ip_address = serial_port[:serial_port.rfind(':')]
                    port = int(serial_port[serial_port.rfind(':')+1:])
                    self.connected_mdns_service = self.gw_registry.find_mdns_service_by_ip_address(serial_port)
                    self._serial_bus = TCP2SerialCommunicator(ip_address, port,
                                                              callback=self._received_serial_event,
                                                              esp2_translation_enabled=True,
                                                              auto_reconnect=False
                                                              )

                elif device_type == GDN[GDT.ESP3]:
                    self._serial_bus = ESP3SerialCommunicator(serial_port, 
                                                              callback=self._received_serial_event,
                                                              esp2_translation_enabled=True,
                                                              auto_reconnect=False
                                                              )
                elif device_type == GDN[GDT.LAN_ESP2]:
                    ip_address = serial_port[:serial_port.rfind(':')]
                    port = int(serial_port[serial_port.rfind(':')+1:])
                    self.connected_mdns_service = self.gw_registry.find_mdns_service_by_ip_address(serial_port)
                    self._serial_bus = ESP2TCP2SerialCommunicator(ip_address, port,
                                                                  callback=self._received_serial_event,
                                                                  auto_reconnect=False)
                    
                else:
                    self._serial_bus = RS485SerialInterfaceV2(serial_port, 
                                                              baud_rate=baudrate, 
                                                              callback=self._received_serial_event, 
                                                              delay_message=delay_message,
                                                              auto_reconnect=False)
                self._serial_bus.start()
                self._serial_bus.is_serial_connected.wait(timeout=2)
                self._serial_bus.set_status_changed_handler(self.connection_status_handler)
                
                if not self._serial_bus.is_active():
                    self._serial_bus.stop()
                
                if self._serial_bus.is_active():
                    self.connected_gateway_type = device_type
                    if device_type in [GDN[GDT.LAN], GDN[GDT.LAN_ESP2] ]:
                        msg = f"TCP to Serial connection established. Server: {serial_port}"
                    else:
                        msg = f"Serial connection established. serial port: {serial_port}, baudrate: {baudrate}"
                    self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'color':'green'})
                    
                    if device_type == GDN[GDT.EltakoFAM14]:

                        def run():
                            asyncio.run( self._get_fam14_device_on_bus() )
                            self.app_bus.fire_event(
                                AppBusEventType.CONNECTION_STATUS_CHANGE, 
                                {'serial_port':  serial_port, 'baudrate': baudrate, 'connected': self._serial_bus.is_active()})
                            
                        t = threading.Thread(target=run)
                        t.start()
                    else:
                        if device_type in [ GDN[GDT.EltakoFAMUSB], GDN[GDT.ESP3], GDN[GDT.LAN] ]:
                            asyncio.run( self.async_create_gateway_device() )

                        self.app_bus.fire_event(
                                AppBusEventType.CONNECTION_STATUS_CHANGE, 
                                {'serial_port':  serial_port, 'baudrate': baudrate, 'connected': self._serial_bus.is_active()})
            
                else:
                    self.app_bus.fire_event(AppBusEventType.CONNECTION_STATUS_CHANGE, {'serial_port':  serial_port, 'baudrate': baudrate, 'connected': False})
                    if device_type == GDN[GDT.LAN]:
                        msg = f"Couldn't establish connection to {serial_port}! Try to restart device."
                    else:
                        msg = f"Establish connection for {device_type} on port {serial_port} failed! Device not ready."
                    self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'log-level': 'ERROR', 'color': 'red'})

        except Exception as e:
            self._serial_bus.stop()
            self.connected_gateway_type = None
            self.app_bus.fire_event(AppBusEventType.CONNECTION_STATUS_CHANGE, {'serial_port':  serial_port, 'baudrate': baudrate, 'connected': False})
            if device_type == GDN[GDT.LAN]:
                msg = f"Establish connection for {device_type} to {serial_port} failed! Retry later."
            else:
                msg = f"Establish connection for {device_type} on port {serial_port} failed!"
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'log-level': 'ERROR', 'color': 'red'})
            logging.exception(msg, exc_info=True)
   

    async def async_create_gateway_device(self):

        await asyncio.sleep(2)

        await self._serial_bus.send_base_id_request()

        await self._serial_bus.send_version_request()                 

    

    def send_message(self, msg: EltakoMessage) -> None:
        asyncio.run( self._serial_bus.send(msg) ) 


    def stop_serial_connection(self) -> None:
        if self.is_serial_connection_active():
            self._serial_bus.stop()
            self._serial_bus._stop_flag.wait()

            time.sleep(0.5)

            self.app_bus.fire_event(AppBusEventType.CONNECTION_STATUS_CHANGE, {'connected': self._serial_bus.is_active()})
            if not self._serial_bus.is_active():
                self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Serial connection stopped.", 'color':'green'})
            self.current_base_id = None
            self.gateway_id = None
            self.connected_gateway_type = None
            self._serial_bus = None


    def kill_serial_connection_before_exit(self) -> None:
        if self.is_serial_connection_active():
            self._serial_bus.stop()


    def scan_for_devices(self, force_overwrite:bool=False) -> None:
        # if connected to FAM14
        if self.is_fam14_connection_active():
            
            t = threading.Thread(target=lambda: asyncio.run( self._scan_for_devices_on_bus(force_overwrite) )  )
            t.start()


    async def enumerate_bus(self) -> Iterator[BusObject]: # type: ignore
        """Search the bus for devices, yield bus objects for every match"""

        skip_until = 0

        for i in range(1, 256):
            try:
                if i > skip_until:
                    self.app_bus.fire_event(AppBusEventType.DEVICE_ITERATION_PROGRESS, i/256.0*100.0)
                    bus_object = await create_busobject(bus=self._serial_bus, id=i)
                    skip_until = i + bus_object.size -1
                    yield bus_object
            except TimeoutError:
                continue
            except Exception as e:
                msg = 'Cannot detect device'
                self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'log-level': 'ERROR', 'color': 'red'})
                logging.exception(msg, exc_info=True)


    async def _get_fam14_device_on_bus(self, force_overwrite:bool=False) -> None:
        is_locked = False
        try:
            logging.debug(colored("Start scanning for devices", 'red'))

            self._serial_bus.set_callback( None )

            is_locked = (await locking.lock_bus(self._serial_bus)) == locking.LOCKED
            
            # first get fam14 and make it know to data manager
            fam14:FAM14 = await create_busobject(bus=self._serial_bus, id=255)
            self.current_base_id = await fam14.get_base_id()
            self.gateway_id = data_helper.a2s( (await fam14.get_base_id_in_int()) + 0xFF )
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Found device: {fam14}", 'color':'grey'})
            await self.app_bus.async_fire_event(AppBusEventType.ASYNC_DEVICE_DETECTED, {'device': fam14, 'base_id': self.current_base_id, 'force_overwrite': force_overwrite})

        except Exception as e:
            msg = 'Failed to load FAM14!!!'
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'log-level': 'ERROR', 'color': 'red'})
            logging.exception(msg, exc_info=True)
            raise e
        finally:
            if is_locked:
                resp = await locking.unlock_bus(self._serial_bus)
            self._serial_bus.set_callback( self._received_serial_event )


    async def _scan_for_devices_on_bus(self, force_overwrite:bool=False) -> None:
        is_locked = False
        try:
            self.app_bus.fire_event(AppBusEventType.DEVICE_SCAN_STATUS, 'STARTED')
            
            msg = "Start scanning for devices"
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'color':'red'})

            self._serial_bus.set_callback( None )

            is_locked = (await locking.lock_bus(self._serial_bus)) == locking.LOCKED
            
            # first get fam14 and make it know to data manager
            fam14:FAM14 = await create_busobject(bus=self._serial_bus, id=255)
            logging.debug(colored(f"Found device: {fam14}",'grey'))
            await self.app_bus.async_fire_event(AppBusEventType.ASYNC_DEVICE_DETECTED, {'device': fam14, 'base_id': self.current_base_id, 'force_overwrite': force_overwrite})

            # iterate through all devices
            async for dev in self.enumerate_bus():
                try:
                    await dev.read_mem()
                    self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Found device: {dev}", 'color':'grey'})
                    self.app_bus.fire_event(AppBusEventType.DEVICE_SCAN_STATUS, 'DEVICE_DETECTED')
                    await self.app_bus.async_fire_event(AppBusEventType.ASYNC_DEVICE_DETECTED, {'device': dev, 'base_id': self.current_base_id, 'force_overwrite': force_overwrite})

                except TimeoutError:
                    logging.error("Read error, skipping: Device %s announces %d memory but produces timeouts at reading" % (dev, dev.discovery_response.memory_size))

            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': "Device scan finished.", 'color':'red'})
        except Exception as e:
            msg = 'Device scan failed!'
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'log-level': 'ERROR', 'color': 'red'})
            logging.exception(msg, exc_info=True)
            raise e
        finally:
            # print("Unlocking the bus again")
            if is_locked:
                await locking.unlock_bus(self._serial_bus)

            self.app_bus.fire_event(AppBusEventType.DEVICE_SCAN_STATUS, 'FINISHED')
            self._serial_bus.set_callback( self._received_serial_event )

    def write_sender_id_to_devices(self, sender_id_list:dict={}):
        t = threading.Thread(target=lambda: asyncio.run( self.async_write_sender_id_to_devices(sender_id_list) )  )
        t.start()


    async def async_ensure_programmed(self, fam14_base_id_int:int, dev:BusObject, sender_id_list:dict):
        #HEATING = [FAE14SSR]
        if isinstance(dev, HasProgrammableRPS) or isinstance(dev, DimmerStyle):# or type(dev) in HEATING:
            for i in range(0,dev.size):
                device_ext_id_str = b2s( (fam14_base_id_int + dev.address+i).to_bytes(4,'big'))

                if device_ext_id_str in sender_id_list:
                    update_result = None
                    if 'sender' in sender_id_list[device_ext_id_str]:
                        sender_id_str = sender_id_list[device_ext_id_str]['sender']['id']
                        sender_eep_str = sender_id_list[device_ext_id_str]['sender']['eep']
                        sender_address = AddressExpression.parse(sender_id_str)
                        eep_profile = EEP.find(sender_eep_str)

                        # if type(dev) in HEATING:
                        #     # need to be at a special position 12 and 13
                        #     continue
                        #     mem_line:bytes = sender_address[0] + bytes((0, 65, 1, 0))
                        #     #TODO: NOT PROPERLY WORKING
                        #     await dev.write_mem_line(12 + i, mem_line)
                        # else:
                        retry = 3
                        exception = None
                        error_msg = {'msg': f'Failed to write sender id ({sender_id_str}) to device ({device_ext_id_str}). Will be retried up to {retry} times!',
                                        'log-level': 'ERROR', 
                                        'color': 'red'}

                        while retry > 0:
                            try:
                                update_result = await dev.ensure_programmed(i, sender_address, eep_profile)
                                retry=0
                                exception = None
                                time.sleep(0.2) # delay to avoid buffer overflow

                            except WriteError as e:
                                logging.exception(str(e))
                                self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, error_msg)
                                retry -= 1
                                exception = e
                            except TimeoutError as e:
                                logging.exception(str(e))
                                self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, error_msg)
                                retry -= 1
                                exception = e
                            except Exception as e:
                                logging.exception(str(e))
                                self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, error_msg)
                                retry -= 1
                                exception = e
                                

                        if exception is not None:
                            raise exception
                                
                        if update_result is None:
                            msg = f'Update for device {type(dev).__name__} ({device_ext_id_str}) NOT supported.'
                        elif update_result == True:
                            msg = f'Updated Home Assistant sender id {sender_id_str} for eep {sender_eep_str} in device {type(dev).__name__} {device_ext_id_str}.'
                        else:
                            msg = f'Sender id {sender_id_str} for eep {sender_eep_str} in device {type(dev).__name__} {device_ext_id_str} already exists.'

                        self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'color':'grey'})
                        self.app_bus.fire_event(AppBusEventType.WRITE_SENDER_IDS_TO_DEVICES_STATUS, 'DEVICE_UPDATED')


    async def async_write_sender_id_to_devices(self, sender_id_list:dict={}): # 45056 = 0x00 00 B0 00
        if not self.is_fam14_connection_active():
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': "Cannot write HA sender ids to devices because you are not connected to FAM14.", 'color':'red'})
        else:
            try:
                self.app_bus.fire_event(AppBusEventType.WRITE_SENDER_IDS_TO_DEVICES_STATUS, 'STARTED')
                self._serial_bus.set_callback( None )

                # print("Sending a lock command onto the bus; its reply should tell us whether there's a FAM in the game.")
                time.sleep(0.2)
                await locking.lock_bus(self._serial_bus)
                
                self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': "Start writing Home Assistant sender ids to devices", 'color':'red'})

                # first get fam14 and make it know to data manager
                fam14:FAM14 = await create_busobject(bus=self._serial_bus, id=255)
                fam14_base_id_int = await fam14.get_base_id_in_int()
                fam14_base_id = b2s(await fam14.get_base_id_in_bytes())
                msg = f"Update devices on Bus (fam14 base id: {fam14_base_id})"
                self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'color':'grey'})

                # iterate through all devices
                async for dev in self.enumerate_bus():
                    await self.async_ensure_programmed(fam14_base_id_int, dev, sender_id_list)

                self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': "Device scan finished.", 'color':'red'})
            except Exception as e:
                msg = 'Write sender id to devices failed!'
                self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'log-level': 'ERROR', 'color': 'red'})
                logging.exception(msg, exc_info=True)
                raise e
            finally:
                # print("Unlocking the bus again")
                await locking.unlock_bus(self._serial_bus)

                self.app_bus.fire_event(AppBusEventType.WRITE_SENDER_IDS_TO_DEVICES_STATUS, 'FINISHED')
                self._serial_bus.set_callback( self._received_serial_event )