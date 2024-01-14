
from enum import Enum
import sys
import glob
import serial
from serial import rs485

from typing import Iterator

from termcolor import colored
import logging

from eltakobus import *
from eltakobus.locking import buslocked
from eltakobus.message import Regular4BSMessage
import threading

DEFAULT_SENDER_ADDRESS = 0x0000B000


class ControllerEventType(Enum):
    LOG_MESSAGE = 0                     # dict with keys: msg:str, color:str
    SERIAL_CALLBACK = 1                 # EltakoMessage
    CONNECTION_STATUS_CHANGE = 2        # dict with keys: serial_port:str, baudrate:int, connected:bool
    DEVICE_SCAN_PROGRESS = 3            # percentage 0..100 in float
    DEVICE_SCAN_STATUS = 4              # str: STARTED, FINISHED, DEVICE_DETECTED
    ASYNC_DEVICE_DETECTED = 5           # BusObject
    UPDATE_DEVICE_REPRESENTATION = 6    # dict with keys: fam14_base_id:str, device:dict
    UPDATE_SENSOR_REPRESENTATION = 7    # sensor:dict
    WINDOW_CLOSED = 8
    WINDOW_LOADED = 9

class ControllerEvent():
    def __init__(self, event_type:ControllerEventType, data):
        self.event_type = event_type
        self.data = data

class AppController():

    def __init__(self) -> None:
        self._bus = None
        self._serial_mutex = threading.Lock()

        for event_type in ControllerEventType:
            if event_type not in self._controller_event_handlers.keys():
                self._controller_event_handlers[event_type] = []

        self.add_event_handler(ControllerEventType.WINDOW_CLOSED, self.on_window_closed)

    _controller_event_handlers={}
    def add_event_handler(self, event:ControllerEventType, handler) -> None:
        self._controller_event_handlers[event].append(handler)

    def fire_event(self, event:ControllerEventType, data) -> None:
        # print(f"[Controller] Fire event {event}")
        for h in self._controller_event_handlers[event]: h(data)

    async def async_fire_event(self, event:ControllerEventType, data) -> None:
        # print(f"[Controller] Fire async event {event}")
        for h in self._controller_event_handlers[event]: await h(data)

    def on_window_closed(self, data) -> None:
        self.kill_serial_connection_before_exit()

    def get_serial_ports(self, device_type:str) ->[str]:
        if device_type == 'FAM14':
            return self.get_serial_ports_for_fam14()
        elif device_type == 'FGW14-USB':
            return self.get_serial_ports_for_fgw14usb()
        elif device_type == 'FAM-USB':
            return self.get_serial_ports_for_famusb()
        else:
            return []

    def get_serial_ports_for_fam14(self) -> [str]:
        return self._get_serial_ports(baudrate=57600, test_fam14=True)
    
    def get_serial_ports_for_fgw14usb(self) -> [str]:
        return self._get_serial_ports(baudrate=57600, test_fam14=False)
    
    def get_serial_ports_for_famusb(self) -> [str]:
        return self._get_serial_ports(baudrate=9600, test_fam14=False, test_famusb=True)

    def _get_serial_ports(self, baudrate:int=57600, test_fam14:bool=True, test_famusb:bool=False) -> [str]:
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
                    self.fire_event(ControllerEventType.LOG_MESSAGE, {'msg': f"FAM14 detected on serial port {port},(baudrate: {baudrate})", 'color':'lightgreen'})
                elif fam14_test_request == fam14_test_response: 
                    continue

                if test_famusb and famusb_test_response == famusb_expected_response:
                    result.append(port)
                    self.fire_event(ControllerEventType.LOG_MESSAGE, {'msg': f"FAM-USB detected on serial port {port},(baudrate: {baudrate})", 'color':'lightgreen'})
                elif test_famusb:
                    continue
                
                if not test_famusb and not test_fam14 and famusb_test_response == famusb_expected_response:
                    result.append(port)
                    self.fire_event(ControllerEventType.LOG_MESSAGE, {'msg': f"FGW14-USB detected on serial port {port},(baudrate: {baudrate})", 'color':'lightgreen'})

                s.close()

            except (OSError, serial.SerialException) as e:
                pass
        return result
    
    def is_serial_connection_active(self) -> None:
        return self._bus is not None and self._bus.is_active()
    
    def is_fam14_connection_active(self) -> None:
        return self.is_serial_connection_active() and self._bus.suppress_echo

    def _send_serial_event(self, message) -> None:
        self.fire_event(ControllerEventType.SERIAL_CALLBACK, message)

    def establish_serial_connection(self, serial_port:str, device_type:str) -> None:
        baudrate:int=57600
        if device_type == 'FAM-USB':
            baudrate = 9600

        if not self.is_serial_connection_active():
            self._bus = RS485SerialInterfaceV2(serial_port, baud_rate=baudrate, callback=self._send_serial_event)
            self._bus.start()
            self._bus.is_serial_connected.wait(timeout=10)

            if not self._bus.is_active():
                self._bus.stop()
            
            if self._bus.is_active():
                self.fire_event(ControllerEventType.LOG_MESSAGE, {'msg': f"Serial connection established. serial port: {serial_port}, baudrate: {baudrate}", 'color':'green'})
                
                if device_type == 'FAM14':

                    def run():
                        asyncio.run( self._get_fam14_device_on_bus() )
                        self.fire_event(
                            ControllerEventType.CONNECTION_STATUS_CHANGE, 
                            {'serial_port':  serial_port, 'baudrate': baudrate, 'connected': self._bus.is_active()})

                    t = threading.Thread(target=run)
                    t.start()

            

    def stop_serial_connection(self) -> None:
        if self.is_serial_connection_active():
            self._bus.stop()
            self._bus._stop_flag.wait()

            time.sleep(0.5)

            self.fire_event(ControllerEventType.CONNECTION_STATUS_CHANGE, {'connected': self._bus.is_active()})
            if not self._bus.is_active():
                self.fire_event(ControllerEventType.LOG_MESSAGE, {'msg': f"Serial connection stopped.", 'color':'green'})
            self._bus = None

    def kill_serial_connection_before_exit(self) -> None:
        if self.is_serial_connection_active():
            self._bus.stop()

    def scan_for_devices(self) -> None:
        # if connected to FAM14
        if self.is_fam14_connection_active():
            
            t = threading.Thread(target=lambda: asyncio.run( self._scan_for_devices_on_bus()) )
            t.start()

    async def create_busobject(self, id: int) -> BusObject:
        response = await self._bus.exchange(EltakoDiscoveryRequest(address=id), EltakoDiscoveryReply)

        assert id == response.reported_address, "Queried for ID %s, received %s" % (id, prettify(response))

        for o in sorted_known_objects:
            if response.model.startswith(o.discovery_name) and (o.size is None or o.size == response.reported_size):
                return o(response, bus=self._bus)
        else:
            return BusObject(response, bus=self._bus)

    async def enumerate_bus(self) -> Iterator[BusObject]:
        """Search the bus for devices, yield bus objects for every match"""

        for i in range(1, 256):
            try:
                self.fire_event(ControllerEventType.DEVICE_SCAN_PROGRESS, i/256.0*100.0)
                yield await self.create_busobject(i)
            except TimeoutError:
                continue

    async def _get_fam14_device_on_bus(self) -> None:
        try:
            self._bus.set_callback( None )

            await locking.lock_bus(self._bus)
                
            logging.info(colored("Start scanning for devices", 'red'))
            self.fire_event(ControllerEventType.LOG_MESSAGE, {'msg': "Get FAM14 information", 'color':'red'})

            # first get fam14 and make it know to data manager
            fam14 = await self.create_busobject(255)
            logging.info(colored(f"Found device: {fam14}",'grey'))
            await self.async_fire_event(ControllerEventType.ASYNC_DEVICE_DETECTED, {'device': fam14, 'fam14': fam14})

        except Exception as e:
            raise e
        finally:
            await locking.unlock_bus(self._bus)

            self.fire_event(ControllerEventType.DEVICE_SCAN_STATUS, 'FINISHED')
            self._bus.set_callback( self._send_serial_event )


    async def _scan_for_devices_on_bus(self) -> None:
        try:
            self.fire_event(ControllerEventType.DEVICE_SCAN_STATUS, 'STARTED')
            self._bus.set_callback( None )

            # print("Sending a lock command onto the bus; its reply should tell us whether there's a FAM in the game.")
            time.sleep(0.2)
            await locking.lock_bus(self._bus)
                
            logging.info(colored("Start scanning for devices", 'red'))
            self.fire_event(ControllerEventType.LOG_MESSAGE, {'msg': "Start scanning for devices", 'color':'red'})

            # first get fam14 and make it know to data manager
            fam14 = await self.create_busobject(255)
            logging.info(colored(f"Found device: {fam14}",'grey'))
            await self.async_fire_event(ControllerEventType.ASYNC_DEVICE_DETECTED, {'device': fam14, 'fam14': fam14})

            # iterate through all devices
            async for dev in self.enumerate_bus():
                try:
                    logging.info(colored(f"Found device: {dev}",'grey'))
                    self.fire_event(ControllerEventType.LOG_MESSAGE, {'msg': f"Found device: {dev}", 'color':'grey'})
                    self.fire_event(ControllerEventType.DEVICE_SCAN_STATUS, 'DEVICE_DETECTED')
                    await self.async_fire_event(ControllerEventType.ASYNC_DEVICE_DETECTED, {'device': dev, 'fam14': fam14})

                except TimeoutError:
                    logging.error("Read error, skipping: Device %s announces %d memory but produces timeouts at reading" % (dev, dev.discovery_response.memory_size))
            logging.info(colored("Device scan finished.", 'red'))
            self.fire_event(ControllerEventType.LOG_MESSAGE, {'msg': "Device scan finished.", 'color':'red'})
        except Exception as e:
            raise e
        finally:
            # print("Unlocking the bus again")
            await locking.unlock_bus(self._bus)

            self.fire_event(ControllerEventType.DEVICE_SCAN_STATUS, 'FINISHED')
            self._bus.set_callback( self._send_serial_event )
