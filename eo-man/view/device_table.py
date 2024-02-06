import threading
import time
import tkinter as tk
import os
from pathlib import Path
from tkinter import *
from tkinter import ttk
from tkinter import filedialog
from tkinter.tix import IMAGETEXT
from PIL import Image, ImageTk
from idlelib.tooltip import Hovertip

from ..controller.app_bus import AppBus, AppBusEventType
from ..data.const import *
from ..data.homeassistant.const import CONF_ID, CONF_NAME
from ..data.filter import DataFilter
from ..data.data_manager import DataManager, Device
from ..data import data_helper

from eltakobus.util import b2s
from eltakobus.eep import EEP
from eltakobus.message import EltakoMessage, RPSMessage, Regular1BSMessage, Regular4BSMessage, EltakoWrappedRPS


class DeviceTable():

    NON_BUS_DEVICE_LABEL:str="Distributed Devices"

    def __init__(self, main: Tk, app_bus:AppBus, data_manager:DataManager):
        
        self.blinking_enabled = True
        self.pane = ttk.Frame(main, padding=2)
        # self.pane.grid(row=0, column=0, sticky=W+E+N+S)
        self.root = self.pane

        # Scrollbar
        yscrollbar = ttk.Scrollbar(self.pane, orient=VERTICAL)
        yscrollbar.pack(side=RIGHT, fill=Y)

        xscrollbar = ttk.Scrollbar(self.pane, orient=HORIZONTAL)
        xscrollbar.pack(side=BOTTOM, fill=X)

        # Treeview
        columns = ("Address", "External Address", "Device Type", "Key Function", "Comment", "Export to HA Config", "HA Platform", "Device EEP", "Sender Address", "Sender EEP")
        self.treeview = ttk.Treeview(
            self.pane,
            selectmode="browse",
            yscrollcommand=yscrollbar.set,
            xscrollcommand=xscrollbar.set,
            columns=(0,1,2,3,4,5,6,7,8,9),
            height=10,
        )
        self.treeview.pack(expand=True, fill=BOTH)
        yscrollbar.config(command=self.treeview.yview)
        xscrollbar.config(command=self.treeview.xview)

        def sort_rows_in_treeview(tree:ttk.Treeview, col_i:int, descending:bool, partent:str=''):
            data = [(tree.set(item, col_i), item) for item in tree.get_children(partent)]
            data.sort(reverse=descending)
            for index, (val, item) in enumerate(data):
                tree.move(item, partent, index)
            
            for item in tree.get_children(partent):
                sort_rows_in_treeview(tree, col_i, descending, item)

        def sort_treeview(tree:ttk.Treeview, col:int, descending:bool):
            i = columns.index(col)
            for item in tree.get_children(''):
                sort_rows_in_treeview(tree, i, descending, item)
            tree.heading(i, command=lambda c=col, d=(not descending): sort_treeview(tree, c, d))

        self.treeview.column('#0', anchor="w", width=250, minwidth=250)#, stretch=NO)
        for col in columns:
            # Treeview headings
            i = columns.index(col)
            if col in ['Key Function']:
                self.treeview.column(i, anchor="w", width=250, minwidth=250)#, stretch=NO)
            else:
                self.treeview.column(i, anchor="w", width=80, minwidth=80)#, stretch=NO)
            self.treeview.heading(i, text=col, anchor="center", command=lambda c=col, d=False: sort_treeview(self.treeview, c, d))
        
        # self.menu = Menu(main, tearoff=0)
        # self.menu.add_command(label="Cut")
        # self.menu.add_command(label="Copy")
        # self.menu.add_command(label="Paste")
        # self.menu.add_command(label="Reload")
        # self.menu.add_separator()
        # self.menu.add_command(label="Rename")

        self.treeview.tag_configure('related_devices', background='lightgreen')
        self.treeview.tag_configure('blinking', background='lightblue')

        # self.treeview.bind('<ButtonRelease-1>', self.on_selected)
        self.treeview.bind('<<TreeviewSelect>>', self.on_selected)
        # self.treeview.bind("<Button-3>", self.show_context_menu)

        self.check_if_wireless_network_exists()

        self.current_data_filter:DataFilter = None
        self.app_bus = app_bus
        self.app_bus.add_event_handler(AppBusEventType.DEVICE_SCAN_STATUS, self.device_scan_status_handler)
        self.app_bus.add_event_handler(AppBusEventType.UPDATE_DEVICE_REPRESENTATION, self.update_device_representation_handler)
        self.app_bus.add_event_handler(AppBusEventType.UPDATE_SENSOR_REPRESENTATION, self.update_sensor_representation_handler)
        self.app_bus.add_event_handler(AppBusEventType.LOAD_FILE, self._reset)
        self.app_bus.add_event_handler(AppBusEventType.SET_DATA_TABLE_FILTER, self._set_data_filter_handler)
        self.app_bus.add_event_handler(AppBusEventType.SERIAL_CALLBACK, self._serial_callback_handler)

        self.data_manager = data_manager

        # initial loading
        if self.data_manager.selected_data_filter_name is not None:
            self._set_data_filter_handler(self.data_manager.data_fitlers[self.data_manager.selected_data_filter_name])
        for d in self.data_manager.devices.values():
            parent = self.NON_BUS_DEVICE_LABEL if not d.is_bus_device() else None
            self.update_device_handler(d, parent)

    def _set_data_filter_handler(self, filter):
        self.current_data_filter = filter

        self._reset(None)
        for d in self.data_manager.devices.values():
            if d.bus_device:
                self.update_device_handler(d)
            else:
                self.update_device_handler(d, parent=self.NON_BUS_DEVICE_LABEL)

    def _reset(self, data):
        for item in self.treeview.get_children():
            self.treeview.delete(item)
        self.check_if_wireless_network_exists()

    def on_selected(self, event):
        device_external_id = self.treeview.focus()
        device = self.data_manager.get_device_by_id(device_external_id)
        if device is not None:
            self.app_bus.fire_event(AppBusEventType.SELECTED_DEVICE, device)

        self.mark_related_elements(device_external_id)


    def mark_related_elements(self, device_external_id:str) -> None:
        for iid in self.treeview.tag_has( 'related_devices' ):
            self.treeview.item( iid, tags=() )

        devices = self.data_manager.get_related_devices(device_external_id)
        for d in devices:
            if self.treeview.exists(d.external_id):
                self.treeview.item(d.external_id, tags=('related_devices'))


    def show_context_menu(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def insert_device(self, device:Device):
        v=("", b2s(device.address[0]), "", "")
        self.treeview.insert(parent="", index="end", text=device.id_string, values=v)
        
    def device_scan_status_handler(self, status:str):
        if status in ['STARTED']:
            #TODO: disable treeview or menue of it
            # self.treeview.config(state=DISABLED)
            pass
        elif status in ['FINISHED']:
            #TODO: enable treeview or menue of it
            # self.treeview.config(state=NORMAL)
            pass


    def add_fam14(self, d:Device):
        if d.is_fam14():
            if not self.treeview.exists(d.base_id):
                text = ""
                comment = ""
                text = d.name
                comment = d.comment if d.comment is not None else "" 
                in_ha = d.use_in_ha
                self.treeview.insert(parent="", index=0, iid=d.external_id, text=text, values=("", "", "", "", comment, in_ha, "", "", ""), open=True)
            else:
                self.treeview.item(d.base_id, text=d.name, values=("", "", "", "", d.comment, d.use_in_ha, "", "", "") )


    def check_if_wireless_network_exists(self):
        id = self.NON_BUS_DEVICE_LABEL
        if not self.treeview.exists(id):
            self.treeview.insert(parent="", index="end", iid=id, text=self.NON_BUS_DEVICE_LABEL, values=("", "", "", "", "", "", "", "", ""), open=True)


    def update_device_representation_handler(self, d:Device):
        self.update_device_handler(d)


    def update_device_handler(self, d:Device, parent:str=None):

        if self.current_data_filter is not None and not self.current_data_filter.filter_device(d):
            return

        if not d.is_fam14():
            in_ha = d.use_in_ha
            ha_pl = "" if d.ha_platform is None else d.ha_platform
            eep = "" if d.eep is None else d.eep
            device_type = "" if d.device_type is None else d.device_type
            key_func = "" if d.key_function is None else d.key_function
            comment = "" if d.comment is None else d.comment
            sender_adr = "" if 'sender' not in d.additional_fields else d.additional_fields['sender'][CONF_ID]
            sender_eep = "" if 'sender' not in d.additional_fields else d.additional_fields['sender'][CONF_EEP]
            _parent = d.base_id if parent is None else parent
            if not self.treeview.exists(_parent): self.add_fam14(self.data_manager.devices[_parent])
            if not self.treeview.exists(d.external_id):
                self.treeview.insert(parent=_parent, index="end", iid=d.external_id, text=d.name, values=(d.address, d.external_id, device_type, key_func, comment, in_ha, ha_pl, eep, sender_adr, sender_eep), open=True)
            else:
                # update device
                self.treeview.item(d.external_id, text=d.name, values=(d.address, d.external_id, device_type, key_func, comment, in_ha, ha_pl, eep, sender_adr, sender_eep), open=True)
                if self.treeview.parent(d.external_id) != _parent:
                    self.treeview.move(d.external_id, _parent, 0)
        else:
            self.add_fam14(d)

        # self.trigger_blinking(d.external_id)

    def _serial_callback_handler(self, data:dict):
        message:EltakoMessage = data['msg']
        current_base_id:str = data['base_id']

        if type(message) in [RPSMessage, Regular1BSMessage, Regular4BSMessage, EltakoWrappedRPS]:
            if isinstance(message.address, int):
                adr = data_helper.a2s(message.address)
            else: 
                adr = b2s(message.address)

            if not adr.startswith('00-00-00-'):
                self.trigger_blinking(adr)
            elif current_base_id is not None:
                d:Device = self.data_manager.find_device_by_local_address(adr, current_base_id)
                if d is not None:
                    self.trigger_blinking(d.external_id)

    def trigger_blinking(self, external_id:str):
        if not self.blinking_enabled:
            return
        
        def blink(ext_id:str):
            for i in range(0,2):
                if self.treeview.exists(ext_id):
                    tags = self.treeview.item(ext_id)['tags']
                    if 'blinking' in tags:
                        if isinstance(tags, str):
                            self.treeview.item(ext_id, tags=() )
                        else:
                            tags.remove('blinking')
                            self.treeview.item(ext_id, tags=tags )
                    else:
                        if isinstance(tags, str):
                            self.treeview.item(ext_id, tags=('blinking') )
                        else:
                            tags.append('blinking')
                            self.treeview.item(ext_id, tags=tags )
                    time.sleep(.5)

            if self.treeview.exists(ext_id):
                tags = self.treeview.item(ext_id)['tags']
                if 'blinking' in tags:
                    if isinstance(tags, str):
                        self.treeview.item(ext_id, tags=() )
                    else:
                        tags.remove('blinking')
                        self.treeview.item(ext_id, tags=tags )

        t = threading.Thread(target=lambda ext_id=external_id: blink(ext_id))
        t.start()


    def update_sensor_representation_handler(self, d:Device):
        self.update_device_handler(d, parent=self.NON_BUS_DEVICE_LABEL)