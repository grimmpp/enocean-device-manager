from enum import Enum
import sys
import glob
import serial
from serial import rs485
from typing import Iterator
from termcolor import colored
import logging
import threading


import serial.tools.list_ports
from serial.tools.list_ports_common import ListPortInfo

from eltakobus import *
from eltakobus.device import *
from eltakobus.locking import buslocked, UNLOCKED
from eltakobus.message import Regular4BSMessage

from esp2_gateway_adapter.esp3_serial_com import ESP3SerialCommunicator
from esp2_gateway_adapter.esp3_tcp_com import TCP2SerialCommunicator, detect_lan_gateways

from ..data import data_helper
from ..data.device import Device
from ..data.const import GatewayDeviceType as GDT, GATEWAY_DISPLAY_NAMES as GDN

from .app_bus import AppBusEventType, AppBus


class SerialController():

    USB_VENDOR_ID = 0x0403

    def __init__(self, app_bus:AppBus) -> None:
        self.app_bus = app_bus
        self._serial_bus = None
        self.connected_gateway_type = None
        self.current_base_id:str = None
        self.gateway_id:str = None
        self.port_mapping = None

        self.app_bus.add_event_handler(AppBusEventType.WINDOW_CLOSED, self.on_window_closed)
    

    def on_window_closed(self, data) -> None:
        self.kill_serial_connection_before_exit()




    def get_serial_ports(self, device_type:str, force_reload:bool=False) ->list[str]:
        if force_reload or self.port_mapping is None:
            self.port_mapping = self._get_gateway2serial_port_mapping()
            self.port_mapping[GDT.LAN] = detect_lan_gateways()

        if device_type == GDN[GDT.EltakoFAM14]:
            return self.port_mapping[GDT.EltakoFAM14.value]
        elif device_type == GDN[GDT.EltakoFGW14USB]:
            return self.port_mapping[GDT.EltakoFGW14USB.value]
        elif device_type == GDN[GDT.EltakoFAMUSB]:
            return self.port_mapping[GDT.EltakoFAMUSB.value]
        elif device_type == GDN[GDT.USB300]:
            return self.port_mapping[GDT.USB300.value]
        elif device_type == GDN[GDT.LAN]:
            return self.port_mapping[GDT.LAN]
        else:
            return []
    
    def is_connected_gateway_device_bus(self):
        return self.connected_gateway_type == 'FAM14' or self.connected_gateway_type == 'FGW14-USB'

    def _get_gateway2serial_port_mapping(self) -> dict[str:list[str]]:
        """ Lists serial port names

            :raises EnvironmentError:
                On unsupported or unknown platforms
            :returns:
                A list of the serial ports available on the system
        """
        # python -m serial.tools.miniterm COM10 57600 --encoding hexlify
        
        # _ports:list[ListPortInfo] = serial.tools.list_ports.comports()
        # for p in _ports:
        #     print(f"port: {p.device}, hwid: {p.hwid}")
        # print(len(_ports), 'ports found')

        if sys.platform.startswith('win'):
            ports = ['COM%s' % (i + 1) for i in range(256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            # this excludes your current terminal "/dev/tty"
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        else:
            raise EnvironmentError('Unsupported platform')
        
        # ports = [p.device for p in _ports if p.vid == self.USB_VENDOR_ID]

        fam14 = GDT.EltakoFAM14.value
        usb300 = GDT.USB300.value
        famusb = GDT.EltakoFAMUSB.value
        fgw14usb = GDT.EltakoFGW14USB.value
        result = { fam14: [], usb300: [], famusb: [], fgw14usb: [], 'all': [] }

        count = 0
        for baud_rate in [9600, 57600]:
            for port in ports:
                count += 1
                # take in 10 as one step and start with 10 to see directly process is running
                progress = min(round((count/(2*256.0))*10)*10 + 10, 100)
                self.app_bus.fire_event(AppBusEventType.DEVICE_ITERATION_PROGRESS, progress) 

                try:
                    # is faster to precheck with serial
                    s = serial.Serial(port, baudrate=baud_rate, timeout=0.2)
                    s.rs485_mode = serial.rs485.RS485Settings()
                    s.close()

                    # test usb300
                    if baud_rate == 57600:
                        s = ESP3SerialCommunicator(port, auto_reconnect=False)
                        s.start()
                        s.is_serial_connected.wait()

                        if s.base_id and isinstance(s.base_id, list) and port not in result['all']:
                            result[usb300].append(port)
                            result['all'].append(port)
                            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"USB300 detected on serial port {port},(baudrate: {baud_rate})", 'color':'lightgreen'})
                            s.stop()
                            continue

                        s.stop()
                    
                    # test fam14, fgw14-usb and fam-usb
                    s = RS485SerialInterfaceV2(port, baud_rate=baud_rate, delay_message=0.2, auto_reconnect=False)
                    s.start()
                    s.is_serial_connected.wait()

                    # test fam14
                    if s.suppress_echo and port not in result['all']:
                        result[fam14].append(port)
                        result['all'].append(port)
                        self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"FAM14 detected on serial port {port},(baudrate: {baud_rate})", 'color':'lightgreen'})
                        s.stop()
                        continue

                    # test fam-usb
                    if baud_rate == 9600:
                        # try to get base id of fam-usb to test if device is fam-usb
                        base_id = asyncio.run( self.async_get_base_id_for_fam_usb(s, None) )
                        # fam14 can answer on both baud rates but fam-usb cannot echo
                        if base_id is not None and base_id != '00-00-00-00' and not s.suppress_echo and port not in result['all']:
                            result[famusb].append(port)
                            result['all'].append(port)
                            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"FAM-USB detected on serial port {port},(baudrate: {baud_rate})", 'color':'lightgreen'})
                            s.stop()
                            continue

                    # fgw14-usb
                    if baud_rate == 57600:
                        if not s.suppress_echo and port not in result['all']:
                            result[fgw14usb].append(port)
                            result['all'].append(port)
                            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"FGW14-USB could be on serial port {port},(baudrate: {baud_rate})", 'color':'lightgreen'})
                            s.stop()
                            continue
                
                    s.stop()

                except (OSError, serial.SerialException) as e:
                    pass

        self.app_bus.fire_event(AppBusEventType.DEVICE_ITERATION_PROGRESS, 0)
        return result
    
    def is_serial_connection_active(self) -> bool:
        return self._serial_bus is not None and self._serial_bus.is_active()
    
    def is_fam14_connection_active(self) -> bool:
        return self.is_serial_connection_active() and self._serial_bus.suppress_echo

    def _received_serial_event(self, message) -> None:
        if isinstance(message.address, int):
             message.address = message.address.to_bytes(4, 'big')

        self.app_bus.fire_event(AppBusEventType.SERIAL_CALLBACK, {'msg': message, 
                                                                  'base_id': self.current_base_id,
                                                                  'gateway_id': self.gateway_id})

    def establish_serial_connection(self, serial_port:str, device_type:str) -> None:
        baudrate:int=57600
        delay_message:float=.1
        if device_type == GDN[GDT.EltakoFAMUSB]:
            baudrate = 9600
        elif device_type == GDN[GDT.EltakoFAM14]:
            delay_message = 0.001

        try:
            if not self.is_serial_connection_active():
                if device_type == GDN[GDT.LAN]:
                    baudrate=5100
                    self._serial_bus = TCP2SerialCommunicator(serial_port, 5100,
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
                else:
                    self._serial_bus = RS485SerialInterfaceV2(serial_port, 
                                                              baud_rate=baudrate, 
                                                              callback=self._received_serial_event, 
                                                              delay_message=delay_message,
                                                              auto_reconnect=False)
                self._serial_bus.start()
                self._serial_bus.is_serial_connected.wait(timeout=2)
                
                if not self._serial_bus.is_active():
                    self._serial_bus.stop()
                
                if self._serial_bus.is_active():
                    self.connected_gateway_type = device_type
                    if device_type == GDN[GDT.LAN]:
                        msg = f"TCP to Serial connection established. Server: {serial_port}:5100"
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
                        if device_type == GDN[GDT.EltakoFAMUSB]: 
                            asyncio.run( self.async_create_fam_usb_device() )
                        elif device_type == GDN[GDT.USB300]:
                            asyncio.run( self.async_create_usb300_device() )
                        elif device_type == GDN[GDT.LAN]:
                            asyncio.run( self.async_create_lan_gw_device(serial_port) )

                        self.app_bus.fire_event(
                                AppBusEventType.CONNECTION_STATUS_CHANGE, 
                                {'serial_port':  serial_port, 'baudrate': baudrate, 'connected': self._serial_bus.is_active()})
            
                else:
                    self.app_bus.fire_event(AppBusEventType.CONNECTION_STATUS_CHANGE, {'serial_port':  serial_port, 'baudrate': baudrate, 'connected': False})
                    if device_type == GDN[GDT.LAN]:
                        msg = f"Couldn't establish connection to {serial_port}:5100! Try to restart device."
                    else:
                        msg = f"Establish connection for {device_type} on port {serial_port} failed! Device not ready."
                    self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'log-level': 'ERROR', 'color': 'red'})

        except Exception as e:
            self._serial_bus.stop()
            self.connected_gateway_type = None
            self.app_bus.fire_event(AppBusEventType.CONNECTION_STATUS_CHANGE, {'serial_port':  serial_port, 'baudrate': baudrate, 'connected': False})
            if device_type == GDN[GDT.LAN]:
                msg = f"Establish connection for {device_type} to {serial_port}:5100 failed! Retry later."
            else:
                msg = f"Establish connection for {device_type} on port {serial_port} failed!"
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'log-level': 'ERROR', 'color': 'red'})
            logging.exception(msg, exc_info=True)


    async def async_create_lan_gw_device(self, address):
        try:
            self._serial_bus.set_callback( None )
            
            time.sleep(.4)

            self.current_base_id = b2s(self._serial_bus.base_id)
            self.gateway_id = self.current_base_id

            await self.app_bus.async_fire_event(AppBusEventType.ASYNC_TRANSCEIVER_DETECTED, {'type': GDN[GDT.LAN], 
                                                                                            'base_id': self.current_base_id, 
                                                                                            'gateway_id': self.gateway_id,
                                                                                            'address': address,
                                                                                            'tcm_version': '', 
                                                                                            'api_version': ''})


        except Exception as e:
            msg = 'Failed to get information about LAN GW (TCP2ESP3)!!!'
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'log-level': 'ERROR', 'color': 'red'})
            logging.exception(msg, exc_info=True)
            raise e
        finally:
            self._serial_bus.set_callback( self._received_serial_event )     

    async def async_create_usb300_device(self):
        try:
            self._serial_bus.set_callback( None )
            
            self.current_base_id = b2s(self._serial_bus.base_id)
            self.gateway_id = self.current_base_id

            await self.app_bus.async_fire_event(AppBusEventType.ASYNC_TRANSCEIVER_DETECTED, {'type': GDN[GDT.USB300], 
                                                                                            'base_id': self.current_base_id, 
                                                                                            'gateway_id': self.gateway_id,
                                                                                            'tcm_version': '', 
                                                                                            'api_version': ''})


        except Exception as e:
            msg = 'Failed to get information about USB300 (ESP3)!!!'
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'log-level': 'ERROR', 'color': 'red'})
            logging.exception(msg, exc_info=True)
            raise e
        finally:
            self._serial_bus.set_callback( self._received_serial_event )                    


    async def async_get_base_id_for_fam_usb(self, fam_usb:RS485SerialInterfaceV2, callback) -> str:
        base_id:str = None
        try:
            fam_usb.set_callback( None )
            
            # get base id
            data = b'\xAB\x58\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            # timeout really requires for this command sometimes 1sec!
            response:ESP2Message = await fam_usb.exchange(ESP2Message(bytes(data)), ESP2Message, retries=3, timeout=1)
            base_id = b2s(response.body[2:6])
        except:
            pass
        finally:
            fam_usb.set_callback( callback )

        return base_id
    

    def send_message(self, msg: EltakoMessage) -> None:
        asyncio.run( self._serial_bus.send(msg) ) 


    async def async_create_fam_usb_device(self):
        try:
            self._serial_bus.set_callback( None )
            
            # get base id
            data = b'\xAB\x58\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            response:ESP2Message = await self._serial_bus.exchange(ESP2Message(bytes(data)), ESP2Message)
            base_id = response.body[2:6]
            self.current_base_id = b2s(base_id)
            self.gateway_id = self.current_base_id

            # get version
            data = b'\xAB\x4B\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            response:ESP2Message = await self._serial_bus.exchange(ESP2Message(bytes(data)), ESP2Message)
            tcm_sw_v = '.'.join(str(n) for n in response.body[2:6])
            api_v = '.'.join(str(n) for n in response.body[6:10])

            await self.app_bus.async_fire_event(AppBusEventType.ASYNC_TRANSCEIVER_DETECTED, {'type': GDN[GDT.EltakoFAMUSB], 
                                                                                            'base_id': self.current_base_id, 
                                                                                            'gateway_id': self.gateway_id,
                                                                                            'tcm_version': tcm_sw_v, 
                                                                                            'api_version': api_v})


        except Exception as e:
            msg = 'Failed to get information about FAM-USB!!!'
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'log-level': 'ERROR', 'color': 'red'})
            logging.exception(msg, exc_info=True)
            raise e
        finally:
            self._serial_bus.set_callback( self._received_serial_event )

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
            await self.app_bus.async_fire_event(AppBusEventType.ASYNC_DEVICE_DETECTED, {'device': fam14, 'fam14': fam14, 'force_overwrite': force_overwrite})

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
            await self.app_bus.async_fire_event(AppBusEventType.ASYNC_DEVICE_DETECTED, {'device': fam14, 'fam14': fam14, 'force_overwrite': force_overwrite})

            # iterate through all devices
            async for dev in self.enumerate_bus():
                try:
                    self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Found device: {dev}", 'color':'grey'})
                    self.app_bus.fire_event(AppBusEventType.DEVICE_SCAN_STATUS, 'DEVICE_DETECTED')
                    await self.app_bus.async_fire_event(AppBusEventType.ASYNC_DEVICE_DETECTED, {'device': dev, 'fam14': fam14, 'force_overwrite': force_overwrite})

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