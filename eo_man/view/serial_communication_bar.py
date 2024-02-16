import tkinter as tk
from tkinter import *
from tkinter import ttk
from idlelib.tooltip import Hovertip
import threading

from eo_man import LOGGER

from ..controller.app_bus import AppBus, AppBusEventType
from ..controller.serial_controller import SerialController
from ..data.data_manager import DataManager, Device

class SerialConnectionBar():

    def __init__(self, main: Tk, app_bus:AppBus, data_manager:DataManager, row:int):
        self.main = main
        self.app_bus = app_bus
        self.data_manager = data_manager
        self.serial_cntr = SerialController(app_bus)

        f = LabelFrame(main, text="Serial Connection", bd=1)#, relief=SUNKEN)
        f.grid(row=row, column=0, columnspan=1, sticky=W+E+N+S, pady=(0,2), padx=2)

        self.b_detect = Button(f, text="Detect Serial Ports")
        self.b_detect.pack(side=tk.LEFT, padx=(5, 5), pady=5)
        self.b_detect.config(command=self.detect_serial_ports_command)
        Hovertip(self.b_detect,"Serial port detection is sometime unstable. Please try again if device was not detected.",300)

        l = Label(f, text="Gateway Type: ")
        l.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self.cb_device_type = ttk.Combobox(f, state="readonly", width="12") 
        self.cb_device_type.pack(side=tk.LEFT, padx=(0, 5), pady=5)
        self.cb_device_type['values'] = ['FAM14', 'FGW14-USB', 'FAM-USB']
        self.cb_device_type.set(self.cb_device_type['values'][0])
        self.cb_device_type.bind('<<ComboboxSelected>>', self.on_device_type_changed)

        l = Label(f, text="Serial Port: ")
        l.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self.cb_serial_ports = ttk.Combobox(f, state="readonly", width="10") 
        self.cb_serial_ports.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self.b_connect = Button(f, text="Connect", state=DISABLED, command=self.toggle_serial_connection_command)
        self.b_connect.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        s = ttk.Separator(f, orient=VERTICAL )
        s.pack(side=tk.LEFT, padx=(0,5), pady=0, fill="y")

        self.b_scan = Button(f, text="Scan for devices", state=DISABLED, command=self.scan_for_devices)
        self.b_scan.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self.overwrite = tk.BooleanVar()
        self.cb_overwrite = Checkbutton(f, text="Overwrite existing values", variable=self.overwrite)
        self.cb_overwrite.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        s = ttk.Separator(f, orient=VERTICAL )
        s.pack(side=tk.LEFT, padx=(0,5), pady=0, fill="y")

        self.b_sync_ha_sender = Button(f, text="Write HA senders to devices", state=DISABLED, command=self.write_ha_senders_to_devices)
        Hovertip(self.b_sync_ha_sender,"Ensures sender configuration for Home Assistant is written into device memory.",300)
        self.b_sync_ha_sender.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self.app_bus.add_event_handler(AppBusEventType.CONNECTION_STATUS_CHANGE, self.is_connected_handler)
        self.app_bus.add_event_handler(AppBusEventType.DEVICE_SCAN_STATUS, self.device_scan_status_handler)
        self.app_bus.add_event_handler(AppBusEventType.WRITE_SENDER_IDS_TO_DEVICES_STATUS, self.device_scan_status_handler)
        self.app_bus.add_event_handler(AppBusEventType.WINDOW_LOADED, self.on_window_loaded)
        

    def on_device_type_changed(self, event):
        self.cb_serial_ports['values'] = []
        self.cb_serial_ports.set('')

        self.detect_serial_ports_command()


    def write_ha_senders_to_devices(self):
        sender_list = {}
        for dev in self.data_manager.devices.values():
            sender_list[dev.external_id] = dev.additional_fields
        self.serial_cntr.write_sender_id_to_devices(45056, sender_list)
        

    def on_window_loaded(self, data):
        self.detect_serial_ports_command()


    def scan_for_devices(self):
        self.serial_cntr.scan_for_devices( self.overwrite.get() )


    def device_scan_status_handler(self, status:str):
        if status == 'FINISHED':
            self.is_connected_handler({'connected': self.serial_cntr.is_serial_connection_active()})
            self.main.config(cursor="")
            self.b_scan.config(state=NORMAL)
            self.b_connect.config(state=NORMAL)
            self.b_sync_ha_sender.config(state=NORMAL)
        if status == 'STARTED':
            self.b_scan.config(state=DISABLED)
            self.b_connect.config(state=DISABLED)
            self.main.config(cursor="watch")    #set cursor for waiting
            self.b_sync_ha_sender.config(state=DISABLED)


    def toggle_serial_connection_command(self):
        try:
            if not self.serial_cntr.is_serial_connection_active():
                self.b_detect.config(state=DISABLED)
                self.b_connect.config(state=DISABLED)
                self.b_scan.config(state=DISABLED)
                self.serial_cntr.establish_serial_connection(self.cb_serial_ports.get(), self.cb_device_type.get())
            else:
                self.serial_cntr.stop_serial_connection()
        except:
            # reset buttons
            self.is_connected_handler(data={'connected': self.serial_cntr.is_serial_connection_active()})
            LOGGER.exception("Was not able to detect serial ports.")


    def is_connected_handler(self, data:dict, skipp_serial_port_detection:bool=False):
        status = data.get('connected')
        
        self.main.config(cursor="")

        if status:
            self.b_connect.config(text="Disconnect", state=NORMAL)
            self.cb_serial_ports.config(state=DISABLED)
            self.b_detect.config(state=DISABLED)
            self.cb_device_type.config(state=DISABLED)
            
            if self.serial_cntr.is_fam14_connection_active():
                self.b_scan.config(state=NORMAL)
                self.b_sync_ha_sender.config(state=NORMAL)
            else:
                self.b_scan.config(state=DISABLED)
                self.b_sync_ha_sender.config(state=DISABLED)

        else:
            self.b_connect.config(text="Connect", state=NORMAL)
            self.b_detect.config(state=NORMAL)
            self.cb_serial_ports.config(state="readonly")
            self.cb_device_type.config(state="readonly")
            self.b_scan.config(state=DISABLED)
            self.b_sync_ha_sender.config(state=DISABLED)
            if not skipp_serial_port_detection: self.detect_serial_ports_command()


    def detect_serial_ports_command(self):

        def detect_serial_ports():
            try:
                self.main.config(cursor="watch")    #set cursor for waiting
                self.b_detect.config(state=DISABLED)
                serial_ports = self.serial_cntr.get_serial_ports(self.cb_device_type.get())
                self.cb_serial_ports['values'] = serial_ports
                if len(self.cb_serial_ports['values']) > 0:
                    self.cb_serial_ports.set(self.cb_serial_ports['values'][0])
                    self.b_connect.config(state=NORMAL)
                else:
                    self.b_connect.config(state=DISABLED)
                    self.cb_serial_ports.set('')
            except:
                # reset buttons
                LOGGER.exception("Was not able to detect serial ports.")
            else:
                self.is_connected_handler(data={'connected': False}, skipp_serial_port_detection=True)

        t = threading.Thread(target=detect_serial_ports)
        t.start()