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

    TEST_MESSAGES: [EltakoMessage] = []
    TEST_ADDRESSES = [] 

    def __init__(self, app_bus:AppBus, serial_port1: str, device_type1: str, serial_port2: str, device_type2: str, message_delay:float=.01, quiet: bool=True, message_count: int=44) -> None:
        self._stop_flag = threading.Event()
        self._receive_queue = queue.Queue(len(BusBurstTester.TEST_MESSAGES))

        self.serial_port1 = serial_port1
        self.device_type1 = device_type1
        self.serial_port2 = serial_port2
        self.device_type2 = device_type2

        self.quiet = quiet
        self.message_delay = message_delay
        self._received_other_messages_count = 0
        self.message_count = message_count
        
        # generate alternating messages
        adr = b'\x00\x00\xa0\x04'  # Address 00-00-A0-04
        BusBurstTester.TEST_MESSAGES.append( Regular4BSMessage(adr, 0x20, b'\x01\x00\x00\x09', 0x00) )  # data: 01-00-00-09, status: 00
        BusBurstTester.TEST_MESSAGES.append( Regular4BSMessage(adr, 0x20, b'\x01\x00\x00\x08', 0x00) )  # data: 01-00-00-08, status: 00
        BusBurstTester.TEST_ADDRESSES.append( b2s(adr) )

        self.app_bus = app_bus
        self.gw_reg = GatewayRegistry(app_bus)
        self.serial_controller1 = SerialController(app_bus, self.gw_reg)
        self.serial_controller2 = SerialController(app_bus, self.gw_reg)
        app_bus.add_event_handler(AppBusEventType.SERIAL_CALLBACK, self._serial_callback)

        self.serial_controller1.establish_serial_connection(self.serial_port1, self.device_type1, delay_msg = 0, disable_echo_test=True)
        self.serial_controller2.establish_serial_connection(self.serial_port2, self.device_type2, delay_msg = 0, disable_echo_test=True)
        

    def start_test(self, run_count:int=1) -> None:

        # Wait for initialization 
        time.sleep(1)
        
        self.serial_controller1.gateway_id = f"GW1 {self.serial_port1} {self.device_type1}"
        self.serial_controller2.gateway_id = f"GW2 {self.serial_port2} {self.device_type2}"

        self._stop_flag.clear()
        count = 0
        successful_runs = 0
        results = []
        while (not self._stop_flag.is_set()):
            count += 1
            self._received_other_messages_count = 0
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': "", 'log-level': 'INFO', 'color': 'grey'})
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Start BURST TEST RUN No. {count} - {self.message_count} Alternating Messages, delayed by {self.message_delay}s", 'log-level': 'INFO', 'color': 'grey'})
            # prepare queues
            self._receive_queue.empty()

            # Send alternating messages
            for i in range(self.message_count): 
                # Alternate between the two messages
                message_index = i % 2
                current_message = BusBurstTester.TEST_MESSAGES[message_index]
                
                if not self.quiet:
                    self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Send Test Telegram {str(current_message)} from {self.device_type1}", 'log-level': 'INFO', 'color': 'grey'})
                self.serial_controller1.send_message(current_message)
                time.sleep(self.message_delay)

            if not self.quiet:
                self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Wait for messages to be received.", 'log-level': 'INFO', 'color': 'grey'})
            time.sleep(4)

            failed_msg_count = self._check_test()
            if failed_msg_count == 0:
                successful_runs += 1
                self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"=> Test run No. {count} was SUCCESSFUL.", 'log-level': 'INFO', 'color': 'green'})
            else:
                self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"=> Test run No. {count} was NOT SUCCESSFUL.", 'log-level': 'INFO', 'color': 'red'})

            results.append({
                'run': count,
                'msg count': self.message_count,
                'not received': failed_msg_count,
                'rvd other msg count': self._received_other_messages_count,
            })

            if count == run_count:
                self._stop_flag.set()

        self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"===================================================================================", 'log-level': 'INFO', 'color': 'grey'})
        self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"     =>      {successful_runs} of {count} RUNS WERE SUCESSFULL. {self.message_count} Message per run delayed by {self.message_delay}s.", 'log-level': 'INFO', 'color': 'green'})
        self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"===================================================================================", 'log-level': 'INFO', 'color': 'grey'})
        for r in results:
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"     run: {r['run']}, msg sent: {r['msg count']}, msg not received: {r['not received']}, received other msgs: {r['rvd other msg count']}", 'log-level': 'INFO', 'color': 'green'})

        self.serial_controller1.stop_serial_connection()
        self.serial_controller2.stop_serial_connection()

    
    def stop_test(self):
        self._stop_flag.set()


    def _serial_callback(self, data: object) -> None:
        if not self._stop_flag.is_set():
            if 'msg' in data and type(data['msg']) != EltakoPoll:
                if 'gateway_id' in data and data['gateway_id'] == self.serial_controller2.gateway_id:
                    if b2s(data['msg'].body[6:10]) in BusBurstTester.TEST_ADDRESSES:
                        self._receive_queue.put(data['msg'])
                    else:
                        self._received_other_messages_count += 1
                
                if not self.quiet:
                    self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Received Telegram {str(data['msg'])} from {data['gateway_id']}", 'log-level': 'INFO', 'color': 'grey'})
            else: 
                self._received_other_messages_count += 1


    def _check_test(self) -> int:
        received_message_count = 0
        target_address = b'\x00\x00\xa0\x04'  # Our target address 00-00-A0-04
        
        while not self._receive_queue.empty():
            received_msg = self._receive_queue.get()
            # Check if the received message has our target address
            if received_msg.body[-5:-1] == target_address:
                received_message_count += 1

        missing_messages = self.message_count - received_message_count

        if missing_messages > 0:
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Did not receive {missing_messages} messages for address: {b2s(target_address)} (received {received_message_count} of {self.message_count})", 'log-level': 'INFO', 'color': 'red'})

        return missing_messages
