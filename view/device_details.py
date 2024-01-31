import tkinter as tk
import os
import copy
from pathlib import Path
from tkinter import *
from tkinter import ttk
from tkinter.tix import IMAGETEXT
from PIL import Image, ImageTk
from idlelib.tooltip import Hovertip
from controller import AppController, ControllerEventType
from const import *
from homeassistant.const import CONF_ID, CONF_NAME

from eltakobus.device import SensorInfo, KeyFunction
from eltakobus.util import b2s
from data.data import DataManager, Device, EEP_MAPPING


class DeviceDetails():

    def __init__(self, main: Tk, controller:AppController, data_manager:DataManager):
        self.main = main
        self.controller = controller
        self.data_manager = data_manager
        self.current_device = None

        self.controller.add_event_handler(ControllerEventType.SELECTED_DEVICE, self.selected_device_handler)

        f = LabelFrame(self.main, padx=3, pady=3, text="Device Details")
        f.pack(fill="both")
        self.root = f


    def show_form(self, device:Device):
        f = self.root

        self.clean_and_disable()

        c_row = 0

        # name
        l = Label(f, text="Name")
        l.grid(row=0, column=0, sticky=W, padx=3)

        self.text_name = Entry(f)
        self.text_name.grid(row=c_row, column=1)
        self._update_text_field(self.text_name, device.name, NORMAL)


        # address
        c_row += 1
        l = Label(f, text="Address")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        self.text_address = Entry(f)
        self.text_address.insert(END, "00-00-00-00")
        self.text_address.config(state=DISABLED)
        self.text_address.grid(row=c_row, column=1)
        self._update_text_field(self.text_address, device.address)


        # version
        c_row += 1
        l = Label(f, text="Version")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        self.text_version = Entry(f)
        self.text_version.config(state=DISABLED)
        self.text_version.grid(row=c_row, column=1)
        self._update_text_field(self.text_version, device.version)

        # device type
        c_row += 1
        l = Label(f, text="Device Type")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        self.cb_device_type = ttk.Combobox(f, width="20") 
        self.cb_device_type['values'] = list(set([t['hw-type'] for t in EEP_MAPPING]))
        self.cb_device_type.grid(row=c_row, sticky=W, column=1)
        self.cb_device_type.set(device.device_type if device.device_type else '')

        # comment
        c_row += 1
        l = Label(f, text="Comment")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        self.text_comment = Entry(f)
        self.text_comment.grid(row=c_row, column=1)
        self._update_text_field(self.text_comment, device.comment, NORMAL)

        c_row += 1
        l = Label(f, text="Device EEP")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        self.cb_device_eep = ttk.Combobox(f, width="20") 
        self.cb_device_eep['values'] = list(set([t[CONF_EEP] for t in EEP_MAPPING]))
        self.cb_device_eep.grid(row=c_row, sticky=W, column=1)
        self.cb_device_eep.set(device.eep if device.eep else '')

        # in HA
        c_row += 1
        self.cb_export_ha_var = tk.IntVar()
        cb = Checkbutton(f, text="Export to HA Config", variable=self.cb_export_ha_var)
        cb.grid(row=c_row, sticky=W, column=0, columnspan=2, padx=3)
        self.cb_export_ha_var.set(1 if device.use_in_ha else 0)

        # HA platform
        c_row += 1
        l = Label(f, text="HA Platform")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        self.cb_ha_platform = ttk.Combobox(f, width="20", state="readonly") 
        self.cb_ha_platform['values'] = [p.value for p in Platform]
        self.cb_ha_platform.grid(row=c_row, sticky=W, column=1)
        self.cb_ha_platform.set(device.ha_platform if device.ha_platform else '')

        # additional fields
        c_row += 1
        f = Frame(self.root)
        f.grid(row=c_row, column=0, sticky=W, padx=3, columnspan=2)
        self.add_additional_fields(device.additional_fields, f)

        # memory entries
        c_row += 1
        l = Label(self.root, text="Device Memory")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        c_row += 1
        f = Frame(self.root)
        f.grid(row=c_row, column=0, sticky=W+E, padx=3, columnspan=2)

        tv = ttk.Treeview(f, selectmode="none",height=10,columns=(0,1,2))
        tv['show'] = 'headings'
        tv.heading(0, text="Mem.Row")
        tv.column(0, anchor="w", width=40)
        tv.heading(1, text="Address")
        tv.column(1, anchor="w", width=80)
        tv.heading(2, text="Function")
        tv.column(2, anchor="w", width=200)
        for _m in device.memory_entries:
            m:SensorInfo = _m
            if not tv.exists(m.sensor_id_str):
                tv.insert(parent='', index="end", iid=m.sensor_id_str, values=(m.memory_line, m.sensor_id_str, KeyFunction(m.key_func).name))
        tv.pack(expand=True, fill="both")

        # list of references
        c_row += 1
        l = Label(self.root, text="Related Devices")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        c_row += 1
        f = Frame(self.root)
        f.grid(row=c_row, column=0, sticky=W+E, padx=3, columnspan=2)

        tv = ttk.Treeview(f, selectmode="none",height=10,columns=(0,1,2))
        tv['show'] = 'headings'
        tv.heading(0, text="Name")
        tv.column(0, anchor="w", width=40)
        tv.heading(1, text="Address")
        tv.column(1, anchor="w", width=80)
        tv.heading(2, text="Type")
        tv.column(2, anchor="w", width=200)
        for _d in self.data_manager.get_related_devices(device.external_id):
            d:Device = _d
            if not tv.exists(d.external_id):
                tv.insert(parent='', index="end", iid=d.external_id, values=(d.name, d.address, d.device_type))
        tv.pack(expand=True, fill="both")


        # buttons
        c_row += 1
        f_btn = Frame(self.root)
        f_btn.grid(row=c_row, column=0, columnspan=2)

        self.btn_cancel = Button(f_btn, text="Reload", anchor=CENTER, command=self.reload_values)
        self.btn_cancel.grid(row=0, column=0, padx=4, pady=4)
        self.btn_apply = Button(f_btn, text="Apply", anchor=CENTER, command=lambda: self.update_device(device))
        self.btn_apply.grid(row=0, column=1, padx=4, pady=4)

        self.last_row = c_row+1


    def update_device(self, device):
        device.name = self.text_name.get()
        device.address = self.text_address.get()
        device.version = self.text_version.get()
        device.device_type = self.cb_device_type.get()
        device.comment = self.text_comment.get()
        device.eep = self.cb_device_eep.get()
        device.use_in_ha = self.cb_export_ha_var.get() == 1
        device.ha_platform = self.cb_ha_platform.get()

        self.data_manager.update_device(device)

    def add_additional_fields(self, add_fields:dict, f:Frame, _row:int=0):
        for key in add_fields:
            value = add_fields[key]
            if not isinstance(value, dict):
                l = Label(f, text=key.title())
                l.grid(row=_row, column=0, sticky=W, padx=3)

                t = Entry(f)
                t.insert(END, str(value) )
                def set_additional_field_value(event, add_fields, t):
                    add_fields[key] = t.get()
                t.bind("<Any-KeyPress>", lambda e, af=add_fields, t=t: set_additional_field_value(e,af,t))
                t.grid(row=_row, column=1)
            _row += 1

        for key in add_fields:
            value = add_fields[key]
            if isinstance(value, dict):
                lf = LabelFrame(f, text=key.title())
                lf.grid(row=_row, column=0, sticky=W, padx=3, columnspan=2)
                self.add_additional_fields(value, lf)
            _row += 1 

    def clean_and_disable(self) -> None:
        for widget in self.root.winfo_children():
            widget.destroy()

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

    def reload_values(self):
        if self.current_device:
            self.selected_device_handler(self.current_device, force_update=True)

    def selected_device_handler(self, device:Device, force_update:bool=False) -> None:
        # do not overwrite values if clicking on the same
        if not self.current_device or force_update or self.current_device.external_id != device.external_id:
            self.show_form(copy.deepcopy(device))
            self.current_device = device
