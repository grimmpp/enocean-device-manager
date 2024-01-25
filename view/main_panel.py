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
from view import DEFAULT_WINDOW_TITLE
from view.device_details import DeviceDetails

from view.device_table import DeviceTable
from view.log_output import LogOutputPanel
from view.menu_presenter import MenuPresenter
from view.serial_communication_bar import SerialConnectionBar
from view.status_bar import StatusBar
from view.tool_bar import ToolBar

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
        mp = MenuPresenter(main, controller, data_manager)
        ToolBar(main, mp, row=0)
        SerialConnectionBar(main, controller, data_manager, row=1)
        # main area
        main_split_area = ttk.PanedWindow(main, orient="vertical")
        main_split_area.grid(row=2, column=0, sticky="nsew", columnspan=3)
        
        data_split_area = ttk.PanedWindow(main_split_area, orient="horizontal")
        
        dt = DeviceTable(data_split_area, controller, data_manager)
        dd = DeviceDetails(data_split_area, controller, data_manager)
        lo = LogOutputPanel(main_split_area, controller)

        main_split_area.add(data_split_area, weight=5)
        main_split_area.add(lo.root, weight=1)

        data_split_area.add(dt.root, weight=5)
        data_split_area.add(dd.root, weight=2)

        StatusBar(main, controller, data_manager, row=3)

        
        main.after(1000, self.on_loaded)

        ## start main loop
        main.mainloop()

        


    def _init_window(self):
        self.main.title(DEFAULT_WINDOW_TITLE)
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