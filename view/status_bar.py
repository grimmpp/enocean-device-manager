import tkinter as tk
from tkinter import *
from tkinter import ttk

from controller import AppController, ControllerEventType
from data import DataManager

class StatusBar():

    
    def __init__(self, main: Tk, controller:AppController, data_manager:DataManager, row:int):
        self.controller = controller
        self.data_manager = data_manager
        
        f = Frame(main, bd=1, relief=SUNKEN)
        f.grid(row=row, column=0, columnspan=1, sticky=W+E+N+S)

        self.l_connected = Label(f, bd=1)
        self.l_connected.pack(side=tk.RIGHT, padx=(5, 5), pady=2)
        self.is_connected_handler({'connected':False})

        self.pb = ttk.Progressbar(f, orient=tk.HORIZONTAL, length=160, maximum=100)
        self.pb.pack(side=tk.RIGHT, padx=(5, 0), pady=2)
        self.pb.step(0)

        l = Label(f, text="Device Scan:")
        l.pack(side=tk.RIGHT, padx=(5, 0), pady=2)

        self.l_devices = Label(f, text=self.get_device_count_str())
        self.l_devices.pack(side=tk.LEFT, padx=(5, 0), pady=2)

        self.controller.add_event_handler(ControllerEventType.CONNECTION_STATUS_CHANGE, self.is_connected_handler)
        self.controller.add_event_handler(ControllerEventType.DEVICE_ITERATION_PROGRESS, self.device_scan_progress_handler)
        self.controller.add_event_handler(ControllerEventType.UPDATE_DEVICE_REPRESENTATION, self.update_device_count)
        self.controller.add_event_handler(ControllerEventType.UPDATE_SENSOR_REPRESENTATION, self.update_device_count)
        self.controller.add_event_handler(ControllerEventType.DEVICE_SCAN_STATUS, self.device_scan_status_handler)

    def get_device_count_str(self) -> str:
        count:int = len(self.data_manager.devices)
        fam14s:int = len([d for d in self.data_manager.devices.values() if d.is_fam14()])
        bus_device:int = len([d for d in self.data_manager.devices.values() if d.bus_device])
        decentralized:int = count-bus_device

        return f"Devices: {count}, FAM14s: {fam14s}, Bus Devices: {bus_device}, Decentralized Devices: {decentralized}"

    def update_device_count(self, data):
        self.l_devices.config(text=self.get_device_count_str())

    def device_scan_status_handler(self, status:str):
        if status in ['STARTED', 'FINISHED']:
            self.pb["value"] = 0

    def is_connected_handler(self, data:dict):
        status = data.get('connected')
        if status:
            self.l_connected.config(bg="lightgreen", fg="black", text="Connected")
        else:
            self.l_connected.config(bg="darkred", fg="white", text="Disconnected")

    def device_scan_progress_handler(self, progress:float):
        self.pb["value"] = progress