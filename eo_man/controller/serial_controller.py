
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
from eltakobus.locking import buslocked, UNLOCKED
from eltakobus.message import Regular4BSMessage

from .app_bus import AppBusEventType, AppBus


class SerialController():

    def __init__(self, app_bus:AppBus) -> None:
        self.app_bus = app_bus
        self._serial_bus = None
        self.current_base_id = None

        self.app_bus.add_event_handler(AppBusEventType.WINDOW_CLOSED, self.on_window_closed)
    

    def on_window_closed(self, data) -> None:
        self.kill_serial_connection_before_exit()

    def get_serial_ports(self, device_type:str) ->list[str]:
        if device_type == 'FAM14':
            return self.get_serial_ports_for_fam14()
        elif device_type == 'FGW14-USB':
            return self.get_serial_ports_for_fgw14usb()
        elif device_type == 'FAM-USB':
            return self.get_serial_ports_for_famusb()
        else:
            return []

    def get_serial_ports_for_fam14(self) -> list[str]:
        return self._get_serial_ports(baudrate=57600, test_fam14=True)
    
    def get_serial_ports_for_fgw14usb(self) -> list[str]:
        return self._get_serial_ports(baudrate=57600, test_fam14=False)
    
    def get_serial_ports_for_famusb(self) -> list[str]:
        return self._get_serial_ports(baudrate=9600, test_fam14=False, test_famusb=True)

    def _get_serial_ports(self, baudrate:int=57600, test_fam14:bool=True, test_famusb:bool=False) -> list[str]:
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

        result = []
        for port in ports:
            try:
                s = serial.Serial(port, baudrate=baudrate, timeout=0.2)
                s.rs485_mode = serial.rs485.RS485Settings()

                # test fam14
                fam14_test_request = b'\xff\x00\xff' * 5
                s.write(fam14_test_request)
                fam14_test_response = s.read_until(fam14_test_request)

                # test fam-usb and fgw14-usb
                famusb_test_request = ESP2Message(b'\xAB\x58\x00\x00\x00\x00\x00\x00\x00\x00\x00').serialize()
                famusb_expected_response = b'\xa5Z\x8b\x98'
                s.write(famusb_test_request)
                famusb_test_response = s.read_until(famusb_expected_response)
                
                if test_fam14 and fam14_test_request == fam14_test_response: 
                    result.append(port)
                    self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"FAM14 detected on serial port {port},(baudrate: {baudrate})", 'color':'lightgreen'})
                elif fam14_test_request == fam14_test_response: 
                    continue

                if test_famusb and famusb_test_response == famusb_expected_response:
                    result.append(port)
                    self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"FAM-USB detected on serial port {port},(baudrate: {baudrate})", 'color':'lightgreen'})
                elif test_famusb:
                    continue
                
                if not test_famusb and not test_fam14 and famusb_test_response == famusb_expected_response:
                    result.append(port)
                    self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"FGW14-USB detected on serial port {port},(baudrate: {baudrate})", 'color':'lightgreen'})

                s.close()

            except (OSError, serial.SerialException) as e:
                pass
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

        if not self.is_serial_connection_active():
            self._serial_bus = RS485SerialInterfaceV2(serial_port, baud_rate=baudrate, callback=self._send_serial_event, delay_message=delay_message)
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
                    self.app_bus.fire_event(
                            AppBusEventType.CONNECTION_STATUS_CHANGE, 
                            {'serial_port':  serial_port, 'baudrate': baudrate, 'connected': self._serial_bus.is_active()})
                        

            

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