from typing import Dict, List

import tkinter as tk
from tkinter import *
from tkinter import ttk
from idlelib.tooltip import Hovertip
import threading

from eo_man import LOGGER

from ..controller.app_bus import AppBus, AppBusEventType
from ..controller.serial_controller import SerialController
from ..data.data_manager import DataManager
from ..data import data_helper
from ..data.data_helper import get_gateway_type_by_name

from eltakobus.message import *
from eltakobus.eep import *
from eltakobus.util import *

from ..data.const import get_display_names, GATEWAY_DISPLAY_NAMES, GatewayDeviceType
from ..data.const import GATEWAY_DISPLAY_NAMES as GDN

class SerialConnectionBar():

    def __init__(self, main: Tk, app_bus:AppBus, data_manager:DataManager, serial_controller:SerialController, row:int):
        self.main = main
        self.app_bus = app_bus
        self.data_manager = data_manager
        self.serial_cntr = serial_controller

        self.endpoint_list:Dict[str, List[str]]={}

        f = LabelFrame(main, text="Serial Connection", bd=1)#, relief=SUNKEN)
        f.grid(row=row, column=0, columnspan=1, sticky=W+E+N+S, pady=(0,2), padx=2)

        self.b_detect = ttk.Button(f, text="Detect Serial Ports")
        self.b_detect.pack(side=tk.LEFT, padx=(5, 5), pady=5)
        self.b_detect.config(command=lambda : self.detect_serial_ports_command(force_reload=True) )
        Hovertip(self.b_detect,"Serial port detection is sometime unstable. Please try again if device was not detected.",300)

        l = Label(f, text="Gateway Type: ")
        l.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self.cb_device_type = ttk.Combobox(f, state="readonly", width="18") 
        self.cb_device_type.pack(side=tk.LEFT, padx=(0, 5), pady=5)
        self.cb_device_type['values'] = get_display_names() # ['FAM14', 'FGW14-USB', 'FAM-USB', 'USB300', 'LAN Gateway']
        self.cb_device_type.set(self.cb_device_type['values'][0])
        self.cb_device_type.bind('<<ComboboxSelected>>', self.on_device_type_changed)

        l = ttk.Label(f, text="Serial Port: ")
        l.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self.cb_serial_ports = ttk.Combobox(f, state=NORMAL, width="14") 
        self.cb_serial_ports.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self.b_connect = ttk.Button(f, text="Connect", state=NORMAL, command=self.toggle_serial_connection_command)
        self.b_connect.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        s = ttk.Separator(f, orient=VERTICAL )
        s.pack(side=tk.LEFT, padx=(0,5), pady=0, fill="y")

        self.b_scan = ttk.Button(f, text="Scan for devices", state=DISABLED, command=self.scan_for_devices)
        self.b_scan.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self.overwrite = tk.BooleanVar()
        self.cb_overwrite = ttk.Checkbutton(f, text="Overwrite existing values", variable=self.overwrite)
        self.cb_overwrite.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        s = ttk.Separator(f, orient=VERTICAL )
        s.pack(side=tk.LEFT, padx=(0,5), pady=0, fill="y")

        text  = "Ensures sender configuration for Home Assistant is written into device memory.\n"
        text += "* Gateways will be added when being once connected.\n"
        text += "* Only devices connected to FAM14 via wire will be updated.\n"
        text += "* Button will be enabled when FAM14 is connected."

        l = ttk.Label(f, text="Program HA senders into devices: ")
        Hovertip(l, text, 300)
        l.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self.cb_gateways_for_HA = ttk.Combobox(f, state="readonly", width="24") 
        Hovertip(self.cb_gateways_for_HA, text, 300)
        self.cb_gateways_for_HA.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self.b_sync_ha_sender = ttk.Button(f, text="Write to devices", state=DISABLED, command=self.write_ha_senders_to_devices)
        Hovertip(self.b_sync_ha_sender, text, 300)
        self.b_sync_ha_sender.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        # # if connected via fam14 force to get status update message
        # b = ttk.Button(f, text="Send Poll", command=lambda: self.serial_cntr.send_message(EltakoPollForced(5)))
        # b.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self.app_bus.add_event_handler(AppBusEventType.CONNECTION_STATUS_CHANGE, self.is_connected_handler)
        self.app_bus.add_event_handler(AppBusEventType.DEVICE_SCAN_STATUS, self.device_scan_status_handler)
        self.app_bus.add_event_handler(AppBusEventType.WRITE_SENDER_IDS_TO_DEVICES_STATUS, self.device_scan_status_handler)
        self.app_bus.add_event_handler(AppBusEventType.WINDOW_LOADED, self.on_window_loaded)
        self.app_bus.add_event_handler(AppBusEventType.UPDATE_DEVICE_REPRESENTATION, self.update_cb_gateways_for_HA)
        self.app_bus.add_event_handler(AppBusEventType.UPDATE_SENSOR_REPRESENTATION, self.update_cb_gateways_for_HA)
        self.app_bus.add_event_handler(AppBusEventType.SERVICE_ENDPOINTS_UPDATES, self.update_service_endpoints)
        

    def update_cb_gateways_for_HA(self, event=None):
        gateways = []
        for d in self.data_manager.devices.values():
            if d.is_gateway():
                gateways.append(f"{d.device_type.replace(' (Wireless Transceiver)', '')} ({d.external_id})")
        
        self.cb_gateways_for_HA['values'] = gateways
        if self.cb_gateways_for_HA.get() == '' and len(gateways) > 0:
            self.cb_gateways_for_HA.set(gateways[0])
        elif len(gateways) == 0:
            self.cb_gateways_for_HA.set('')

    def on_device_type_changed(self, event):
        self.cb_serial_ports['values'] = []
        self.cb_serial_ports.set('')

        self.update_combobox_serial_port()


    def write_ha_senders_to_devices(self):
        # get gateways and its base id
        baseId = self.cb_gateways_for_HA.get().split(' ')[-1].replace('(', '').replace(')', '')
        g = self.data_manager.devices.get(baseId, None)
        if g.is_wired_gateway():
            sender_base_id = '00-00-B0-00'
        else:
            sender_base_id = g.base_id

        # get sender list to be entered
        sender_list = {}
        for d in self.data_manager.devices.values():
            if d.base_id == self.serial_cntr.current_base_id and d.use_in_ha:
                if 'sender' in d.additional_fields:
                    sender_list[d.external_id] = dict(d.additional_fields)
                    sender_id = data_helper.a2i(sender_base_id) + data_helper.a2i(d.address)
                    sender_list[d.external_id]['sender']['id'] =  data_helper.a2s(sender_id)

        self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {
            'msg': f'Write sender ids to devices for gateway {self.cb_gateways_for_HA.get()} with sender base id {sender_base_id} on bus with base id {self.serial_cntr.current_base_id}',
            'color': 'lightgreen'})
        self.serial_cntr.write_sender_id_to_devices(sender_list)
        

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
            
            if self.cb_device_type.get() == GATEWAY_DISPLAY_NAMES[GatewayDeviceType.EltakoFAM14] and self.serial_cntr.is_fam14_connection_active():
                self.b_scan.config(state=NORMAL)
                self.b_sync_ha_sender.config(state=NORMAL)
            else:
                self.b_scan.config(state=DISABLED)
                self.b_sync_ha_sender.config(state=DISABLED)

        else:
            self.b_connect.config(text="Connect", state=NORMAL)
            self.b_detect.config(state=NORMAL)
            if self.cb_device_type.get() in [GDN[GatewayDeviceType.LAN], GDN[GatewayDeviceType.LAN_ESP2]]:
                self.cb_serial_ports.config(state=NORMAL)
            else:
                self.cb_serial_ports.config(state='readonly')
            self.cb_device_type.config(state="readonly")
            self.b_scan.config(state=DISABLED)
            self.b_sync_ha_sender.config(state=DISABLED)
            if not skipp_serial_port_detection: self.detect_serial_ports_command()

    def update_service_endpoints(self, data:Dict[str, List[str]]=None):

        self.endpoint_list = data
        self.update_combobox_serial_port()

    def update_combobox_serial_port(self):

        self.b_detect.config(state=NORMAL)
        self.cb_device_type.config(state="readonly")
        try:
            self.cb_serial_ports['values'] = self.endpoint_list[get_gateway_type_by_name(self.cb_device_type.get())]
            if len(self.cb_serial_ports['values']) > 0:
                self.cb_serial_ports.set(self.cb_serial_ports['values'][0])
                self.b_connect.config(state=NORMAL)
                self.cb_serial_ports.config(state=NORMAL)
            else:
                # self.b_connect.config(state=DISABLED)
                self.cb_serial_ports.config(state=NORMAL)
                self.cb_serial_ports.set('')
        except:
            # self.b_connect.config(state=DISABLED)
            self.cb_serial_ports.config(state=NORMAL)
            self.cb_serial_ports.set('')
            
        self.main.config(cursor="")

    def detect_serial_ports_command(self, force_reload:bool=False):

        self.main.config(cursor="watch")    #set cursor for waiting
        self.b_detect.config(state=DISABLED)
        self.b_connect.config(state=DISABLED)
        self.cb_device_type.config(state=DISABLED)
        self.cb_serial_ports.config(state=DISABLED)
        self.app_bus.fire_event(AppBusEventType.REQUEST_SERVICE_ENDPOINT_DETECTION, force_reload)

        # def detect_serial_ports():
        #     try:
        #         self.main.config(cursor="watch")    #set cursor for waiting
        #         self.b_detect.config(state=DISABLED)
        #         self.b_connect.config(state=DISABLED)
        #         self.cb_device_type.config(state=DISABLED)
        #         self.cb_serial_ports.config(state=DISABLED)
        #         self.app_bus.fire_event(AppBusEventType.REQUEST_SERVICE_ENDPOINT_DETECTION, None)
        #         serial_ports = self.serial_cntr.get_serial_ports(self.cb_device_type.get(), force_reload)
        #         self.b_detect.config(state=NORMAL)
        #         self.cb_device_type.config(state=NORMAL)
        #         self.cb_serial_ports['values'] = serial_ports
        #         if len(self.cb_serial_ports['values']) > 0:
        #             self.cb_serial_ports.set(self.cb_serial_ports['values'][0])
        #             self.b_connect.config(state=NORMAL)
        #         else:
        #             self.b_connect.config(state=DISABLED)
        #             self.cb_serial_ports.set('')
        #     except:
        #         # reset buttons
        #         LOGGER.exception("Was not able to detect serial ports.")
        #     else:
        #         self.is_connected_handler(data={'connected': False}, skipp_serial_port_detection=True)

        # t = threading.Thread(target=detect_serial_ports)
        # t.start()