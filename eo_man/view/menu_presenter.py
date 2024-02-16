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

        menu_bar = Menu(main)
        file_menu = Menu(menu_bar, tearoff=False)
        
        # filemenu.add_command(label="New")
        load_file_icon = ImageGallery.get_open_folder_icon(size=(16,16))
        file_menu.add_command(label="Load File...", 
                              image=load_file_icon,
                              compound=LEFT,
                              command=self.load_file, 
                              accelerator="Ctrl+O")
        file_menu.add_command(label="Import From File...", 
                              image=load_file_icon,
                              compound=LEFT,
                              command=self.import_from_file, 
                              accelerator="Ctrl+I")
        file_menu.add_separator()
        ha_icon = ImageGallery.get_ha_logo(size=(16,16))
        file_menu.add_command(label="Export Home Assistant Configuration", 
                              image=ha_icon, 
                              compound=LEFT, 
                              command=self.export_ha_config, 
                              accelerator="Ctrl+E")
        file_menu.add_command(label="Export Home Assistant Configuration as ...", 
                              image=ha_icon, 
                              compound=LEFT, 
                              command=lambda: self.export_ha_config(save_as=True), 
                              accelerator="Ctrl+SHIFT+E")
        file_menu.add_separator()
        save_icon = ImageGallery.get_save_file_icon((16,16))
        file_menu.add_command(label="Save", 
                              image=save_icon,
                              compound=LEFT,
                              command=self.save_file, 
                              accelerator="Ctrl+S")
        save_as_icon = ImageGallery.get_save_file_as_icon((16,16))
        file_menu.add_command(label="Save as...", 
                             image=save_as_icon,
                             compound=LEFT,
                             command=lambda: self.save_file(save_as=True), 
                             accelerator="Ctrl+SHIFT+S")
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=main.quit, accelerator="ALT+F4")

        menu_bar.add_cascade(menu=file_menu, 
                                  label="File",
                                  accelerator="ALT+F")
        

        help_menu = Menu(menu_bar, tearoff=False)
        menu_bar.add_cascade(label="Help", menu=help_menu)
        
        github_icon = ImageGallery.get_github_icon((16,16))
        docs_menu = Menu(help_menu, tearoff=False)
        help_menu.add_cascade(menu=docs_menu, 
                             label="Documentation")
        docs_menu.add_command(label="EnOcean Device Manager ...", 
                             image=github_icon,
                             compound=LEFT,
                             command=self.open_eo_man_documentation)
        docs_menu.add_separator()
        docs_menu.add_command(label="Home Assistant Eltako Integration ...", 
                             image=github_icon,
                             compound=LEFT,
                             command=lambda: webbrowser.open_new(r"https://github.com/grimmpp/home-assistant-eltako/tree/main/docs"))

        repos_menu = Menu(help_menu, tearoff=0)
        help_menu.add_cascade(menu=repos_menu, 
                             label="GitHub Repositories")
        repos_menu.add_command(label="EnOcean Device Manager ...", 
                              image=github_icon,
                              compound=LEFT,
                              command=lambda: webbrowser.open_new(r"https://github.com/grimmpp/enocean-device-manager"))
        repos_menu.add_separator()
        repos_menu.add_command(label="Home Assistant Eltako Integration ...", 
                               image=github_icon,
                               compound=LEFT,
                               command=self.open_eo_man_repo)
        repos_menu.add_separator()
        repos_menu.add_command(label="Eltako14Bus Communication Library ...", 
                               image=github_icon,
                               compound=LEFT,
                               command=lambda: webbrowser.open_new(r"https://github.com/grimmpp/eltako14bus"))

        about_icon = ImageGallery.get_about_icon((16,16))
        help_menu.add_command(label="About...", 
                              image=about_icon,
                              compound=LEFT,
                              command=lambda: AboutWindow(main), 
                              accelerator="F1")
        

        main.config(menu=menu_bar)

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

    def open_eo_man_repo(self):
        webbrowser.open_new(r"https://github.com/grimmpp/enocean-device-manager")
        
    def open_eo_man_documentation(self):
        webbrowser.open_new(r"https://github.com/grimmpp/enocean-device-manager/tree/main/docs")
