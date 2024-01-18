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
from data import DataManager, Device


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
        columns = ("Address", "External Address", "Device Type", "Comment")
        self.treeview = ttk.Treeview(
            self.pane,
            selectmode="browse",
            yscrollcommand=self.scrollbar.set,
            columns=(0,1,2,3,4),
            height=10,
        )
        self.treeview.pack(expand=True, fill="both")
        self.scrollbar.config(command=self.treeview.yview)

        def sort_treeview(tree, col, descending):
            data = [(tree.set(item, col), item) for item in tree.get_children('')]
            data.sort(reverse=descending)
            for index, (val, item) in enumerate(data):
                tree.move(item, '', index)
            tree.heading(col, command=lambda: sort_treeview(tree, col, not descending))

        for col in columns:
            # Treeview headings
            i = columns.index(col)
            self.treeview.column(i, anchor="w", width=100)
            self.treeview.heading(i, text=col, anchor="center", command=lambda c=col: sort_treeview(self.treeview, c, False))
        
        self.menu = Menu(main, tearoff=0)
        self.menu.add_command(label="Cut")
        self.menu.add_command(label="Copy")
        self.menu.add_command(label="Paste")
        self.menu.add_command(label="Reload")
        self.menu.add_separator()
        self.menu.add_command(label="Rename")

        self.treeview.bind('<ButtonRelease-1>', self.on_selected)
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
        device_id = self.treeview.focus()
        device = self.data_manager.get_device_by_id(device_id)
        if device is not None:
            self.controller.fire_event(ControllerEventType.SELECTED_DEVICE, device)

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

    def check_if_bus_element_exists(self, d:Device):
        if not self.treeview.exists(d.base_id):
            text = ""
            comment = ""
            if d.is_fam14():
                text = d.name
                comment = d.comment
            self.treeview.insert(parent="", index=0, iid=d.external_id, text=text, values=("", "", "", comment), open=True)
        
        elif d.is_fam14():
            self.treeview.item(d.base_id, text=d.name, values=("", "", "", d.comment) )

    def check_if_wireless_network_exists(self):
        id = self.NON_BUS_DEVICE_LABEL
        if not self.treeview.exists(id):
            self.treeview.insert(parent="", index="end", iid=id, text=self.NON_BUS_DEVICE_LABEL, values=("", "", ""), open=True)

    def add_function_group(self, external_dev_id:str, func_group_id:str) -> str:
        fg_id = f"{external_dev_id}_{func_group_id}"
        if not self.treeview.exists(fg_id):
            text = "Function Group: "+str(func_group_id)
            self.treeview.insert(parent=external_dev_id, index="end", iid=fg_id, text=text, values=("", "", ""), open=True)
        return fg_id

    def update_device_representation_handler(self, d:Device):
        self.check_if_bus_element_exists(d)

        if not d.is_fam14():
            if not self.treeview.exists(d.external_id):
                self.treeview.insert(parent=d.base_id, index="end", iid=d.external_id, text=d.name, values=(d.address, d.external_id, d.device_type, d.comment), open=True)
            else:
                # update device
                self.treeview.item(d.external_id, text=d.name, values=(d.address, d.external_id, d.device_type, d.comment), open=True)
                if self.treeview.parent(d.external_id) != d.base_id:
                    self.treeview.move(d.external_id, d.base_id, 0)


        # fam14_base_id:str = data['fam14_base_id']
        # device:dict = data['device']
        # is_fam14 = device[CONF_ID] == '00-00-00-FF'
        # external_id = device[CONF_EXTERNAL_ID]
        
        # self.check_if_bus_element_exists(fam14_base_id)
        
        # if not is_fam14 and not self.treeview.exists(external_id):
        #     id = device[CONF_ID]
        #     name = device[CONF_NAME]
        #     text = f"{name}<{id}>"
        #     comment = device.get(CONF_COMMENT, '')
        #     self.treeview.insert(parent=fam14_base_id, index="end", iid=external_id, text=text, values=(id, external_id, name, comment), open=True)

        #     for ml in device[CONF_MEMORY_ENTRIES]:
        #         fg_id = self.add_function_group(external_id, ml.in_func_group)
        #         ml_id = f"mem_line_{external_id}_{ml.memory_line}"
        #         text = "Mem Entry: "+str(ml.memory_line)
        #         name = KeyFunction(ml.key_func).name
        #         comment = ""
        #         self.treeview.insert(parent=fg_id, index="end", iid=ml_id, text=text, values=(ml.sensor_id_str, ml.sensor_id_str, name, comment), open=True)
        

    def update_sensor_representation_handler(self, d:Device):

        if not self.treeview.exists(d.external_id):
            self.treeview.insert(parent=self.NON_BUS_DEVICE_LABEL, index="end", iid=d.external_id, text=d.name, values=("", d.external_id, d.device_type, d.comment), open=True)
        else:
            self.treeview.item(d.external_id, text=d.name, values=("", d.external_id, d.device_type, d.comment) )

        # id = sensor[CONF_ID]
        # ext_id = sensor.get(CONF_EXTERNAL_ID, id)
        # base_id = sensor.get(CONF_BASE_ID, None)
        # if base_id is None and not self.treeview.exists(ext_id):
        #     name = sensor.get(CONF_NAME, '')
        #     text = f"{name}<{id}>"
        #     comment = sensor.get(CONF_COMMENT, '')
        #     self.treeview.insert(parent=self.NON_BUS_DEVICE_LABEL, index="end", iid=ext_id, text=text, values=(id, ext_id, name, comment))
        
        # ext_dev_ids = sensor.get(CONF_CONFIGURED_IN_DEVICES, [])
        # for ext_dev_id in ext_dev_ids:
        #     unique_id = f"{ext_id}_{ext_dev_id}"
        #     if not self.treeview.exists(unique_id):
        #         name = sensor.get(CONF_NAME, '')
        #         text = f"{name}<{id}>"
        #         comment = sensor.get(CONF_COMMENT, '')
        #         self.treeview.insert(parent=ext_dev_id, index="end", iid=unique_id, text=text, values=(id, ext_id, name, comment))