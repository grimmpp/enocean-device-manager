import tkinter as tk
from tkinter import *
from tkinter import ttk
import tkinter.scrolledtext as ScrolledText

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

    def serial_callback(self, data):
        if type(data) not in [EltakoPoll, EltakoDiscoveryReply, EltakoDiscoveryRequest]:
            self.receive_log_message({'msg': str(prettify(data)), 'color': 'darkgrey'})

    def receive_log_message(self, data):
        msg = data.get('msg', False)
        if not msg: return

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