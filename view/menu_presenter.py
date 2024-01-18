import os
from pathlib import Path
from tkinter import *
from tkinter import filedialog
from controller import AppController, ControllerEventType
from data import DataManager
from view.about_window import AboutWindow

import pickle

class MenuPresenter():

    def __init__(self, main: Tk, controller: AppController, data_manager: DataManager):

        self.controller = controller
        self.data_manager = data_manager
        self.remember_latest_filename = None

        self.menu_bar = Menu(main)
        filemenu = Menu(self.menu_bar, tearoff=0)
        filemenu.add_command(label="New")
        filemenu.add_command(label="Load File...", command=self._load_file)
        filemenu.add_command(label="Import From File...", command=self._import_from_file)
        filemenu.add_command(label="Save", command=self._save_file)
        filemenu.add_command(label="Save as...", command=lambda: self._save_file(True))
        # filemenu.add_command(label="Close")
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=main.quit)
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
        helpmenu.add_command(label="About...", command=lambda: AboutWindow(main))
        self.menu_bar.add_cascade(label="Help", menu=helpmenu)

        main.config(menu=self.menu_bar)

    def _save_file(self, save_as:bool=False):
        if save_as or not self.remember_latest_filename:
        # initial_dir = os.path.dirname(self.remember_latest_filename)

            filename = filedialog.asksaveasfilename(initialdir=self.remember_latest_filename, 
                                                title="Save Application State",
                                                filetypes=[("EnOcean Device Manager", "*.eodm")],
                                                defaultextension=".eodm")
            if not filename.endswith('.eodm'):
                filename += '.eodm'
            self.remember_latest_filename = filename

        # self.data_manager.export_cached_objects(self.remember_latest_filename)
        with open(self.remember_latest_filename, 'wb') as file:
            pickle.dump( self.data_manager.devices, file)

    def _import_from_file(self):
        if not self.remember_latest_filename:
            self.remember_latest_filename = os.path.expanduser('~')

        initial_dir = os.path.dirname(self.remember_latest_filename)
        filename = filedialog.askopenfilename(initialdir=initial_dir, 
                                                title="Load Application State",
                                                filetypes=[("EnOcean Device Manager", "*.eodm")],
                                                defaultextension=".eodm") #, ("configuration", "*.yaml"), ("all files", "*.*")))
        
        with open(filename, 'rb') as file:
            self.data_manager.load_devices( pickle.load(file) )

        return filename
        
    def _load_file(self):
        self.controller.fire_event(ControllerEventType.LOAD_FILE, {})
        self.remember_latest_filename = self._import_from_file()
        self.controller.fire_event(ControllerEventType.LOG_MESSAGE, {'msg': f"Load File: '{self.remember_latest_filename}'", 'color': 'red'})
        