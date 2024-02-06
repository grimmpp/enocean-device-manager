import os
from pathlib import Path
import threading
from tkinter import *
from tkinter import filedialog

from ..controller.app_bus import AppBus, AppBusEventType
from ..data.data_manager import DataManager
from ..view.about_window import AboutWindow
from ..view import DEFAULT_WINDOW_TITLE

class MenuPresenter():

    def __init__(self, main: Tk, app_bus: AppBus, data_manager: DataManager):
        self.main = main
        self.app_bus = app_bus
        self.data_manager = data_manager
        self.remember_latest_filename = ""

        self.menu_bar = Menu(main)
        filemenu = Menu(self.menu_bar, tearoff=0)
        # filemenu.add_command(label="New")
        filemenu.add_command(label="Load File...", command=self.load_file, accelerator="Ctrl+O")
        filemenu.add_command(label="Import From File...", command=self.import_from_file, accelerator="Ctrl+I")
        filemenu.add_separator()
        filemenu.add_command(label="Export Home Assistant Configuration", command=self.export_ha_config, accelerator="Ctrl+E")
        filemenu.add_command(label="Export Home Assistant Configuration as ...", command=lambda: self.export_ha_config(save_as=True), accelerator="Ctrl+SHIFT+E")
        filemenu.add_separator()
        filemenu.add_command(label="Save", command=self.save_file, accelerator="Ctrl+S")
        filemenu.add_command(label="Save as...", command=lambda: self.save_file(save_as=True), accelerator="Ctrl+SHIFT+S")
        # filemenu.add_command(label="Close")
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=main.quit, accelerator="ALT+F4")
        self.menu_bar.add_cascade(label="File", menu=filemenu)
        
        # editmenu = Menu(self.menu_bar, tearoff=0)
        # editmenu.add_command(label="Undo")
        # editmenu.add_separator()
        # editmenu.add_command(label="Cut")
        # editmenu.add_command(label="Copy")
        # editmenu.add_command(label="Paste")
        # editmenu.add_command(label="Delete")
        # editmenu.add_command(label="Select All")
        # self.menu_bar.add_cascade(label="Edit", menu=editmenu)

        helpmenu = Menu(self.menu_bar, tearoff=0)
        # helpmenu.add_command(label="Help Index")
        helpmenu.add_command(label="About...", command=lambda: AboutWindow(main), accelerator="F1")
        self.menu_bar.add_cascade(label="Help", menu=helpmenu)

        main.config(menu=self.menu_bar)

        main.bind('<Control-o>', lambda e: self.load_file())
        main.bind('<Control-i>', lambda e: self.import_from_file())
        main.bind('<Control-e>', lambda e: self.export_ha_config())
        main.bind('<Control-Shift-E>', lambda e: self.export_ha_config(save_as=True))
        main.bind('<Control-s>', lambda e: self.save_file())
        main.bind('<Control-Shift-S>', lambda e: self.save_file(save_as=True))
        main.bind('<F1>', lambda e: AboutWindow(main))
        


    def save_file(self, save_as:bool=False):
        if save_as or not os.path.isfile(self.remember_latest_filename):
        # initial_dir = os.path.dirname(self.remember_latest_filename)

            filename = filedialog.asksaveasfilename(initialdir=self.remember_latest_filename, 
                                                title="Save Application State",
                                                filetypes=[("EnOcean Device Manager", "*.eodm")],
                                                defaultextension=".eodm")
            if not filename:
                return
            
            if not filename.endswith('.eodm'):
                filename += '.eodm'
            self.remember_latest_filename = filename

        self.data_manager.write_application_data_to_file(self.remember_latest_filename)
        # with open(self.remember_latest_filename, 'wb') as file:
        #     pickle.dump( self.data_manager.devices, file)
        
        self.main.title(f"{DEFAULT_WINDOW_TITLE} ({os.path.basename(self.remember_latest_filename)})")
        self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Save to File: '{self.remember_latest_filename}'", 'color': 'red'})

    def import_from_file(self):
        if not self.remember_latest_filename:
            self.remember_latest_filename = os.path.expanduser('~')

        initial_dir = os.path.dirname(self.remember_latest_filename)
        filename = filedialog.askopenfilename(initialdir=initial_dir, 
                                                title="Load Application State",
                                                filetypes=[("EnOcean Device Manager", "*.eodm")],
                                                defaultextension=".eodm") #, ("configuration", "*.yaml"), ("all files", "*.*")))
        
        if not filename:
            return None
        
        def load():
            self.data_manager.load_application_data_from_file(filename)
            # with open(filename, 'rb') as file:
            #     self.data_manager.load_devices( pickle.load(file) )

        t = threading.Thread(target=load)
        t.start()

        return filename
        
    def load_file(self, filename:str=None):
        if filename == None:
            filename = self.import_from_file()

        if filename:
            self.app_bus.fire_event(AppBusEventType.LOAD_FILE, {})
            self.remember_latest_filename = filename

            self.main.title(f"{DEFAULT_WINDOW_TITLE} ({os.path.basename(self.remember_latest_filename)})")
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Load File: '{self.remember_latest_filename}'", 'color': 'red'})

    
    remember_latest_ha_config_filename:str=None
    def export_ha_config(self, save_as:bool=False):
        if save_as or not self.remember_latest_ha_config_filename:
        # initial_dir = os.path.dirname(self.remember_latest_filename)

            filename = filedialog.asksaveasfilename(initialdir=self.remember_latest_filename, 
                                                title="Save Home Assistant Configuration",
                                                filetypes=[("Home Assistant Configuration", "*.yaml")],
                                                defaultextension=".yaml")
            if not filename:
                return

            if not filename.endswith('.yaml'):
                filename += '.yaml'
            self.remember_latest_ha_config_filename = filename

        file_content = self.data_manager.generate_ha_config()
        with open(self.remember_latest_ha_config_filename, 'w') as file:
            file.write(file_content)

        self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Export Home Assistant Config to File: '{self.remember_latest_ha_config_filename}'", 'color': 'red'})

        
