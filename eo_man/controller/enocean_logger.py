from datetime import datetime

from eltakobus.message import EltakoPoll, EltakoDiscoveryReply, EltakoDiscoveryRequest, EltakoMessage, prettify, Regular1BSMessage, EltakoWrapped1BS
from esp2_gateway_adapter.esp3_serial_com import ESP3SerialCommunicator

from eo_man import LOGGER

from .app_bus import AppBus
from ..data.data_manager import DataManager
from ..data.data_helper import b2s, a2s
from ..data.device import Device

class EnOceanLogger():

    def __init__(self, app_bus:AppBus, data_manager:DataManager):
        self.app_bus = app_bus
        self.data_manager = data_manager

        self.show_telegram_values = False
        self.show_esp2_binary = False
        self.show_esp3_binary = False

        self.id_filter = []

        self.process_log_message = None

    def set_show_telegram_values(self, value: bool):
        self.show_telegram_values = value

    def set_show_esp2_binary(self, value: bool):
        self.show_esp2_binary = value

    def set_show_esp3_binary(self, value: bool):
        self.show_esp3_binary = value

    def set_process_log_message(self, rev):
        self.process_log_message = rev

    def set_id_filter(self, filter: dict):
        self.id_filter = filter

    def serial_callback(self, data:dict):
        telegram:EltakoMessage = data['msg']
        current_base_id:str = data['base_id']

        # filter out poll messages
        filter = type(telegram) not in [EltakoPoll]
        # filter out empty telegrams (generated when sending telegrams with FAM-USB)
        try:
            filter &= (int.from_bytes(telegram.address, 'big') > 0 and int.from_bytes(telegram.payload, 'big'))
        except:
            pass

        if filter:
            tt = type(telegram).__name__
            adr = str(telegram.address) if isinstance(telegram.address, int) else b2s(telegram.address)
            if hasattr(telegram, 'reported_address'):
                adr = telegram.reported_address
            payload = ''
            if hasattr(telegram, 'data'):
                payload += ', data: '+b2s(telegram.data)
            elif hasattr(telegram, 'payload'):
                payload += ', payload: '+b2s(telegram.payload)
            
            if hasattr(telegram, 'status'):
                payload += ', status: '+ a2s(telegram.status, 1)

            # show only selected ids
            if self.id_filter is not None and len(self.id_filter) > 0:
                if adr.upper() not in self.id_filter:
                    return

            values_txt = ''
            device:Device = None
            if current_base_id is None: 
                device = self.data_manager.get_device_by_id(adr)
            elif isinstance(adr, str) and '-' in adr:
                device = self.data_manager.find_device_by_local_address(adr, current_base_id)

            if device and not (device.name == 'unknown' and device.device_type == 'unknown'):
                values_txt += f" \n=> {device.name} ({device.device_type})"

                eep, values = self.data_manager.get_values_from_message_to_string(telegram, current_base_id)
                if eep is not None: 
                    if values is not None:
                        values_txt += f" values for EEP {eep.__name__}: ({values})"
                    else:
                        values_txt += f" No matching value for EEP {eep.__name__}"

            display_values:str = values_txt if self.show_telegram_values else ''
            display_esp2:str = f", ESP2: {telegram.serialize().hex()}" if self.show_esp2_binary else ''
            display_esp3:str = f", ESP3: { ''.join(f'{num:02x}' for num in ESP3SerialCommunicator.convert_esp2_to_esp3_message(telegram).build())}" if self.show_esp3_binary else ''

            log_msg     = f"Received Telegram: {tt} from {adr}{payload}{display_values}"
            LOGGER.info(log_msg)

            display_msg = f"Received Telegram: {tt} from {adr}{payload}{display_values}{display_esp2}{display_esp3}"
            if self.process_log_message is not None: 
                self.process_log_message({'msg': display_msg, 'color': 'darkgrey'})