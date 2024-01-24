import tkinter as tk
import os
from pathlib import Path
from tkinter import *
from tkinter import ttk
from tkinter import filedialog
from tkinter.tix import IMAGETEXT
from PIL import Image, ImageTk
from idlelib.tooltip import Hovertip
from controller import AppController, ControllerEventType
from const import *
from homeassistant.const import CONF_ID, CONF_NAME

from eltakobus.util import b2s
from data import DataManager, Device, EEP_MAPPING


class DeviceDetails():

    def __init__(self, main: Tk, controller:AppController, data_manager:DataManager):
        self.main = main
        self.controller = controller
        self.data_manager = data_manager
        self.current_device = None

        f = LabelFrame(main, padx=3, pady=3, text="Device Details")
        f.pack()
        self.root = f

        c_row = 0

        # name
        l = Label(f, text="Name")
        l.grid(row=0, column=0, sticky=W, padx=3)

        self.text_name = Entry(f)
        self.text_name.grid(row=c_row, column=1)


        # address
        c_row += 1
        l = Label(f, text="Address")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        self.text_address = Entry(f)
        self.text_address.insert(END, "00-00-00-00")
        self.text_address.config(state=DISABLED)
        self.text_address.grid(row=c_row, column=1)


        # version
        c_row += 1
        l = Label(f, text="Version")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        self.text_version = Entry(f)
        self.text_version.config(state=DISABLED)
        self.text_version.grid(row=c_row, column=1)

        # device type
        c_row += 1
        l = Label(f, text="Device Type")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        self.cb_device_type = ttk.Combobox(f, width="20") 
        self.cb_device_type['values'] = list(set([t['hw-type'] for t in EEP_MAPPING]))
        self.cb_device_type.grid(row=c_row, sticky=W, column=1)

        # comment
        c_row += 1
        l = Label(f, text="Comment")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        self.text_comment = Entry(f)
        self.text_comment.grid(row=c_row, column=1)

        # comment
        c_row += 1
        l = Label(f, text="Device EEP")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        self.cb_device_eep = ttk.Combobox(f, width="20") 
        self.cb_device_eep['values'] = list(set([t[CONF_EEP] for t in EEP_MAPPING]))
        self.cb_device_eep.grid(row=c_row, sticky=W, column=1)

        # in HA
        c_row += 1
        self.text_comment = Checkbutton(f, text="Export to HA Config")
        self.text_comment.grid(row=c_row, sticky=W, column=0, columnspan=2, padx=3)

        # HA platform
        c_row += 1
        l = Label(f, text="HA Platform")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        self.cb_device_eep = ttk.Combobox(f, width="20", state="readonly") 
        self.cb_device_eep['values'] = [p.value for p in Platform]
        self.cb_device_eep.grid(row=c_row, sticky=W, column=1)

        # sender
        c_row += 1
        lf = LabelFrame(f, padx=3, pady=3, text="Sender")
        lf.grid(row=c_row, column=0, sticky=W, columnspan=2)
        l = Label(lf, text="Address")
        l.grid(row=0, column=0, sticky=W, padx=3)

        self.text_sender_id = Entry(lf)
        self.text_sender_id.grid(row=0, column=1)

        l = Label(lf, text="EEP")
        l.grid(row=1, column=0, sticky=W, padx=3)

        self.text_sender_eep = Entry(lf)
        self.text_sender_eep.grid(row=1, column=1)

        # buttons
        c_row += 1
        f_btn = Frame(f)
        f_btn.grid(row=c_row, column=0, columnspan=2)

        self.btn_cancel = Button(f_btn, text="Cancel", anchor=CENTER, command=self.clean_and_disable)
        self.btn_cancel.grid(row=0, column=0, padx=4, pady=4)
        self.btn_apply = Button(f_btn, text="Apply", anchor=CENTER, command=self.update_current_device)
        self.btn_apply.grid(row=0, column=1, padx=4, pady=4)
        
        
        # self.clean_and_disable()

        self.controller.add_event_handler(ControllerEventType.SELECTED_DEVICE, self.selected_device_handler)


    def clean_and_disable(self) -> None:
        for t in [self.text_name, self.text_address, self.text_version, self.text_comment]:
            t.config(state=NORMAL)
            t.delete(0, 'end')
            t.config(state=DISABLED)

    def update_current_device(self) -> None:
        if self.current_device is not None:
            if self.text_name['state'] == NORMAL:
                self.current_device.name = self.text_name.get()
            if self.text_comment['state'] == NORMAL:
                self.current_device.comment = self.text_comment.get()
            self.data_manager.update_device(self.current_device)

    def _update_text_field(self, text_field:Entry, value:str, state:str=DISABLED):
        try:
            text_field.config(state=NORMAL)
            text_field.delete(0, END)
            if value is None:
                value = ""
            text_field.insert(END, value)
        except Exception as e:
            pass
        else:
            text_field.config(state=state)


    def selected_device_handler(self, device:Device) -> None:
        self.current_device = device
        self._update_text_field(self.text_name, device.name, NORMAL)
        self._update_text_field(self.text_version, device.version)
        self._update_text_field(self.text_address, device.address)
        self._update_text_field(self.text_comment, device.comment, NORMAL)

        