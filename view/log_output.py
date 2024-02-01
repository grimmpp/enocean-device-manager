from datetime import datetime
import tzlocal
import time
import tkinter as tk
from tkinter import *
from tkinter import ttk
import tkinter.scrolledtext as ScrolledText
from data.data_helper import b2s, a2s
from eltakobus.message import EltakoPoll, EltakoDiscoveryReply, EltakoDiscoveryRequest, EltakoMessage, prettify, Regular1BSMessage, EltakoWrapped1BS

from controller import AppController, ControllerEventType

class LogOutputPanel():

    def __init__(self, main: Tk, controller:AppController):
        self.controller = controller

        pane = ttk.Frame(main, padding=2)
        # pane.grid(row=2, column=0, sticky="nsew", columnspan=3)
        self.root = pane

        self.st = ScrolledText.ScrolledText(pane, border=3, height=10, state='disabled', bg='black', fg='lightgrey', font=('Arial', 14), padx=5, pady=5)
        self.st.configure(font='TkFixedFont')
        self.st.pack(expand=True, fill="both")
        # self.st.grid(row=2, column=0, sticky="nsew", columnspan=3)

        controller.add_event_handler(ControllerEventType.SERIAL_CALLBACK, self.serial_callback)
        controller.add_event_handler(ControllerEventType.LOG_MESSAGE, self.receive_log_message)

    def serial_callback(self, data:EltakoMessage):
        if type(data) not in [EltakoPoll, EltakoDiscoveryReply, EltakoDiscoveryRequest]:
            telegram = data
            tt = type(telegram).__name__
            adr = b2s(telegram.address)
            payload = ''
            if hasattr(telegram, 'data'):
                payload += ', data: '+b2s(telegram.data)
            elif hasattr(telegram, 'payload'):
                payload += ', payload: '+b2s(telegram.payload)
            
            if hasattr(telegram, 'status'):
                payload += ', status: '+ a2s(telegram.status, 1)

            self.receive_log_message({'msg': f"Received Telegram: {tt} from {adr}{payload}", 'color': 'darkgrey'})

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