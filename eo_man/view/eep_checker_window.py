from tkinter import *
import tkinter as tk
from tkinter import Tk, ttk

from eltakobus.message import *
from eltakobus.eep import A5_08_01

from ..data import data_helper


class EepCheckerWindow():

    def __init__(self, main:Tk):
        popup = Toplevel(main, padx=4, pady=4)
        popup.wm_title("EEP Checker")
        self.popup = popup

        row = 0
        self.l_telegram = ttk.Label(popup, text="A5 5A")
        self.l_telegram.grid(row=row, column=0, sticky=EW, columnspan=2)

        row += 1
        l = ttk.Label(popup, text="EEP: ")
        l.grid(row=row, column=0, sticky=W)

        self.cb_eep = ttk.Combobox(popup, state="readonly", width="14") 
        self.cb_eep['values'] = data_helper.get_all_eep_names()
        self.cb_eep.set(A5_08_01.eep_string)
        self.cb_eep.grid(row=row, column=1, sticky=W)
        self.cb_eep.bind('<<ComboboxSelected>>', lambda e: [self.set_message_type(), self.show_eep_values(e)])


        row += 1
        l = ttk.Label(popup, text="Message Type: ")
        l.grid(row=row, column=0, sticky=W)

        self.l_msg_type = ttk.Label(popup, text='')
        self.l_msg_type.grid(row=row, column=1, sticky=W)
        # self.cb_msg_type = ttk.Combobox(popup, state="readonly", width="14") 
        # self.cb_msg_type['values'] = ['RPS (Org = 0x05)', '1BS (Org = 0x06)', '4BS (Org = 0x7)']
        # self.cb_msg_type.set('4BS (Org = 0x7)')
        # self.cb_msg_type.grid(row=row, column=1, sticky=W)
        # self.cb_msg_type.bind('<<ComboboxSelected>>', self.show_message)


        row += 1
        l = ttk.Label(popup, text="Data: ")
        l.grid(row=row, column=0, sticky=W)

        self.e_data = ttk.Entry(popup, width="12") 
        self.e_data.insert(END, "aa 80 76 0f")
        self.e_data.bind_all('<Key>', self.show_eep_values)
        self.e_data.grid(row=row, column=1, sticky=W)


        row += 1
        l = ttk.Label(popup, text="EEP Values: ")
        l.grid(row=row, column=0, sticky=W, columnspan=2)


        row += 1
        self.l_result = ttk.Label(popup, text="", font=("Arial", 11))
        self.l_result.grid(row=row, column=0, sticky=W, columnspan=2)


        row += 1
        l = ttk.Label(popup, text="")
        l.grid(row=row, column=0, sticky=W, columnspan=2)


        row += 1
        b = ttk.Button(popup, text="Close", command=popup.destroy)
        b.bind('<Return>', lambda e: popup.destroy())
        b.grid(row=row, column=0, columnspan=2, sticky=E)

        self.show_eep_values(None)

        popup.wm_attributes('-toolwindow', 'True')

        def center():
            w = popup.winfo_width()
            h = popup.winfo_height()
            x = main.winfo_x() + main.winfo_width()/2 - w/2
            y = main.winfo_y() + main.winfo_height()/2 - h/2
            popup.geometry('%dx%d+%d+%d' % (w, h, x, y))

        popup.after(10, center)

        main.wait_window(popup)


    
    def set_message_type(self):
        try:
            msg = Regular4BSMessage(b'\x00\x00\x00\x00', 0x00, b'\x00\x00\x00\x00', False)
            eep = data_helper.find_eep_by_name(self.cb_eep.get())
            eep_values = data_helper.get_values_for_eep(eep, msg)
            self.l_msg_type.config(text= '4BS (Org = 0x7)')
            return '4BS (Org = 0x7)'
        except:
            pass

        try:
            msg = Regular1BSMessage(b'\x00\x00\x00\x00', 0x00, b'\x00', False)
            eep = data_helper.find_eep_by_name(self.cb_eep.get())
            eep_values = data_helper.get_values_for_eep(eep, msg)
            self.l_msg_type.config(text= '1BS (Org = 0x06)')
            return '1BS (Org = 0x06)'
        except:
            pass

        try:
            msg = RPSMessage(b'\x00\x00\x00\x00', 0x00, b'\x00', False)
            eep = data_helper.find_eep_by_name(self.cb_eep.get())
            eep_values = data_helper.get_values_for_eep(eep, msg)
            self.l_msg_type.config(text= 'RPS (Org = 0x05)')
            return 'RPS (Org = 0x05)'
        except:
            pass


    def get_data_from_entry(self):
        text = self.e_data.get().upper()
        hex_string = '0x'
        for c in text:
            if c in ['0','1','2','3','4','5','6','7','8','9','A','B','C','D','E','F']:
                hex_string += c
        return int(hex_string, 16).to_bytes(4, 'big') 


    def show_eep_values(self, event):
        msg_type = self.set_message_type()
        try:
            data = self.get_data_from_entry()
            
            if '4BS' in msg_type:
                msg = Regular4BSMessage(b'\x00\x00\x00\x00', 0x00, data, False)
            elif '1BS' in msg_type:
                data = data[0:1]
                msg = Regular1BSMessage(b'\x00\x00\x00\x00', 0x00, data, False)
            elif 'RPS' in msg_type:
                msg = RPSMessage(b'\x00\x00\x00\x00', 0x00, data, False)
                data = data[0:1]

            msg_text = b2a(msg.serialize()).upper()
            self.l_telegram.config(text=msg_text)
        except:
            self.l_telegram.config(text='')

        try:
            eep = data_helper.find_eep_by_name(self.cb_eep.get())
            eep_values = data_helper.get_values_for_eep(eep, msg)
            self.l_result.config(text='\n'.join(eep_values).replace('_',' '))

        except:
            self.l_result.config(text='')