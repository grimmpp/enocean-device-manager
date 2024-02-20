# -*- encoding: utf-8 -*-
from __future__ import print_function, unicode_literals, division, absolute_import
import asyncio
import datetime
import logging
import serial
import time
import threading

import queue

from enocean.communicators.communicator import Communicator
from enocean.protocol.packet import Packet, RadioPacket, RORG, PACKET, UTETeachInPacket
from enocean.protocol.constants import PACKET, PARSE_RESULT, RETURN_CODE

from eltakobus.message import ESP2Message, RPSMessage, Regular1BSMessage,  Regular4BSMessage, prettify
from eltakobus.util import b2s

class ESP3SerialCommunicator(Communicator):
    ''' Serial port communicator class for EnOcean radio '''

    def __init__(self, filename, log=None, callback=None, baud_rate=57600, reconnection_timeout:float=10, esp2_translation_enabled:bool=False):
        self.esp2_translation_enabled = esp2_translation_enabled
        self._outside_callback = callback
        super(ESP3SerialCommunicator, self).__init__(self.__callback_wrapper)
        
        self._filename = filename
        self.log = log or logging.getLogger('enocean.communicators.SerialCommunicator')

        self._baud_rate = baud_rate
        self.__recon_time = reconnection_timeout
        self.is_serial_connected = threading.Event()
        self.status_changed_handler = None
        self.__ser = None

    def set_callback(self, callback):
        self._outside_callback = callback

    def is_active(self) -> bool:
        return not self._stop_flag.is_set() and self.is_serial_connected.is_set()     

    def set_status_changed_handler(self, handler) -> None:
        self.status_changed_handler = handler
        self._fire_status_change_handler(self.is_active())

    def _fire_status_change_handler(self, connected:bool) -> None:
        try:
            if self.status_changed_handler:
                self.status_changed_handler(connected)
        except Exception as e:
            pass

    @classmethod
    def convert_esp2_to_esp3_message(cls, message: ESP2Message) -> RadioPacket:
    
        d = message.data[0]

        if isinstance(message, RPSMessage):
            org = RORG.RPS
            org_func = 0x02
            org_type = 0x02
        elif isinstance(message, Regular1BSMessage):
            org = RORG.BS1
            org_func = 0x02
            org_type = 0x02
        elif isinstance(message, Regular4BSMessage):
            org = RORG.BS4
            org_func = 0x01
            org_type = 0x01
            d = message.data
        else:
            return None
        
        # command = [0xA5, 0x02, bval, 0x01, 0x09]
        # command.extend(self._sender_id)
        # command.extend([0x00])
        # self.send_command(data=command, optional=[], packet_type=0x01)

        # data = bytes([org, 0x02, 0x01, 0x01, 0x09]) + d + message.address + bytes([message.status])

# RadioPacket.create(rorg=RORG.BS4, rorg_func=0x20, rorg_type=0x01,
#                               sender=transmitter_id,
#                               CV=50,
#                               TMP=21.5,
#                               ES='true')
        sender = [x for x in message.address]

        # packet = Packet(packet_type=0x01, data=data, optional=[])
        packet = RadioPacket.create(rorg=org, 
                                rorg_func=org_func, 
                                rorg_type=org_type,
                                sender=sender,
                                command=[0x01, 0x00, 0x00, 0x09]
                                )
        return packet

    @classmethod
    def convert_esp3_to_esp2_message(cls, packet: RadioPacket) -> ESP2Message:
        
        if packet.rorg == RORG.RPS:
            org = 0x05
        elif packet.rorg == RORG.BS1:
            org = 0x06
        elif packet.rorg == RORG.BS4:
            org = 0x07
        else:
            return None

        if org == 0x07:
            body:bytes = bytes([0x0b, org] + packet.data[1:])
        else:
            # data = ['0xf6', '0x50', '0xff', '0xa2', '0x24', '0x1', '0x30']
            body:bytes = bytes([0x0b, org] + packet.data[1:2] + [0,0,0] + packet.data[2:])

        return prettify( ESP2Message(body) )
    

    def __callback_wrapper(self, msg):
        if self._outside_callback:
            if self.esp2_translation_enabled:
                esp2_msg = ESP3SerialCommunicator.convert_esp3_to_esp2_message(msg)
                
                if esp2_msg is None:
                    self.log.warn("[ESP3SerialCommunicator] Cannot convert to esp2 message (%s).", msg)
                else:
                    self._outside_callback(esp2_msg)

            else:
                self._outside_callback(msg)

    def reconnect(self):
        self._stop_flag.set()
        self._stop_flag.wait()
        self.start()

    async def send(self, packet) -> bool:
        if self.esp2_translation_enabled:
            esp3_msg = ESP3SerialCommunicator.convert_esp2_to_esp3_message(packet)
            if esp3_msg is None:
                self.log.warn("[ESP3SerialCommunicator] Cannot convert to esp3 message (%s).", packet)
            else:
                return super().send(esp3_msg)
        else:
            return super().send(packet)

    def run(self):
        self.logger.info('SerialCommunicator started')
        self._fire_status_change_handler(connected=False)
        while not self._stop_flag.is_set():
            try:
                # Initialize serial port
                if self.__ser is None:
                    self.__ser = serial.Serial(self._filename, self._baud_rate, timeout=0.1)
                    self.log.info("Established serial connection to %s - baudrate: %d", self._filename, self._baud_rate)
                    self.is_serial_connected.set()
                    self._fire_status_change_handler(connected=True)

                # If there's messages in transmit queue
                # send them
                while True:
                    packet = self._get_from_send_queue()
                    if not packet:
                        break
                    self.log.debug("send msg: %s", packet)
                    self.__ser.write(bytearray(packet.build()))

                # Read chars from serial port as hex numbers
                self._buffer.extend(bytearray(self.__ser.read(16)))
                self.parse()
                time.sleep(0)

            except (serial.SerialException, IOError) as e:
                self._fire_status_change_handler(connected=False)
                self.is_serial_connected.clear()
                self.log.error(e)
                self.__ser = None
                self.log.info("Serial communication crashed. Wait %s seconds for reconnection.", self.__recon_time)
                time.sleep(self.__recon_time)

        self.__ser.close()
        self._fire_status_change_handler(connected=False)
        self.logger.info('SerialCommunicator stopped')

    def parse(self):
        ''' Parses messages and puts them to receive queue '''
        # Loop while we get new messages
        while True:
            status, self._buffer, packet = Packet.parse_msg(self._buffer)
            # If message is incomplete -> break the loop
            if status == PARSE_RESULT.INCOMPLETE:
                return status

            # If message is OK, add it to receive queue or send to the callback method
            if status == PARSE_RESULT.OK and packet:
                packet.received = datetime.datetime.now()

                if isinstance(packet, UTETeachInPacket) and self.teach_in:
                    response_packet = packet.create_response_packet(self.base_id)
                    self.logger.info('Sending response to UTE teach-in.')
                    self.send(response_packet)

                if self._outside_callback is None:
                    self.receive.put(packet)
                else:
                    self.__callback_wrapper(packet)
                self.logger.debug(packet)

    @property
    def base_id(self):
        ''' Fetches Base ID from the transmitter, if required. Otherwise returns the currently set Base ID. '''
        # If base id is already set, return it.
        if self._base_id is not None:
            return self._base_id

        # Send COMMON_COMMAND 0x08, CO_RD_IDBASE request to the module
        super().send(Packet(PACKET.COMMON_COMMAND, data=[0x08]))
        # Loop over 10 times, to make sure we catch the response.
        # Thanks to timeout, shouldn't take more than a second.
        # Unfortunately, all other messages received during this time are ignored.
        for i in range(0, 10):
            try:
                packet = self.receive.get(block=True, timeout=0.2)
                # We're only interested in responses to the request in question.
                if packet.packet_type == PACKET.RESPONSE and packet.response == RETURN_CODE.OK and len(packet.response_data) == 4:  # noqa: E501
                    # Base ID is set in the response data.
                    self._base_id = packet.response_data
                    # Put packet back to the Queue, so the user can also react to it if required...
                    self.receive.put(packet)
                    break
                # Put other packets back to the Queue.
                self.receive.put(packet)
            except queue.Empty:
                continue
        # Return the current Base ID (might be None).
        return self._base_id

if __name__ == '__main__':

    def cb(package:Packet):
        print("Callback Base id: " + b2s(package.data[1:]))
        print(package)

    # com = ESP3SerialCommunicator("COM12", callback=cb)
    # com.start()
    # com.is_serial_connected.wait(timeout=10)
    # asyncio.run( com.send(Packet(PACKET.COMMON_COMMAND, data=[0x08])) )
    

    com = ESP3SerialCommunicator("COM12", callback=cb)
    com.start()
    com.is_serial_connected.wait(timeout=10)
    com.set_callback(None)

    if com.base_id:
        print("base_id: "+ b2s(com.base_id) +"\n\n")

    com.set_callback(cb)
    com.base_id
    
    print("\n\n")
    time.sleep(2)

    data = [0xf6, 0x50, 0xff, 0xa2, 0x24, 0x1, 0x30]
    body:bytes = bytes([0x0b, 0x05] + data[1:2] + [0,0,0] + data[2:])
    msg =  prettify( ESP2Message(body) )
    print( msg )

    # command = [0xA5, 0x02, 0x01, 0x01, 0x09] # data
    # command.extend([0xFF, 0xD6, 0x30, 0x01]) # address
    # command.extend([0x00])  #status
    # packet = RadioPacket(0x01, command, [])
    # print(packet)

    packet = RadioPacket.create(rorg=RORG.RPS, 
                                rorg_func=0x02, 
                                rorg_type=0x02,
                                sender=[0xFF,0xD6,0x30,0x01],
                                command=[0x01, 0x00, 0x00, 0x09]
                                )
    print(packet)

    packet = ESP3SerialCommunicator.convert_esp2_to_esp3_message(msg)
    print(packet)