import serial
from serial import rs485
import serial.tools.list_ports
import logging
import sys
import time

from esp2_gateway_adapter.esp3_serial_com import ESP3SerialCommunicator
from esp2_gateway_adapter.esp3_tcp_com import TCP2SerialCommunicator, detect_lan_gateways
from esp2_gateway_adapter.esp2_tcp_com import ESP2TCP2SerialCommunicator

from eltakobus.serial import RS485SerialInterfaceV2
from eltakobus.message import ESP2Message
from eltakobus.util import b2s

from .app_bus import AppBusEventType, AppBus
from ..data.data_helper import GatewayDeviceType
from ..data.const import GatewayDeviceType as GDT, GATEWAY_DISPLAY_NAMES as GDN

class SerialPortDetector:

    ## not used only for documentation
    # DATA = [
    #     {'USB VID': 'PID=0403:6001', 'Manufacturer': 'FTDI', 'Device_Type': GatewayDeviceType.EltakoFAM14},
    #     {'USB VID': 'PID=0403:6010', 'Manufacturer': 'FTDI', 'Device_Type': GatewayDeviceType.GatewayEltakoFGW14USB},
    #     {'USB VID': 'PID=0403:6001', 'Manufacturer': 'FTDI', 'Device_Type': GatewayDeviceType.USB300},
    # ]

    def __init__(self, app_bus: AppBus):
        self.app_bus = app_bus

    @classmethod
    def print_device_info(cls):
        ports = serial.tools.list_ports.comports()

        for port in ports:
            logging.getLogger().info(f"Port: {port.device}")
            logging.getLogger().info(f"Description: {port.description}")
            logging.getLogger().info(f"HWID: {port.hwid}") 
            logging.getLogger().info(f"Manufacturer: {port.manufacturer}") 
            logging.getLogger().info(f"Interface: {port.interface}") 
            logging.getLogger().info(f"Location: {port.location}") 
            logging.getLogger().info(f"Name: {port.name}") 
            logging.getLogger().info(f"PID: {port.pid}") 
            logging.getLogger().info(f"Product: {port.product}") 
            logging.getLogger().info(f"Serial Number: {port.serial_number}") 
            

            ser = serial.Serial(port.device)
            logging.getLogger().info(f"Baud rate: {ser.baudrate}")
            ser.close()

            logging.getLogger().info("\n")


    # A port which is no gateway at all cannot be distinguished from a gateway
    # which does not answer, so every test costs its full timeout. The detection
    # runs over every serial port of the system, therefore the number of retries
    # is kept low - a gateway which is there answers on the first attempt.
    FAM_USB_BASE_ID_RETRIES = 1
    # this command really requires sometimes 1sec!
    FAM_USB_BASE_ID_TIMEOUT = 1.0
    # time granted to a communicator to open the serial port
    CONNECT_TIMEOUT = 1.0

    async def async_get_gateway2serial_port_mapping(self, callback=None) -> dict[str:list[str]]:
        """Probes every serial port of the system for a supported gateway.

        callback is called with the intermediate result every time a gateway was
        found, so that it can be used before the whole detection has finished."""

        self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Start detecting serial ports", 'color':'grey'})

        fam14 = GDT.EltakoFAM14.value
        esp3_gw = GDT.ESP3.value
        famusb = GDT.EltakoFAMUSB.value
        fgw14usb = GDT.EltakoFGW14USB.value
        result = { fam14: [], esp3_gw: [], famusb: [], fgw14usb: [], 'all': [] }

        if sys.platform.startswith('win') or sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
            # ports = ['COM%s' % (i + 1) for i in range(256)]
            # pyserial's list_ports works on Windows, Linux and macOS (returns /dev/cu.* devices)
            port_infos = serial.tools.list_ports.comports()
        else:
            raise NotImplementedError(f"Detection of devices under {sys.platform} is not yet supported!")

        ports = [d.device for d in port_infos]
        # A FAM-USB is a USB stick, so it cannot be behind a port without a USB
        # vendor id (built-in serial ports, bluetooth, /dev/ttyAMA0, ...). Skipping
        # its test there saves a full timeout per port. FAM14 and FGW14 are also
        # reachable via such ports, their tests run for every port.
        usb_ports = {d.device for d in port_infos if d.vid is not None}
        self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Check ports {ports} for gateways", 'color':'grey'})

        # 9600 baud has to be checked first, see _async_detect_gateway
        steps = max(len(ports) * 2, 1)
        step = 0
        for baud_rate in [9600, 57600]:
            for port in ports:
                step += 1
                self.app_bus.fire_event(AppBusEventType.DEVICE_ITERATION_PROGRESS,
                                        min(step / steps * 100.0, 100.0))

                if port in result['all']:
                    continue

                gateway_type = await self._async_detect_gateway(port, baud_rate,
                                                               is_usb_port=port in usb_ports)
                if gateway_type is None:
                    continue

                result[gateway_type].append(port)
                result['all'].append(port)
                self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE,
                                        {'msg': self._detection_message(gateway_type, port, baud_rate),
                                         'color': 'lightgreen'})
                if callback is not None:
                    callback(result)

        self.app_bus.fire_event(AppBusEventType.DEVICE_ITERATION_PROGRESS, 0)
        return result


    def _detection_message(self, gateway_type:str, port:str, baud_rate:int) -> str:
        if gateway_type == GDT.EltakoFGW14USB.value:
            # the test matches every port which is reachable and does not echo
            return f"FGW14(-USB) could be on serial port {port}, (baudrate: {baud_rate})"
        name = {GDT.EltakoFAM14.value: 'FAM14', GDT.ESP3.value: 'USB300',
                GDT.EltakoFAMUSB.value: 'FAM-USB'}.get(gateway_type, gateway_type)
        return f"{name} detected on serial port {port}, (baudrate: {baud_rate})"


    async def _async_detect_gateway(self, port:str, baud_rate:int, is_usb_port:bool=True) -> str:
        """Probes one serial port with one baud rate and returns the type of the
        detected gateway or None.

        The order of the tests must not be changed:
        * Only the adapter of a FAM14 echoes back what is written to it, that is
          the cheapest test and it works with both baud rates.
        * A FAM-USB only works with 9600 baud and has to be tested before the
          FGW14, because the FGW14 test matches every port which does not echo.
        """
        communicator = None
        try:
            # is faster to precheck with serial
            s = serial.Serial(port, baudrate=baud_rate, timeout=0.2)
            # not working under linux
            # s.rs485_mode = serial.rs485.RS485Settings()
            s.close()

            # test esp3 devices (USB300, USB500)
            if baud_rate == 57600:
                communicator = ESP3SerialCommunicator(port, auto_reconnect=False)
                self._start(communicator)
                if communicator.is_serial_connected.wait(self.CONNECT_TIMEOUT):
                    base_id = await communicator.async_base_id
                    if base_id and isinstance(base_id, list):
                        return GDT.ESP3.value
                # no esp3 gateway - the port can still be a fam14 or a fgw14
                self._stop(communicator)
                communicator = None

            # test fam14, fam-usb and fgw14-usb
            communicator = RS485SerialInterfaceV2(port, baud_rate=baud_rate, delay_message=0.2,
                                                 auto_reconnect=False)
            self._start(communicator)
            if not communicator.is_serial_connected.wait(self.CONNECT_TIMEOUT):
                return None

            # test fam14
            if communicator.suppress_echo:
                return GDT.EltakoFAM14.value

            # test fam-usb: it answers with its base id
            if baud_rate == 9600:
                if not is_usb_port:
                    logging.debug("Port %s has no USB vendor id, skipping the FAM-USB test.", port)
                else:
                    base_id = await self.async_get_base_id_for_fam_usb(communicator, None)
                    if base_id is not None and base_id != '00-00-00-00':
                        return GDT.EltakoFAMUSB.value

            # fgw14-usb: reachable with 57600 baud and no echo
            if baud_rate == 57600:
                return GDT.EltakoFGW14USB.value

            return None

        except Exception as e:
            logging.debug("Port %s is no gateway with %d baud: %s", port, baud_rate, e)
            return None
        finally:
            self._stop(communicator)


    def _start(self, communicator) -> None:
        """RS485SerialInterfaceV2 is no daemon thread. A port which blocks while
        being probed must not keep the application alive after it was closed."""
        communicator.daemon = True
        communicator.start()


    def _stop(self, communicator) -> None:
        """Closes a communicator, no matter whether it managed to connect."""
        if communicator is None:
            return
        try:
            communicator.stop()
            communicator.join(.5)
        except Exception as e:
            logging.debug("Could not stop communicator: %s", e)


    async def async_get_base_id_for_fam_usb(self, fam_usb:RS485SerialInterfaceV2, callback) -> str:
        base_id:str = None
        try:
            fam_usb.set_callback( None )

            # get base id
            data = b'\xAB\x58\x00\x00\x00\x00\x00\x00\x00\x00\x00'
            response:ESP2Message = await fam_usb.exchange(ESP2Message(bytes(data)), ESP2Message,
                                                          retries=self.FAM_USB_BASE_ID_RETRIES,
                                                          timeout=self.FAM_USB_BASE_ID_TIMEOUT)
            base_id = b2s(response.body[2:6])
        except:
            pass
        finally:
            fam_usb.set_callback( callback )

        return base_id