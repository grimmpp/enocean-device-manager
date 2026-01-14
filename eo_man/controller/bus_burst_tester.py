import threading
import queue
import time
import asyncio

from .app_bus import AppBus, AppBusEventType
from .gateway_registry import GatewayRegistry
from .serial_controller import SerialController

from eltakobus.message import EltakoMessage, Regular4BSMessage, EltakoPoll, prettify
from eltakobus.util import b2s

class BusBurstTester:

    TEST_MESSAGES: [EltakoMessage] = [
        Regular4BSMessage(b'\xFF\x00\x00\x01', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x02', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x03', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x04', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x05', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x06', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x07', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x08', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x09', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x0A', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x0B', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x0C', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x0D', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x0E', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x0F', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x10', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x11', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x12', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x13', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x14', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x15', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x16', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x17', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x18', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x19', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x1A', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x1B', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x1C', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x1D', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x1E', 0x20, b'\00\x00\x00\x00', True),
        Regular4BSMessage(b'\xFF\x00\x00\x1F', 0x20, b'\00\x00\x00\x00', True),
    ]

    def __init__(self, app_bus:AppBus, serial_port1: str, device_type1: str, serial_port2: str, device_type2: str, message_delay:float=.1) -> None:
        self._stop_flag = threading.Event()
        self._receive_queue = queue.Queue(len(BusBurstTester.TEST_MESSAGES))

        self.serial_port1 = serial_port1
        self.device_type1 = device_type1
        self.serial_port2 = serial_port2
        self.device_type2 = device_type2

        self.message_delay = message_delay

        self.app_bus = app_bus
        self.gw_reg = GatewayRegistry(app_bus)
        self.serial_controller1 = SerialController(app_bus, self.gw_reg)
        self.serial_controller2 = SerialController(app_bus, self.gw_reg)
        app_bus.add_event_handler(AppBusEventType.SERIAL_CALLBACK, self._serial_callback)

        self.serial_controller1.establish_serial_connection(self.serial_port1, self.device_type1)
        self.serial_controller2.establish_serial_connection(self.serial_port2, self.device_type2)
        

    def start_test(self, run_count:int=1) -> None:
        
        self.serial_controller1.gateway_id = f"GW1 {self.serial_port1} {self.device_type1}"
        self.serial_controller2.gateway_id = f"GW2 {self.serial_port2} {self.device_type2}"

        self._stop_flag.clear()
        count = 0
        while (not self._stop_flag.is_set()):
            count += 1
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': "", 'log-level': 'INFO', 'color': 'grey'})
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Start BURST TEST RUN No. {count} - {len(BusBurstTester.TEST_MESSAGES)} Messages, delayed by {self.message_delay}s", 'log-level': 'INFO', 'color': 'grey'})
            # prepare queues
            self._receive_queue.empty()

            for m in BusBurstTester.TEST_MESSAGES: 
                self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Send Test Telegram {str(m)}", 'log-level': 'INFO', 'color': 'grey'})
                self.serial_controller1.send_message(m)
                time.sleep(self.message_delay)

            if self._check_test():
                self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"=> Test run No. {count} was SUCCESSFUL.", 'log-level': 'INFO', 'color': 'green'})
            else:
                self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"=> Test run No. {count} was NOT SUCCESSFUL.", 'log-level': 'INFO', 'color': 'red'})

            if count == run_count:
                self._stop_flag.set()

        self.serial_controller1.stop_serial_connection()
        self.serial_controller2.stop_serial_connection()
    
    def stop_test(self):
        self._stop_flag.set()

    def _serial_callback(self, data: object) -> None:
        if 'msg' in data and type(data['msg']) != EltakoPoll:
            if 'gateway_id' in data and data['gateway_id'] == self.serial_controller2.gateway_id:
                self._receive_queue.put(data['msg'])
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Received Telegram {str(data['msg'])} from {data['gateway_id']}", 'log-level': 'INFO', 'color': 'grey'})

    def _check_test(self) -> bool:
        missing_addresses = []
        received_addresses = []
        while not self._receive_queue.empty():
            received_addresses.append(prettify(self._receive_queue.get()).body[6:10])

        for a in [m.address for m in BusBurstTester.TEST_MESSAGES]: 
            if a not in received_addresses:
                missing_addresses.append(a)

        if len(missing_addresses) > 0:
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Did not receive messages for addresses: {str.join(', ', [b2s(a) for a in missing_addresses])}", 'log-level': 'INFO', 'color': 'red'})

        return len(missing_addresses) == 0
