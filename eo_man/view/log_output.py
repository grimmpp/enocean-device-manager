from datetime import datetime
import tkinter as tk
from tkinter import *
from tkinter import ttk
import tkinter.scrolledtext as ScrolledText

from eltakobus.message import EltakoPoll, EltakoDiscoveryReply, EltakoDiscoveryRequest, EltakoMessage, prettify, Regular1BSMessage, EltakoWrapped1BS
from esp2_gateway_adapter.esp3_serial_com import ESP3SerialCommunicator

from eo_man import LOGGER

from ..data.data_helper import b2s, a2s
from ..data.data_manager import DataManager
from ..controller.app_bus import AppBus, AppBusEventType

class LogOutputPanel():

    def __init__(self, main: Tk, app_bus:AppBus, data_manager:DataManager):
        self.app_bus = app_bus
        self.data_manager = data_manager

        pane = ttk.Frame(main, padding=2, height=150)
        # pane.grid(row=2, column=0, sticky="nsew", columnspan=3)
        self.root = pane

        tool_bar = ttk.Frame(pane, height=24)
        tool_bar.pack(expand=False, fill=X, anchor=NW, pady=(0,4))

        # l = Label(tool_bar, text="Search")
        # l.pack(side=LEFT, padx=(2,0))

        # self.e_search = ttk.Entry(tool_bar, width="14") 
        # self.e_search.pack(side=LEFT, padx=(2,0))

        self.show_telegram_values = tk.BooleanVar(value=True)
        cb_show_values = ttk.Checkbutton(tool_bar, text="Show Telegram Values", variable=self.show_telegram_values)
        cb_show_values.pack(side=LEFT, padx=(2,0))

        self.show_esp2_binary =tk.BooleanVar(value=False)
        cb_show_es2_binary = ttk.Checkbutton(tool_bar, text="Show ESP2 Binary", variable=self.show_esp2_binary)
        cb_show_es2_binary.pack(side=LEFT, padx=(2,0))

        self.show_esp3_binary =tk.BooleanVar(value=False)
        cb_show_es3_binary = ttk.Checkbutton(tool_bar, text="Show ESP3 Binary", variable=self.show_esp3_binary)
        cb_show_es3_binary.pack(side=LEFT, padx=(2,0))

        self.st = ScrolledText.ScrolledText(pane, border=3,  height=150, 
                                            state=DISABLED, bg='black', fg='lightgrey', 
                                            font=('Arial', 14), padx=5, pady=5)
        self.st.configure(font='TkFixedFont')
        self.st.pack(expand=True, fill=BOTH)
        # self.st.grid(row=2, column=0, sticky="nsew", columnspan=3)

        app_bus.add_event_handler(AppBusEventType.SERIAL_CALLBACK, self.serial_callback)
        app_bus.add_event_handler(AppBusEventType.LOG_MESSAGE, self.receive_log_message)


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

            values = ''
            eep, values = self.data_manager.get_values_from_message_to_string(telegram, current_base_id)
            if eep is not None: 
                if values is not None:
                    values = f" => values for EEP {eep.__name__}: ({values})"
                else:
                    values = f" => No matching value for EEP {eep.__name__}"
            else:
                values = ''

            display_values:str = values if self.show_telegram_values.get() else ''
            display_esp2:str = f", ESP2: {telegram.serialize().hex()}" if self.show_esp2_binary.get() else ''
            display_esp3:str = f", ESP3: { ''.join(f'{num:02x}' for num in ESP3SerialCommunicator.convert_esp2_to_esp3_message(telegram).build())}" if self.show_esp3_binary.get() else ''

            log_msg     = f"Received Telegram: {tt} from {adr}{payload}{values}"
            LOGGER.info(log_msg)

            display_msg = f"Received Telegram: {tt} from {adr}{payload}{display_values}{display_esp2}{display_esp3}"
            self.receive_log_message({'msg': display_msg, 'color': 'darkgrey'})


    def receive_log_message(self, data):
        msg = data.get('msg', False)
        if not msg: return

        # time_format = "%d.%b %Y %H:%M:%S"
        time_format = "%Y-%m-%d %H:%M:%S.%f"
        time_str = datetime.now().strftime(time_format)
        msg = f"{time_str}: {msg}"

        self.st.configure(state='normal')
        self.st.insert(tk.END, msg + '\n')
        self.st.configure(state='disabled')
        
        color = data.get('color', False)
        if color:
            final_index = str(self.st.index(tk.END))
            num_of_lines = int(final_index.split('.')[0])-2
            self.st.tag_config('mark_'+color, foreground=color)
            self.st.tag_add('mark_'+color, f"{num_of_lines}.0", f"{num_of_lines}.{len(msg)}")
        
        self.st.yview(tk.END)