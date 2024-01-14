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
import tkinter.scrolledtext as ScrolledText
from const import *
from homeassistant.const import CONF_ID, CONF_NAME

from eltakobus.message import EltakoPoll, EltakoDiscoveryReply, EltakoDiscoveryRequest, EltakoMessage
from eltakobus.util import b2s
from eltakobus.device import KeyFunction, SensorInfo
from data import DataManager, Device

from view.menu_presenter import MenuPresenter

class ToolBar():
    # icon list
    # https://commons.wikimedia.org/wiki/Comparison_of_icon_sets
    def __init__(self, main: Tk, controller:AppController, data_manager:DataManager, row:int):
        self.main = main
        self.controller = controller
        self.data_manager = data_manager

        f = Frame(main, bd=1)#, relief=SUNKEN)
        f.grid(row=row, column=0, columnspan=1, sticky=W+E+N+S)

        b = self._create_img_button(f, "Save to current file", "icons/Oxygen480-actions-document-save.png")
        b = self._create_img_button(f, "Save as file", "icons/Oxygen480-actions-document-save-as.png")
        b = self._create_img_button(f, "Open file", "icons/Oxygen480-status-folder-open.png")
        b = self._create_img_button(f, "Export Home Assistant Configuration", "icons/Home_Assistant_Logo.png")
        b.config(command=self._export_home_assistant_configuration)

    def _export_home_assistant_configuration(self) -> None:
        filename = filedialog.asksaveasfile(
            initialdir=Path.home(), 
            title="Save Home Assistant Configuration File", 
            filetypes=(("configuration", "*.yaml"), ("all files", "*.*")))
        

    def _create_img_button(self, f:Frame, tooltip:str, img_filename:str) -> Button:
        img = Image.open(img_filename)
        img = img.resize((24, 24), Image.LANCZOS)
        eimg = ImageTk.PhotoImage(img)
        b = Button(f, image=eimg, relief=FLAT )
        Hovertip(b,tooltip,300)
        b.image = eimg
        b.pack(side=LEFT, padx=2, pady=2)
        return b


class SerialConnectionBar():

    def __init__(self, main: Tk, controller:AppController, row:int):
        self.main = main
        self.controller = controller

        f = LabelFrame(main, text="Serial Connection", bd=1)#, relief=SUNKEN)
        f.grid(row=row, column=0, columnspan=1, sticky=W+E+N+S)

        self.b_detect = Button(f, text="Detect")
        self.b_detect.pack(side=tk.LEFT, padx=(5, 5), pady=5)

        l = Label(f, text="Device Type: ")
        l.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self.cb_device_type = ttk.Combobox(f, state="readonly", width="12") 
        self.cb_device_type.pack(side=tk.LEFT, padx=(0, 5), pady=5)
        self.cb_device_type['values'] = ['FAM14', 'FGW14-USB', 'FAM-USB']
        self.cb_device_type.set(self.cb_device_type['values'][0])

        l = Label(f, text="Serial Port (FAM14): ")
        l.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self.cb_serial_ports = ttk.Combobox(f, state="readonly", width="10") 
        self.cb_serial_ports.pack(side=tk.LEFT, padx=(0, 5), pady=5)
        self.b_detect.config(command=self.detect_serial_ports_command)

        self.b_connect = Button(f, text="Connect", state=DISABLED, command=self.toggle_serial_connection_command)
        self.b_connect.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self.b_scan = Button(f, text="Scan for devices", state=DISABLED, command=self.scan_for_devices)
        self.b_scan.pack(side=tk.LEFT, padx=(0, 5), pady=5)

        self.controller.add_event_handler(ControllerEventType.CONNECTION_STATUS_CHANGE, self.is_connected_handler)
        self.controller.add_event_handler(ControllerEventType.DEVICE_SCAN_STATUS, self.device_scan_status_handler)
        self.controller.add_event_handler(ControllerEventType.WINDOW_LOADED, self.on_window_loaded)
        
        
    def on_window_loaded(self, data):
        self.detect_serial_ports_command()

    def scan_for_devices(self):
        self.b_scan.config(state=DISABLED)
        self.b_connect.config(state=DISABLED)
        self.controller.scan_for_devices()

    def device_scan_status_handler(self, status:str):
        if status == 'FINISHED':
            self.main.config(cursor="")
            self.b_scan.config(state=NORMAL)
            self.b_connect.config(state=NORMAL)
        if status == 'STARTED':
            self.main.config(cursor="watch")    #set cursor for waiting

    def toggle_serial_connection_command(self):
        if not self.controller.is_serial_connection_active():
            self.controller.establish_serial_connection(self.cb_serial_ports.get(), self.cb_device_type.get())
        else:
            self.controller.stop_serial_connection()

    def is_connected_handler(self, data:dict):
        status = data.get('connected')
        if status:
            self.b_connect.config(text="Disconnect")
            self.cb_serial_ports.config(state=DISABLED)
            self.b_detect.config(state=DISABLED)
            self.cb_device_type.config(state=DISABLED)
        else:
            self.b_connect.config(text="Connect")
            self.b_detect.config(state=NORMAL)
            self.cb_serial_ports.config(state="readonly")
            self.cb_device_type.config(state="readonly")
            self.detect_serial_ports_command()

        if self.controller.is_fam14_connection_active():
            self.b_scan.config(state=NORMAL)
        else:
            self.b_scan.config(state=DISABLED)

    def detect_serial_ports_command(self):
        serial_ports = self.controller.get_serial_ports(self.cb_device_type.get())
        self.cb_serial_ports['values'] = serial_ports
        if len(self.cb_serial_ports['values']) > 0:
            self.cb_serial_ports.set(self.cb_serial_ports['values'][0])
            self.b_connect.config(state=NORMAL)
        else:
            self.b_connect.config(state=DISABLED)
            self.cb_serial_ports.set('')


class StatusBar():

    def __init__(self, main: Tk, controller:AppController, row:int):
        self.controller = controller
        
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

        self.controller.add_event_handler(ControllerEventType.CONNECTION_STATUS_CHANGE, self.is_connected_handler)
        self.controller.add_event_handler(ControllerEventType.DEVICE_SCAN_PROGRESS, self.device_scan_progress_handler)
        self.controller.add_event_handler(ControllerEventType.DEVICE_SCAN_STATUS, self.device_scan_status_handler)

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


class DataTable():

    NON_BUS_DEVICE_LABEL:str="Distributed Devices"

    def __init__(self, main: Tk, controller:AppController, data_manager:DataManager):
        
        self.pane = ttk.Frame(main, padding=2)
        # self.pane_1.grid(row=1, column=0, sticky="nsew", columnspan=3)
        self.root = self.pane

        # Scrollbar
        self.scrollbar = ttk.Scrollbar(self.pane)
        self.scrollbar.pack(side="right", fill="y")

        # Treeview
        columns = ("Address", "External Address", "Name", "Comment")
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
            

        self.check_if_wireless_network_exists()

        self.controller = controller
        self.controller.add_event_handler(ControllerEventType.DEVICE_SCAN_STATUS, self.device_scan_status_handler)
        self.controller.add_event_handler(ControllerEventType.UPDATE_DEVICE_REPRESENTATION, self.update_device_representation_handler)
        self.controller.add_event_handler(ControllerEventType.UPDATE_SENSOR_REPRESENTATION, self.update_sensor_representation_handler)


    def insert_device(self, device:Device):
        v=("", b2s(device.id[0]), "", "")
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

    def check_if_bus_element_exists(self, fam14_base_id):
        if not self.treeview.exists(fam14_base_id):
            self.treeview.insert(parent="", index=0, iid=fam14_base_id, text=f"Bus on FAM14<{fam14_base_id}>", values=("", "", ""), open=True)

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

    def update_device_representation_handler(self, data:dict):
        fam14_base_id:str = data['fam14_base_id']
        device:dict = data['device']
        is_fam14 = device[CONF_ID] == '00-00-00-FF'
        external_id = device[CONF_EXTERNAL_ID]
        
        self.check_if_bus_element_exists(fam14_base_id)
        
        if not is_fam14 and not self.treeview.exists(external_id):
            id = device[CONF_ID]
            name = device[CONF_NAME]
            text = f"{name}<{id}>"
            comment = device.get(CONF_COMMENT, '')
            self.treeview.insert(parent=fam14_base_id, index="end", iid=external_id, text=text, values=(id, external_id, name, comment), open=True)

            for ml in device[CONF_MEMORY_ENTRIES]:
                fg_id = self.add_function_group(external_id, ml.in_func_group)
                ml_id = f"mem_line_{external_id}_{ml.memory_line}"
                text = "Mem Entry: "+str(ml.memory_line)
                name = KeyFunction(ml.key_func).name
                comment = ""
                self.treeview.insert(parent=fg_id, index="end", iid=ml_id, text=text, values=(ml.sensor_id_str, ml.sensor_id_str, name, comment), open=True)
        

    def update_sensor_representation_handler(self, sensor:dict):

        id = sensor[CONF_ID]
        ext_id = sensor.get(CONF_EXTERNAL_ID, id)
        base_id = sensor.get(CONF_BASE_ID, None)
        if base_id is None and not self.treeview.exists(ext_id):
            name = sensor.get(CONF_NAME, '')
            text = f"{name}<{id}>"
            comment = sensor.get(CONF_COMMENT, '')
            self.treeview.insert(parent=self.NON_BUS_DEVICE_LABEL, index="end", iid=ext_id, text=text, values=(id, ext_id, name, comment))
        
        # ext_dev_ids = sensor.get(CONF_CONFIGURED_IN_DEVICES, [])
        # for ext_dev_id in ext_dev_ids:
        #     unique_id = f"{ext_id}_{ext_dev_id}"
        #     if not self.treeview.exists(unique_id):
        #         name = sensor.get(CONF_NAME, '')
        #         text = f"{name}<{id}>"
        #         comment = sensor.get(CONF_COMMENT, '')
        #         self.treeview.insert(parent=ext_dev_id, index="end", iid=unique_id, text=text, values=(id, ext_id, name, comment))


class LogOutputPanel():

    def __init__(self, main: Tk, controller:AppController):
        self.controller = controller

        pane = ttk.Frame(main, padding=2)
        # pane.grid(row=2, column=0, sticky="nsew", columnspan=3)
        self.root = pane

        self.st = ScrolledText.ScrolledText(pane, border=3, height=10, state='disabled', bg='black', fg='lightgrey', font=('Arial', 14), padx=5, pady=5)
        self.st.configure(font='TkFixedFont')
        self.st.pack(expand=True, fill="both")
        # self.st.grid(row=2, column=0, sticky="nsew", columnspan=3)

        controller.add_event_handler(ControllerEventType.SERIAL_CALLBACK, self.serial_callback)
        controller.add_event_handler(ControllerEventType.LOG_MESSAGE, self.receive_log_message)

    def serial_callback(self, data):
        if type(data) not in [EltakoPoll, EltakoDiscoveryReply, EltakoDiscoveryRequest]:
            self.receive_log_message({'msg': str(data), 'color': 'darkgrey'})

    def receive_log_message(self, data):
        msg = data.get('msg', False)
        if not msg: return

        self.st.configure(state='normal')
        self.st.insert(tk.END, msg + '\n')
        self.st.configure(state='disabled')
        
        color = data.get('color', False)
        if color:
            final_index = str(self.st.index(tk.END))
            num_of_lines = int(final_index.split('.')[0])-2
            self.st.tag_config('mark_'+color, foreground=color)
            self.st.tag_add('mark_'+color, f"{num_of_lines}.0", f"{num_of_lines}.{len(msg)}")
        
        self.st.yview(tk.END)




class MainPanel():

    def __init__(self, main: Tk, controller:AppController, data_manager: DataManager):
        self.main = main
        self.controller = controller
        ## init main window
        self._init_window()

        ## define grid
        main.rowconfigure(0, weight=0, minsize=38)  # connection button bar
        main.rowconfigure(1, weight=0, minsize=38)  # connection button bar
        main.rowconfigure(2, weight=5, minsize=100) # treeview
        # main.rowconfigure(2, weight=1, minsize=30)  # logview
        main.rowconfigure(3, weight=0, minsize=30)  # status bar
        main.columnconfigure(0, weight=1, minsize=100)

        ## init presenters
        MenuPresenter(main, controller)
        ToolBar(main, controller, data_manager, row=0)
        SerialConnectionBar(main, controller, row=1)
        # main area
        main_split_area = ttk.PanedWindow(main, orient="vertical")
        main_split_area.grid(row=2, column=0, sticky="nsew", columnspan=3)
        
        data_split_area = ttk.PanedWindow(main_split_area, orient="horizontal")
        
        dt = DataTable(data_split_area, controller, data_manager)
        lo = LogOutputPanel(main_split_area, controller)

        main_split_area.add(data_split_area, weight=5)
        main_split_area.add(lo.root, weight=1)

        data_split_area.add(dt.root, weight=5)
        data_split_area.add(Frame(data_split_area), weight=2)

        StatusBar(main, controller, row=3)

        
        main.after(1000, self.on_loaded)

        ## start main loop
        main.mainloop()

        


    def _init_window(self):
        self.main.title("Device Manager")
        # main.geometry("500x300")  # set starting size of window
        self.main.config(bg="lightgrey")
        self.main.protocol("WM_DELETE_WINDOW", self.on_closing)
        filename = os.path.join(os.getcwd(), 'icons', 'Faenza-system-search.png')
        self.main.wm_iconphoto(False, tk.PhotoImage(file=filename))

    def on_loaded(self) -> None:
        self.controller.fire_event(ControllerEventType.WINDOW_LOADED, {})

    def on_closing(self) -> None:
        self.controller.fire_event(ControllerEventType.WINDOW_CLOSED, {})
        self.main.destroy()