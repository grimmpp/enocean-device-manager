
from enum import Enum
import sys
import glob
import serial
from serial import rs485
from typing import Iterator
from termcolor import colored
import logging
import threading

from eltakobus import *
from eltakobus.device import *
from eltakobus.locking import buslocked, UNLOCKED
from eltakobus.message import Regular4BSMessage
from .esp3_serial_com import ESP3SerialCommunicator

from ..data import data_helper
from ..data.device import Device
from ..data.const import GatewayDeviceType

from .app_bus import AppBusEventType, AppBus


class SerialController():

    def __init__(self, app_bus:AppBus) -> None:
        self.app_bus = app_bus
        self._serial_bus = None
        self.current_base_id:str = None
        self.port_mapping = None

        self.app_bus.add_event_handler(AppBusEventType.WINDOW_CLOSED, self.on_window_closed)
    

    def on_window_closed(self, data) -> None:
        self.kill_serial_connection_before_exit()


    def get_serial_ports(self, device_type:str, force_reload:bool=False) ->list[str]:
        if force_reload or self.port_mapping is None:
            self.port_mapping = self._get_gateway2serial_port_mapping()

        if device_type == 'FAM14':
            return self.port_mapping[GatewayDeviceType.GatewayEltakoFAM14.value]
        elif device_type == 'FGW14-USB':
            return self.port_mapping[GatewayDeviceType.GatewayEltakoFGW14USB.value]
        elif device_type == 'FAM-USB':
            return self.port_mapping[GatewayDeviceType.GatewayEltakoFAMUSB.value]
        elif device_type == 'USB300':
            return self.port_mapping[GatewayDeviceType.GatewayEnOceanUSB300.value]
        else:
            return []
    

    def _get_gateway2serial_port_mapping(self) -> dict[str:list[str]]:
        """ Lists serial port names

            :raises EnvironmentError:
                On unsupported or unknown platforms
            :returns:
                A list of the serial ports available on the system
        """
        # python -m serial.tools.miniterm COM10 57600 --encoding hexlify
        
        if sys.platform.startswith('win'):
            ports = ['COM%s' % (i + 1) for i in range(256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            # this excludes your current terminal "/dev/tty"
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        else:
            raise EnvironmentError('Unsupported platform')

        fam14 = GatewayDeviceType.GatewayEltakoFAM14.value
        usb300 = GatewayDeviceType.GatewayEnOceanUSB300.value
        famusb = GatewayDeviceType.GatewayEltakoFAMUSB.value
        fgw14usb = GatewayDeviceType.GatewayEltakoFGW14USB.value
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

    def _send_serial_event(self, message) -> None:
        self.app_bus.fire_event(AppBusEventType.SERIAL_CALLBACK, {'msg': message, 'base_id': self.current_base_id})

    def establish_serial_connection(self, serial_port:str, device_type:str) -> None:
        baudrate:int=57600
        delay_message:float=.1
        if device_type == 'FAM-USB':
            baudrate = 9600
        elif device_type == 'FAM14':
            delay_message = .001

        try:
            if not self.is_serial_connection_active():
                if device_type == 'USB300':
                    self._serial_bus = ESP3SerialCommunicator(serial_port, 
                                                              callback=self._send_serial_event,
                                                              esp2_translation_enabled=True,
                                                              auto_reconnect=False
                                                              )
                else:
                    self._serial_bus = RS485SerialInterfaceV2(serial_port, 
                                                              baud_rate=baudrate, 
                                                              callback=self._send_serial_event, 
                                                              delay_message=delay_message,
                                                              auto_reconnect=False)
                self._serial_bus.start()
                self._serial_bus.is_serial_connected.wait(timeout=10)
                
                if not self._serial_bus.is_active():
                    self._serial_bus.stop()
                
                if self._serial_bus.is_active():
                    self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Serial connection established. serial port: {serial_port}, baudrate: {baudrate}", 'color':'green'})
                    
                    if device_type == 'FAM14':

                        def run():
                            asyncio.run( self._get_fam14_device_on_bus() )
                            self.app_bus.fire_event(
                                AppBusEventType.CONNECTION_STATUS_CHANGE, 
                                {'serial_port':  serial_port, 'baudrate': baudrate, 'connected': self._serial_bus.is_active()})
                            
                        t = threading.Thread(target=run)
                        t.start()
                    else:
                        if device_type == 'FAM-USB': 
                            asyncio.run( self.async_create_fam_usb_device() )
                        elif device_type == 'USB300':
                            asyncio.run( self.async_create_usb300_device() )

                        self.app_bus.fire_event(
                                AppBusEventType.CONNECTION_STATUS_CHANGE, 
                                {'serial_port':  serial_port, 'baudrate': baudrate, 'connected': self._serial_bus.is_active()})
            
        except Exception as e:
            self._serial_bus.stop()
            self.app_bus.fire_event(AppBusEventType.CONNECTION_STATUS_CHANGE, {'serial_port':  serial_port, 'baudrate': baudrate, 'connected': False})
            msg = f"Establish connection for {device_type} on port {serial_port} failed!!!"
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'log-level': 'ERROR', 'color': 'red'})
            logging.exception(msg, exc_info=True)

    async def async_create_usb300_device(self):
        try:
            self._serial_bus.set_callback( None )
            
            self.current_base_id = b2s(self._serial_bus.base_id)

            await self.app_bus.async_fire_event(AppBusEventType.ASYNC_TRANCEIVER_DETECTED, {'type': 'USB300', 
                                                                                            'base_id': self.current_base_id, 
                                                                                            'tcm_version': '', 
                                                                                            'api_version': ''})


        except Exception as e:
            msg = 'Failed to get information about USB300!!!'
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'log-level': 'ERROR', 'color': 'red'})
            logging.exception(msg, exc_info=True)
            raise e
        finally:
            self._serial_bus.set_callback( self._send_serial_event )                    

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

    async def async_create_fam_usb_device(self):
        try:
            self._serial_bus.set_callback( None )
            
            # get base id
            data = b'\xAB\x58\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            response:ESP2Message = await self._serial_bus.exchange(ESP2Message(bytes(data)), ESP2Message)
            base_id = response.body[2:6]
            self.current_base_id = b2s(base_id)

            # get version
            data = b'\xAB\x4B\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            response:ESP2Message = await self._serial_bus.exchange(ESP2Message(bytes(data)), ESP2Message)
            tcm_sw_v = '.'.join(str(n) for n in response.body[2:6])
            api_v = '.'.join(str(n) for n in response.body[6:10])

            await self.app_bus.async_fire_event(AppBusEventType.ASYNC_TRANCEIVER_DETECTED, {'type': 'FAM-USB', 
                                                                                            'base_id': self.current_base_id, 
                                                                                            'tcm_version': tcm_sw_v, 
                                                                                            'api_version': api_v})


        except Exception as e:
            msg = 'Failed to get information about FAM-USB!!!'
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'log-level': 'ERROR', 'color': 'red'})
            logging.exception(msg, exc_info=True)
            raise e
        finally:
            self._serial_bus.set_callback( self._send_serial_event )

    def stop_serial_connection(self) -> None:
        if self.is_serial_connection_active():
            self._serial_bus.stop()
            self._serial_bus._stop_flag.wait()

            time.sleep(0.5)

            self.app_bus.fire_event(AppBusEventType.CONNECTION_STATUS_CHANGE, {'connected': self._serial_bus.is_active()})
            if not self._serial_bus.is_active():
                self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Serial connection stopped.", 'color':'green'})
            self.current_base_id = None
            self._serial_bus = None

    def kill_serial_connection_before_exit(self) -> None:
        if self.is_serial_connection_active():
            self._serial_bus.stop()

    def scan_for_devices(self, force_overwrite:bool=False) -> None:
        # if connected to FAM14
        if self.is_fam14_connection_active():
            
            t = threading.Thread(target=lambda: asyncio.run( self._scan_for_devices_on_bus(force_overwrite) )  )
            t.start()

    async def create_busobject(self, id: int) -> BusObject:
        response = await self._serial_bus.exchange(EltakoDiscoveryRequest(address=id), EltakoDiscoveryReply)

        assert id == response.reported_address, "Queried for ID %s, received %s" % (id, prettify(response))

        for o in sorted_known_objects:
            if response.model.startswith(o.discovery_name) and (o.size is None or o.size == response.reported_size):
                return o(response, bus=self._serial_bus)
        else:
            return BusObject(response, bus=self._serial_bus)

    async def enumerate_bus(self) -> Iterator[BusObject]: # type: ignore
        """Search the bus for devices, yield bus objects for every match"""

        for i in range(1, 256):
            try:
                self.app_bus.fire_event(AppBusEventType.DEVICE_ITERATION_PROGRESS, i/256.0*100.0)
                yield await self.create_busobject(i)
            except TimeoutError:
                continue

    async def _get_fam14_device_on_bus(self, force_overwrite:bool=False) -> None:
        is_locked = False
        try:
            logging.debug(colored("Start scanning for devices", 'red'))

            self._serial_bus.set_callback( None )

            is_locked = (await locking.lock_bus(self._serial_bus)) == locking.LOCKED
            
            # first get fam14 and make it know to data manager
            fam14:FAM14 = await self.create_busobject(255)
            self.current_base_id = await fam14.get_base_id()
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
            self._serial_bus.set_callback( self._send_serial_event )


    async def _scan_for_devices_on_bus(self, force_overwrite:bool=False) -> None:
        is_locked = False
        try:
            self.app_bus.fire_event(AppBusEventType.DEVICE_SCAN_STATUS, 'STARTED')
            
            msg = "Start scanning for devices"
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'color':'red'})

            self._serial_bus.set_callback( None )

            is_locked = (await locking.lock_bus(self._serial_bus)) == locking.LOCKED
            
            # first get fam14 and make it know to data manager
            fam14:FAM14 = await self.create_busobject(255)
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
            self._serial_bus.set_callback( self._send_serial_event )

    def write_sender_id_to_devices(self, sender_base_id:int=45056, sender_id_list:dict={}):
        t = threading.Thread(target=lambda: asyncio.run( self.async_write_sender_id_to_devices(sender_base_id, sender_id_list) )  )
        t.start()


    async def async_ensure_programmed(self, fam14_base_id_int:int, dev:BusObject, sender_id_list:dict):
        HEATING = [FAE14SSR]
        if isinstance(dev, HasProgrammableRPS) or isinstance(dev, DimmerStyle) or type(dev) in HEATING:
            for i in range(0,dev.size):
                device_ext_id_str = b2s( (fam14_base_id_int + dev.address+i).to_bytes(4,'big'))

                if device_ext_id_str in sender_id_list:
                    if 'sender' in sender_id_list[device_ext_id_str]:
                        sender_id_str = sender_id_list[device_ext_id_str]['sender']['id']
                        sender_eep_str = sender_id_list[device_ext_id_str]['sender']['eep']
                        sender_address = AddressExpression.parse(sender_id_str)
                        eep_profile = EEP.find(sender_eep_str)

                        if type(dev) in HEATING:
                            # need to be at a special position 12 and 13
                            continue
                            mem_line:bytes = sender_address[0] + bytes((0, 65, 1, 0))
                            #TODO: NOT PROPERLY WORKING
                            await dev.write_mem_line(12 + i, mem_line)
                        else:
                            await dev.ensure_programmed(i, sender_address, eep_profile)
                
                        msg = f"Updated Home Assistant sender id ({sender_id_str}) in device {type(dev).__name__} ({device_ext_id_str})"
                        self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'color':'grey'})
                        self.app_bus.fire_event(AppBusEventType.WRITE_SENDER_IDS_TO_DEVICES_STATUS, 'DEVICE_UPDATED')


    async def async_write_sender_id_to_devices(self, sender_base_id:int=45056, sender_id_list:dict={}): # 45056 = 0x00 00 B0 00
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
                fam14:FAM14 = await self.create_busobject(255)
                fam14_base_id_int = await fam14.get_base_id_in_int()
                fam14_base_id = b2s(await fam14.get_base_id_in_bytes())
                msg = f"Update devices on Bus (fam14 base id: {fam14_base_id})"
                self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'color':'grey'})

                # iterate through all devices
                async for dev in self.enumerate_bus():
                    try:
                        await self.async_ensure_programmed(fam14_base_id_int, dev, sender_id_list)
                    except TimeoutError:
                        logging.error("Read error, skipping: Device %s announces %d memory but produces timeouts at reading" % (dev, dev.discovery_response.memory_size))

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
                self._serial_bus.set_callback( self._send_serial_event )