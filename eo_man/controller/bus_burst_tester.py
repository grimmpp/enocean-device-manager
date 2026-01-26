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
        
        # generate messages
        for n in range(1, message_count+1):
            adr = (int("0xFF000000", 16) + n).to_bytes(4, byteorder='big')
            BusBurstTester.TEST_MESSAGES.append( Regular4BSMessage(adr, 0x20, b'\00\x00\x00\x00', True) )
            BusBurstTester.TEST_ADDRESSES.append( b2s(adr) )

        self.app_bus = app_bus
        self.gw_reg = GatewayRegistry(app_bus)
        self.serial_controller1 = SerialController(app_bus, self.gw_reg)
        self.serial_controller2 = SerialController(app_bus, self.gw_reg)
        app_bus.add_event_handler(AppBusEventType.SERIAL_CALLBACK, self._serial_callback)

        self.serial_controller1.establish_serial_connection(self.serial_port1, self.device_type1)
        self.serial_controller2.establish_serial_connection(self.serial_port2, self.device_type2)
        

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
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Start BURST TEST RUN No. {count} - {len(BusBurstTester.TEST_MESSAGES)} Messages, delayed by {self.message_delay}s", 'log-level': 'INFO', 'color': 'grey'})
            # prepare queues
            self._receive_queue.empty()

            for m in BusBurstTester.TEST_MESSAGES: 
                if not self.quiet:
                    self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Send Test Telegram {str(m)} from {self.device_type1}", 'log-level': 'INFO', 'color': 'grey'})
                self.serial_controller1.send_message(m)
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
                'msg count': len(BusBurstTester.TEST_MESSAGES),
                'not received': failed_msg_count,
                'rvd other msg count': self._received_other_messages_count,
            })

            if count == run_count:
                self._stop_flag.set()

        self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"===================================================================================", 'log-level': 'INFO', 'color': 'grey'})
        self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"     =>      {successful_runs} of {count} RUNS WERE SUCESSFULL. {len(BusBurstTester.TEST_MESSAGES)} Message per run delayed by {self.message_delay}s.", 'log-level': 'INFO', 'color': 'green'})
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
        missing_addresses = []
        received_addresses = []
        while not self._receive_queue.empty():
            received_addresses.append( self._receive_queue.get().body[-5:-1] )

        for a in [m.address for m in BusBurstTester.TEST_MESSAGES]: 
            if a not in received_addresses:
                missing_addresses.append(a)

        if len(missing_addresses) > 0:
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Did not receive {len(missing_addresses)} messages for addresses: {str.join(', ', [b2s(a) for a in missing_addresses])}", 'log-level': 'INFO', 'color': 'red'})

        return len(missing_addresses)
