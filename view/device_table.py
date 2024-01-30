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
from eltakobus.eep import EEP
from data import DataManager, Device, add_addresses, a2s


class DeviceTable():

    NON_BUS_DEVICE_LABEL:str="Distributed Devices"

    def __init__(self, main: Tk, controller:AppController, data_manager:DataManager):
        
        self.pane = ttk.Frame(main, padding=2)
        # self.pane_1.grid(row=1, column=0, sticky="nsew", columnspan=3)
        self.root = self.pane

        # Scrollbar
        self.scrollbar = ttk.Scrollbar(self.pane)
        self.scrollbar.pack(side="right", fill="y")

        # Treeview
        columns = ("Address", "External Address", "Device Type", "Comment", "Export to HA Config", "HA Platform", "Device EEP", "Sender Address", "Sender EEP")
        self.treeview = ttk.Treeview(
            self.pane,
            selectmode="browse",
            yscrollcommand=self.scrollbar.set,
            columns=(0,1,2,3,4,5,6,7,8),
            height=10,
        )
        self.treeview.pack(expand=True, fill="both")
        self.scrollbar.config(command=self.treeview.yview)

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

        for col in columns:
            # Treeview headings
            i = columns.index(col)
            if col in ['Comment']:
                self.treeview.column(i, anchor="w", width=250)
            else:
                self.treeview.column(i, anchor="w", width=80)
            self.treeview.heading(i, text=col, anchor="center", command=lambda c=col, d=False: sort_treeview(self.treeview, c, d))
        
        self.menu = Menu(main, tearoff=0)
        self.menu.add_command(label="Cut")
        self.menu.add_command(label="Copy")
        self.menu.add_command(label="Paste")
        self.menu.add_command(label="Reload")
        self.menu.add_separator()
        self.menu.add_command(label="Rename")

        self.treeview.tag_configure('related_devices', background='lightgreen')

        # self.treeview.bind('<ButtonRelease-1>', self.on_selected)
        self.treeview.bind('<<TreeviewSelect>>', self.on_selected)
        self.treeview.bind("<Button-3>", self.show_context_menu)

        self.check_if_wireless_network_exists()

        self.controller = controller
        self.controller.add_event_handler(ControllerEventType.DEVICE_SCAN_STATUS, self.device_scan_status_handler)
        self.controller.add_event_handler(ControllerEventType.UPDATE_DEVICE_REPRESENTATION, self.update_device_representation_handler)
        self.controller.add_event_handler(ControllerEventType.UPDATE_SENSOR_REPRESENTATION, self.update_sensor_representation_handler)
        self.controller.add_event_handler(ControllerEventType.LOAD_FILE, self._reset)

        self.data_manager = data_manager

    def _reset(self, data):
        for item in self.treeview.get_children():
            self.treeview.delete(item)
        self.check_if_wireless_network_exists()

    def on_selected(self, event):
        device_external_id = self.treeview.focus()
        device = self.data_manager.get_device_by_id(device_external_id)
        if device is not None:
            self.controller.fire_event(ControllerEventType.SELECTED_DEVICE, device)

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
                self.treeview.insert(parent="", index=0, iid=d.external_id, text=text, values=("", "", "", comment, in_ha, "", "", ""), open=True)
            else:
                self.treeview.item(d.base_id, text=d.name, values=("", "", "", d.comment, d.use_in_ha, "", "", "") )


    def check_if_wireless_network_exists(self):
        id = self.NON_BUS_DEVICE_LABEL
        if not self.treeview.exists(id):
            self.treeview.insert(parent="", index="end", iid=id, text=self.NON_BUS_DEVICE_LABEL, values=("", "", "", "", "", "", "", ""), open=True)


    def update_device_representation_handler(self, d:Device):
        self.update_device_handler(d)


    def update_device_handler(self, d:Device, parent:str=None):

        if not d.is_fam14():
            in_ha = d.use_in_ha
            ha_pl = "" if d.ha_platform is None else d.ha_platform
            eep = "" if d.eep is None else d.eep
            device_type = "" if d.device_type is None else d.device_type
            comment = "" if d.comment is None else d.comment
            sender_adr = "" if 'sender' not in d.additional_fields else d.additional_fields['sender'][CONF_ID]
            sender_eep = "" if 'sender' not in d.additional_fields else d.additional_fields['sender'][CONF_EEP]
            _parent = d.base_id if parent is None else parent
            if not self.treeview.exists(d.external_id):
                self.treeview.insert(parent=_parent, index="end", iid=d.external_id, text=d.name, values=(d.address, d.external_id, device_type, comment, in_ha, ha_pl, eep, sender_adr, sender_eep), open=True)
            else:
                # update device
                self.treeview.item(d.external_id, text=d.name, values=(d.address, d.external_id, device_type, comment, in_ha, ha_pl, eep, sender_adr, sender_eep), open=True)
                if self.treeview.parent(d.external_id) != _parent:
                    self.treeview.move(d.external_id, _parent, 0)
        else:
            self.add_fam14(d)
        

    def update_sensor_representation_handler(self, d:Device):
        self.update_device_handler(d, parent=self.NON_BUS_DEVICE_LABEL)