import tkinter as tk
import copy
from tkinter import *
from tkinter import ttk
from tkscrolledframe import ScrolledFrame

from idlelib.tooltip import Hovertip

from eltakobus.device import SensorInfo, KeyFunction
from eltakobus.util import b2s
from eltakobus.eep import EEP

from ..data.data_manager import DataManager, Device
from ..data import data_helper
from ..controller.app_bus import AppBus, AppBusEventType
from ..data.const import *

from ..icons.image_gallary import ImageGallery

from .device_info_window import DeviceInfoWindow


class DeviceDetails():

    def __init__(self, window: Tk, main: Tk, app_bus:AppBus, data_manager:DataManager):
        self.window = window
        self.main = main
        self.app_bus = app_bus
        self.data_manager = data_manager
        self.current_device = None

        self.app_bus.add_event_handler(AppBusEventType.SELECTED_DEVICE, self.selected_device_handler)

        main_frame = Frame(main, width=365)
        main_frame.pack(side=LEFT, fill=BOTH, expand=2)

        # main
        scrolledFrame = ScrolledFrame(main_frame, use_ttk=True)
        scrolledFrame.pack(side=LEFT, fill=BOTH, expand=2)

        # Bind the arrow keys and scroll wheel
        scrolledFrame.bind_arrow_keys(window)
        scrolledFrame.bind_scroll_wheel(window)

        inner_frame = scrolledFrame.display_widget(LabelFrame)
        inner_frame.config(text="Device Details", padx=6, pady=3)
        

        self.root = main_frame
        self.inner_frame = inner_frame
        

    def show_form(self, device:Device):
        f = self.inner_frame

        self.clean_and_disable(self.inner_frame)

        c_row = 0

        # name
        l = Label(f, text="Name")
        l.grid(row=0, column=0, sticky=W, padx=3)

        self.text_name = ttk.Entry(f)
        self.text_name.grid(row=c_row, column=1, sticky=W+E)
        self._update_text_field(self.text_name, device.name, NORMAL)
        self.text_name.bind('<Return>', lambda e, d=device: self.update_device(d))
        

        # address
        c_row += 1
        l = Label(f, text="Address")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        self.text_address = ttk.Entry(f)
        self.text_address.insert(END, "00-00-00-00")
        self.text_address.config(state=NORMAL)
        self.text_address.grid(row=c_row, column=1, sticky=W+E)
        self._update_text_field(self.text_address, device.address)
        # self.text_address.bind('<Return>', lambda e, d=device: self.update_device(d))
        self.text_address.bind_all('<Key>', lambda e: [])

        # base id
        c_row += 1
        l = Label(f, text="Base Id")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        self.text_base_id = ttk.Entry(f)
        self.text_base_id.insert(END, "00-00-00-00")
        self.text_base_id.config(state=DISABLED)
        self.text_base_id.grid(row=c_row, column=1, sticky=W+E)
        self._update_text_field(self.text_base_id, device.base_id)
        # self.text_address.bind('<Return>', lambda e, d=device: self.update_device(d))

        # external address
        c_row += 1
        l = Label(f, text="External Id")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        self.text_ext_address = ttk.Entry(f)
        self.text_ext_address.insert(END, "00-00-00-00")
        self.text_ext_address.config(state=DISABLED)
        self.text_ext_address.grid(row=c_row, column=1, sticky=W+E)
        self._update_text_field(self.text_ext_address, device.external_id)
        self.text_ext_address.bind('<Return>', lambda e, d=device: self.update_device(d))


        # version
        c_row += 1
        l = Label(f, text="Version")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        self.text_version = ttk.Entry(f)
        self.text_version.config(state=DISABLED)
        self.text_version.grid(row=c_row, column=1, sticky=W+E)
        self._update_text_field(self.text_version, device.version)
        self.text_version.bind('<Return>', lambda e, d=device: self.update_device(d))

        # device type
        c_row += 1
        f2 = Frame(f)
        f2.grid(row=c_row, column=0, sticky=W, padx=3 )
        l = Label(f2, text="Device Type")
        l.grid(row=0, column=0, sticky=W, padx=(0,3) )
        
        device_info_btn = tk.Button(f2, relief=FLAT, borderwidth=0, image=ImageGallery.get_info_icon((16,16)), cursor="hand2")
        Hovertip(device_info_btn, 'Detailed Device Info', 300)
        device_info_btn.grid(row=0, column=1, sticky=W, padx=0)
        device_info_btn.bind("<Button-1>", lambda e: DeviceInfoWindow(self.window))

        self.cb_device_type = ttk.Combobox(f, width="20") 
        self.cb_device_type['values'] = data_helper.get_known_device_types()
        self.cb_device_type.grid(row=c_row, column=1, sticky=W+E)
        self.cb_device_type.set(device.device_type if device.device_type else '')
        if device.is_gateway():
            self.cb_device_type.config(state=DISABLED)
        else:
            self.cb_device_type.bind('<Return>', lambda e, d=device: self.update_device(d))
            self.cb_device_type.bind('<<ComboboxSelected>>', lambda e, d=device: self.update_device(d, False, True) )



        # Key Function
        c_row += 1
        l = Label(f, text="Key Function (for Sensor)")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        self.cb_key_function = ttk.Combobox(f, width="20") 
        self.cb_key_function['values'] = [kf.name for kf in KeyFunction]
        self.cb_key_function.grid(row=c_row, column=1, sticky=W+E)
        self.cb_key_function.set(device.key_function if device.key_function else '')
        self.cb_key_function.bind('<Return>', lambda e, d=device: self.update_device(d))


        # comment
        c_row += 1
        l = Label(f, text="Comment")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        self.text_comment = ttk.Entry(f)
        self.text_comment.grid(row=c_row, column=1, sticky=W+E)
        self._update_text_field(self.text_comment, device.comment, NORMAL)
        self.text_comment.bind('<Return>', lambda e, d=device: self.update_device(d))

        c_row += 1
        l = Label(f, text="Device EEP")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        
        self.cb_device_eep = ttk.Combobox(f, width="20") 
        self.cb_device_eep['values'] = data_helper.get_all_eep_names()
        self.cb_device_eep.grid(row=c_row, column=1, sticky=W+E)
        self.cb_device_eep.set(device.eep if device.eep else '')
        self.cb_device_eep.bind('<Return>', lambda e, d=device: self.update_device(d))


        # in HA
        c_row += 1
        self.cb_export_ha_var = tk.IntVar()
        cb = ttk.Checkbutton(f, text="Export to HA Config", variable=self.cb_export_ha_var)
        cb.grid(row=c_row, column=0, columnspan=2, padx=3, sticky=W)
        self.cb_export_ha_var.set(1 if device.use_in_ha else 0)
        cb.bind('<Return>', lambda e, d=device: self.update_device(d))

        # HA platform
        c_row += 1
        l = Label(f, text="HA Platform")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        self.cb_ha_platform = ttk.Combobox(f, width="20", state="readonly") 
        self.cb_ha_platform['values'] = sorted([p.value for p in Platform])
        self.cb_ha_platform.grid(row=c_row, sticky=W+E, column=1)
        self.cb_ha_platform.set(device.ha_platform if device.ha_platform else '')
        self.cb_ha_platform.bind('<Return>', lambda e, d=device: self.update_device(d))

        # additional fields
        c_row += 1
        c_row = self.add_additional_fields(device, device.additional_fields, f, '', c_row)

        # memory entries
        c_row += 1
        l = Label(f, text="Device Memory")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        c_row += 1
        ff = Frame(f)
        ff.grid(row=c_row, column=0, sticky=W+E, padx=3, columnspan=2)

        tv = ttk.Treeview(ff, selectmode="none",height=10,columns=(0,1,2))
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
        l = Label(f, text="Related Devices")
        l.grid(row=c_row, column=0, sticky=W, padx=3)

        c_row += 1
        ff = Frame(f)
        ff.grid(row=c_row, column=0, sticky=W+E, padx=3, columnspan=2)

        tv = ttk.Treeview(ff, selectmode="none",height=10,columns=(0,1,2))
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
        f_btn = Frame(f)
        f_btn.grid(row=c_row, column=0, columnspan=2)

        self.btn_cancel = Button(f_btn, text="Reload", anchor=CENTER, command=self.reload_values)
        self.btn_cancel.grid(row=0, column=0, padx=4, pady=4)
        self.btn_apply = Button(f_btn, text="Apply", anchor=CENTER, command=lambda d=device: self.update_device(d))
        self.btn_apply.grid(row=0, column=1, padx=4, pady=4)

        self.last_row = c_row+1



    def update_device(self, device:Device, force_update:bool=True, suggest_default_values:bool=False):
        device.name = self.text_name.get()
        device.address = self.text_address.get()
        device.version = self.text_version.get()
        device.device_type = self.cb_device_type.get()
        device.key_function = self.cb_key_function.get()
        device.comment = self.text_comment.get()
        device.eep = self.cb_device_eep.get()
        device.use_in_ha = self.cb_export_ha_var.get() == 1
        device.ha_platform = self.cb_ha_platform.get()

        Device.init_sender_fields(device)

        if suggest_default_values:
            Device.set_suggest_ha_config(device, use_in_ha=True)

        if force_update:
            self.data_manager.update_device(device)

        self.selected_device_handler(device, force_update)

    def add_additional_fields(self, device:Device, add_fields:dict, f:Frame, parent_key:str='', _row:int=0, spaces:int=0):
        for key, value in add_fields.items():
            
            if not isinstance(value, dict):
                l = Label(f, text=spaces*" "+key.title())
                l.grid(row=_row, column=0, sticky=W, padx=3)

                def set_additional_field_value(af, k, t):
                    af[k]=t.get()

                if key == 'id' and parent_key == 'sender':
                    cb_s = ttk.Combobox(f, state="readonly", width="3")
                    cb_s['values'] = [data_helper.a2s(i,1) for i in range(0,256)]
                    cb_s.bind('<FocusIn>', self.on_focus_combobox)
                    cb_s.bind('<Key>', self.select_by_entered_keys)
                    cb_s.bind('<Return>', lambda e, af=add_fields, k=key, t=cb_s, d=device: [set_additional_field_value(af,k,t), self.update_device(d)])
                    cb_s.set(str(value))
                    cb_s.grid(row=_row, column=1, sticky=W)
                    # entry = Entry(f)
                    # entry.insert(END, str(value) )
                    # entry.bind("<Any-KeyPress>", lambda e, af=add_fields, k=key, t=entry: set_additional_field_value(af,k,t))# set_additional_field_value(e,af,k,t))
                    # entry.bind('<Return>', lambda e, af=add_fields, k=key, t=entry, d=device: [set_additional_field_value(af,k,t), self.update_device(d)])
                    # if device.address.startswith('00-00-00-'): entry.config(state="readonly")
                    # entry.grid(row=_row, column=1, sticky=W)
                elif 'eep' in key: 
                    cb = ttk.Combobox(f, width="20") 
                    cb['values'] = data_helper.get_all_eep_names()
                    cb.grid(row=_row, column=1, sticky=W+E)
                    cb.set(value)
                    cb.bind('<Return>', lambda e, af=add_fields, k=key, t=cb, d=device: [set_additional_field_value(af,k,t), self.update_device(d)])
                else:
                    entry = Entry(f)
                    entry.insert(END, str(value) )
                    entry.bind("<Any-KeyPress>", lambda e, af=add_fields, k=key, t=entry: set_additional_field_value(af,k,t))# set_additional_field_value(e,af,k,t))
                    entry.bind('<Return>', lambda e, af=add_fields, k=key, t=entry, d=device: [set_additional_field_value(af,k,t), self.update_device(d)])
                    entry.grid(row=_row, column=1, sticky=W+E)

            if isinstance(value, dict):
                # lf = LabelFrame(f, text=key.title())
                # lf.grid(row=_row, column=0, sticky=W, padx=3, columnspan=2)
                l = Label(f, text=spaces*" "+key.title()+":")
                l.grid(row=_row, column=0, sticky=W, padx=3, columnspan=2)
                _row = self.add_additional_fields(device, value, f, key, _row+1, spaces+3)

            _row += 1 

        return _row

    def on_focus_combobox(self, event=None):
        self.entered_keys = ''

    def select_by_entered_keys(self, event=None):

        if event.char.upper() not in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D', 'E', 'F']:
            return

        if event is not None:
            if len(self.entered_keys) < 2:
                self.entered_keys += event.char.upper()
            else:
                self.entered_keys = event.char.upper()

        cb:ttk.Combobox = self.popup.focus_get()
        if len(self.entered_keys) == 2:
            cb.set(self.entered_keys)
        elif len(self.entered_keys) == 1:
            for v in cb['values']:
                if v[0] == self.entered_keys:
                    cb.set(v)
                    break

        self.show_message()

    def clean_and_disable(self, frame:Frame) -> None:
        for widget in frame.winfo_children():
            if isinstance(widget, Frame):
                self.clean_and_disable(widget)
                widget.destroy()
            else:
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
        if device is None:
            self.clean_and_disable(self.inner_frame)
        else:
            if not self.current_device or force_update or self.current_device.external_id != device.external_id:
                self.show_form(copy.deepcopy(device))
                self.current_device = device
            elif self.current_device.external_id == device.external_id:
                self.show_form(copy.deepcopy(device))

