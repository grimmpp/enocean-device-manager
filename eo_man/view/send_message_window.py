
from tkinter import *
import tkinter as tk
from tkinter import Tk, ttk

from eltakobus.message import *
from eltakobus.eep import A5_08_01
from eltakobus.util import AddressExpression

from ..controller.app_bus import AppBus, AppBusEventType
from ..controller.serial_controller import SerialController
from ..data import data_helper


class SendMessageWindow():

    def __init__(self, main:Tk, app_bus:AppBus, serial_controller:SerialController):
        self.main = main
        self.app_bus = app_bus
        self.serial_controller = serial_controller

        self.app_bus.add_event_handler(AppBusEventType.CONNECTION_STATUS_CHANGE, self.on_connection_state_changed)

        self.popup = None

    def show_window(self):
        if self.popup:
            self.center_window()
            return

        self.popup = Toplevel(self.main, padx=4, pady=4)
        self.popup.wm_title("Send Message")
        
        row = 0
        l = ttk.Label(self.popup, text="Message Type: ")
        l.grid(row=row, column=0, sticky=W)

        self.l_msg_type = ttk.Label(self.popup, text='')
        self.l_msg_type.grid(row=row, column=1, sticky=W)
        self.cb_msg_type = ttk.Combobox(self.popup, state="readonly", width="14") 
        self.cb_msg_type['values'] = ['RPS (Org = 0x05)', '1BS (Org = 0x06)', '4BS (Org = 0x7)']
        self.cb_msg_type.set('4BS (Org = 0x7)')
        self.cb_msg_type.grid(row=row, column=1, sticky=W)
        # self.cb_msg_type.bind('<<ComboboxSelected>>', self.show_message)


        row += 1
        l = ttk.Label(self.popup, text="Data: ")
        l.grid(row=row, column=0, sticky=W)

        self.e_data = ttk.Entry(self.popup, width="12") 
        self.e_data.insert(END, "aa 80 76 0f")
        self.e_data.bind_all('<Key>', self.show_message)
        self.e_data.grid(row=row, column=1, sticky=W)


        row += 1
        l = ttk.Label(self.popup, text="Status: ")
        l.grid(row=row, column=0, sticky=W)

        self.e_status = ttk.Entry(self.popup, width="3") 
        self.e_status.insert(END, "00")
        self.e_status.bind_all('<Key>', self.show_message)
        self.e_status.grid(row=row, column=1, sticky=W)


        row += 1
        l = ttk.Label(self.popup, text="Sender Id: ")
        l.grid(row=row, column=0, sticky=W)
        self.cb_sender_id = ttk.Combobox(self.popup, state="readonly", width="14") 
        self.set_sender_ids()
        self.cb_sender_id.grid(row=row, column=1, sticky=W)


        row += 1
        self.l_telegram = ttk.Label(self.popup, text="A5 5A")
        self.l_telegram.grid(row=row, column=0, sticky=EW, columnspan=2)


        row += 1
        l = ttk.Label(self.popup, text="")
        l.grid(row=row, column=0, sticky=W, columnspan=2)


        row += 1
        b_close = ttk.Button(self.popup, text="Close", command=self.close)
        b_close.bind('<Return>', lambda e: self.close())
        b_close.grid(row=row, column=0)

        self.b_send = ttk.Button(self.popup, text="Send", command=lambda send=True: self.show_message(None, send))
        if not self.serial_controller.is_serial_connection_active():
            self.b_send.config(state=DISABLED)
        self.b_send.bind('<Return>', lambda event, send=True: self.show_message(event, send))
        self.b_send.grid(row=row, column=1)

        self.show_message(None)

        self.popup.wm_attributes('-toolwindow', 'True')
        self.popup.protocol("WM_DELETE_WINDOW", self.close)
        self.popup.resizable (width=False, height=False)
        
        self.popup.after(10, self.center_window)

        self.main.wait_window(self.popup)


    def center_window(self):
        if self.popup:
            w = 230 # popup.winfo_width()
            h = self.popup.winfo_height()
            x = self.main.winfo_x() + self.main.winfo_width()/2 - w/2
            y = self.main.winfo_y() + self.main.winfo_height()/2 - h/2
            self.popup.geometry('%dx%d+%d+%d' % (w, h, x, y))
            self.popup.focus()


    def close(self):
        if self.popup:
            self.popup.destroy()
            self.popup = None
    
    
    def set_sender_ids(self):
        if self.serial_controller.current_base_id:
            base_id = self.serial_controller.current_base_id
            adr_space = []
            for i in range(0,128): adr_space.append(data_helper.a2s(data_helper.a2i(base_id)+i))
            self.cb_sender_id['values'] = adr_space
            self.cb_sender_id.set(adr_space[0])
        else:
            self.cb_sender_id['values'] = []
            self.cb_sender_id.set('')


    def on_connection_state_changed(self, data):
        if self.popup:
            if data.get('connected'):
                self.b_send.config(state=NORMAL)
            else:
                self.b_send.config(state=DISABLED)
            self.set_sender_ids()
    

    def get_data_from_entry(self):
        text = self.e_data.get().upper()
        hex_string = '0x'
        for c in text:
            if c in ['0','1','2','3','4','5','6','7','8','9','A','B','C','D','E','F']:
                hex_string += c
        return int(hex_string, 16).to_bytes(4, 'big') 


    def show_message(self, event, send:bool=False):
        msg_type = self.cb_msg_type.get()
        try:
            sender_id = AddressExpression.parse( self.cb_sender_id.get() )[0]
            data = self.get_data_from_entry()
            status = int(self.e_status.get(), 16)
            
            if '4BS' in msg_type:
                msg = Regular4BSMessage(sender_id, status, data, True)
            elif '1BS' in msg_type:
                data = data[0:1]
                msg = Regular1BSMessage(sender_id, status, data, True)
            elif 'RPS' in msg_type:
                msg = RPSMessage(sender_id, status, data, True)
                data = data[0:1]

            msg_text = b2a(msg.serialize()).upper()
            self.l_telegram.config(text=msg_text)

            if send:
                self.serial_controller.send_message(msg)
                self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Send Message: {str(msg)}", 'color':'green', 'log-level':'INFO'})
        except:
            self.l_telegram.config(text='No valid telegram')


