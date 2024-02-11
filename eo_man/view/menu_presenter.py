import os
import threading
from tkinter import *
from tkinter import filedialog
import logging
import webbrowser

from ..controller.app_bus import AppBus, AppBusEventType

from ..data.data_manager import DataManager
from ..data.ha_config_generator import HomeAssistantConfigurationGenerator

from ..icons.image_gallary import ImageGallery

from .about_window import AboutWindow
from . import DEFAULT_WINDOW_TITLE

class MenuPresenter():

    def __init__(self, main: Tk, app_bus: AppBus, data_manager: DataManager):
        self.main = main
        self.app_bus = app_bus
        self.data_manager = data_manager
        self.ha_conf_gen = HomeAssistantConfigurationGenerator(app_bus, data_manager)
        self.remember_latest_filename = ""

        self.menu_bar = Menu(main)
        filemenu = Menu(self.menu_bar, tearoff=False)
        self.menu_bar.add_cascade(menu=filemenu, 
                                  label="File", 
                                  underline=0, 
                                  accelerator="ALT+F")
        # filemenu.add_command(label="New")
        filemenu.add_command(label="Load File...", 
                            #  image=ImageGallery.get_open_folder_icon(size=(16,16)),
                            #  compound=LEFT,
                             command=self.load_file, 
                             accelerator="Ctrl+O")
        filemenu.add_command(label="Import From File...", 
                             command=self.import_from_file, 
                             accelerator="Ctrl+I")
        filemenu.add_separator()
        filemenu.add_command(label="Export Home Assistant Configuration", 
                            #  image=ImageGallery.get_ha_logo(size=(16,16)), 
                            #  compound=LEFT, 
                             command=self.export_ha_config, 
                             accelerator="Ctrl+E")
        filemenu.add_command(label="Export Home Assistant Configuration as ...", 
                            #  image=ImageGallery.get_ha_logo(size=(16,16)), 
                            #  compound=LEFT, 
                             command=lambda: self.export_ha_config(save_as=True), 
                             accelerator="Ctrl+SHIFT+E")
        filemenu.add_separator()
        filemenu.add_command(label="Save", 
                            #  image=ImageGallery.get_save_file_icon(),
                            #  compound=LEFT,
                             command=self.save_file, 
                             accelerator="Ctrl+S")
        filemenu.add_command(label="Save as...", 
                             image=ImageGallery.get_save_file_as_icon(),
                             compound=LEFT,
                             command=lambda: self.save_file(save_as=True), 
                             accelerator="Ctrl+SHIFT+S")
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=main.quit, accelerator="ALT+F4")
        
        # editmenu = Menu(self.menu_bar, tearoff=0)
        # editmenu.add_command(label="Undo")
        # editmenu.add_separator()
        # editmenu.add_command(label="Cut")
        # editmenu.add_command(label="Copy")
        # editmenu.add_command(label="Paste")
        # editmenu.add_command(label="Delete")
        # editmenu.add_command(label="Select All")
        # self.menu_bar.add_cascade(label="Edit", menu=editmenu)

        helpmenu = Menu(self.menu_bar, tearoff=False)
        self.menu_bar.add_cascade(label="Help", menu=helpmenu)
        
        docsmenu = Menu(helpmenu, tearoff=False)
        helpmenu.add_cascade(menu=docsmenu, 
                             label="Documentation")
        docsmenu.add_command(label="EnOcean Device Manager ...", 
                             command=self.open_eo_man_documentation)
        docsmenu.add_separator()
        docsmenu.add_command(label="Home Assistant Eltako Integration ...", 
                             command=lambda: webbrowser.open_new(r"https://github.com/grimmpp/home-assistant-eltako/tree/main/docs"))

        reposmenu = Menu(helpmenu, tearoff=0)
        helpmenu.add_cascade(menu=reposmenu, 
                             label="GitHub Repositories")
        reposmenu.add_command(label="EnOcean Device Manager ...", 
                              command=lambda: webbrowser.open_new(r"https://github.com/grimmpp/enocean-device-manager"))
        reposmenu.add_separator()
        reposmenu.add_command(label="Home Assistant Eltako Integration ...", 
                              command=lambda: webbrowser.open_new(r"https://github.com/grimmpp/home-assistant-eltako"))
        reposmenu.add_separator()
        reposmenu.add_command(label="Eltako14Bus Communication Library ...", 
                              command=lambda: webbrowser.open_new(r"https://github.com/grimmpp/eltako14bus"))

        helpmenu.add_command(label="About...", 
                            #  image=ImageGallery.get_about_icon(size=(16,16)),
                            #  compound=LEFT,
                             command=lambda: AboutWindow(main), 
                             accelerator="F1")
        

        main.config(menu=self.menu_bar)

        # add shortcuts globally
        main.bind('<Control-o>', lambda e: self.load_file())
        main.bind('<Control-i>', lambda e: self.import_from_file())
        main.bind('<Control-e>', lambda e: self.export_ha_config())
        main.bind('<Control-Shift-E>', lambda e: self.export_ha_config(save_as=True))
        main.bind('<Control-s>', lambda e: self.save_file())
        main.bind('<Control-Shift-S>', lambda e: self.save_file(save_as=True))
        main.bind('<F1>', lambda e: AboutWindow(main))
        


    def save_file(self, save_as:bool=False):
        try:
            if save_as or not os.path.isfile(self.remember_latest_filename):
            # initial_dir = os.path.dirname(self.remember_latest_filename)

                filename = filedialog.asksaveasfilename(initialdir=self.remember_latest_filename, 
                                                    title="Save Application State",
                                                    filetypes=[("EnOcean Device Manager", "*.eodm"), ("EnOcean Device Manager", "*.yaml")],
                                                    defaultextension=".eodm")
                if not filename:
                    return
                
                if not filename.endswith('.eodm') and not filename.endswith('.yaml'):
                    filename += '.eodm'
                self.remember_latest_filename = filename

            self.data_manager.write_application_data_to_file(self.remember_latest_filename)
            # with open(self.remember_latest_filename, 'wb') as file:
            #     pickle.dump( self.data_manager.devices, file)
            
            self.main.title(f"{DEFAULT_WINDOW_TITLE} ({os.path.basename(self.remember_latest_filename)})")
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Save to File: '{self.remember_latest_filename}'", 'color': 'red'})

        except Exception as e:
            msg = f"Saving application configuration to file '{filename}' failed!"
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'log-level': 'ERROR', 'color': 'red'})
            logging.exception(msg, exc_info=True)


    def import_from_file(self):
        filename = None
        try:
            if not self.remember_latest_filename:
                self.remember_latest_filename = os.path.expanduser('~')

            initial_dir = os.path.dirname(self.remember_latest_filename)
            filename = filedialog.askopenfilename(initialdir=initial_dir, 
                                                    title="Load Application State",
                                                    filetypes=[("EnOcean Device Manager", "*.eodm"), ("EnOcean Device Manager", "*.yaml")],
                                                    defaultextension=".eodm") #, ("configuration", "*.yaml"), ("all files", "*.*")))
            
            if not filename:
                return None
            
            def load():
                self.data_manager.load_application_data_from_file(filename)
                # with open(filename, 'rb') as file:
                #     self.data_manager.load_devices( pickle.load(file) )

            t = threading.Thread(target=load)
            t.start()

        except Exception as e:
            msg = f"Loading application configuration file '{filename}' failed!"
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'log-level': 'ERROR', 'color': 'red'})
            logging.exception(msg, exc_info=True)

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
        try:
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

            self.ha_conf_gen.save_as_yaml_to_file(self.remember_latest_ha_config_filename)

        except Exception as e:
            msg = 'Exporting Home Assistant Configuration failed!'
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'log-level': 'ERROR', 'color': 'red'})
            logging.exception(msg, exc_info=True)

        
    def open_eo_man_documentation(self):
        webbrowser.open_new(r"https://github.com/grimmpp/enocean-device-manager/tree/main/docs")
