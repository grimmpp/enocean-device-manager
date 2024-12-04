import serial
from serial import rs485
import serial.tools.list_ports
import logging
import sys

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


    async def async_get_gateway2serial_port_mapping(self) -> dict[str:list[str]]:

        self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Start detecting serial ports", 'color':'grey'})

        if sys.platform.startswith('win'):
            # ports = ['COM%s' % (i + 1) for i in range(256)]
            ports = [d.device for d in serial.tools.list_ports.comports()]
        else:
            raise NotImplementedError("Detection of devices under other systems than windows is not yet supported!")
        
        # ports = [p.device for p in _ports if p.vid == self.USB_VENDOR_ID]

        fam14 = GDT.EltakoFAM14.value
        esp3_gw = GDT.ESP3.value
        famusb = GDT.EltakoFAMUSB.value
        fgw14usb = GDT.EltakoFGW14USB.value
        result = { fam14: [], esp3_gw: [], famusb: [], fgw14usb: [], 'all': [] }

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

                    # test esp3 devices
                    if baud_rate == 57600:
                        s = ESP3SerialCommunicator(port, auto_reconnect=False)
                        s.start()
                        if not s.is_serial_connected.wait(1):
                            break

                        base_id = await s.async_base_id
                        if base_id and isinstance(base_id, list) and port not in result['all']:
                            result[esp3_gw].append(port)
                            result['all'].append(port)
                            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"USB300 detected on serial port {port},(baudrate: {baud_rate})", 'color':'lightgreen'})
                            s.stop()
                            continue

                        s.stop()
                    
                    # test fam14, fgw14-usb and fam-usb
                    s = RS485SerialInterfaceV2(port, baud_rate=baud_rate, delay_message=0.2, auto_reconnect=False)
                    s.start()
                    if not s.is_serial_connected.wait(1):
                        break

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
                        base_id = await self.async_get_base_id_for_fam_usb(s, None)
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

                except Exception as e:
                    pass

        self.app_bus.fire_event(AppBusEventType.DEVICE_ITERATION_PROGRESS, 0)
        return result


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