import time
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
from data.data_manager import DataManager, Device
from view import DEFAULT_WINDOW_TITLE
from view.device_details import DeviceDetails

from view.device_table import DeviceTable
from view.filter_bar import FilterBar
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

        self.main

        ## define grid
        row_button_bar = 0
        row_serial_con_bar = 1
        row_filter_bar = 2
        row_main_area = 3
        row_status_bar = 4
        main.rowconfigure(row_button_bar, weight=0, minsize=38)      # button bar
        main.rowconfigure(row_serial_con_bar, weight=0, minsize=38)      # serial connection bar
        main.rowconfigure(row_filter_bar, weight=0, minsize=38)      # table filter bar
        main.rowconfigure(row_main_area, weight=5, minsize=100)     # treeview
        # main.rowconfigure(2, weight=1, minsize=30)    # logview
        main.rowconfigure(row_status_bar, weight=0, minsize=30)      # status bar
        main.columnconfigure(0, weight=1, minsize=100)

        ## init presenters
        mp = MenuPresenter(main, controller, data_manager)
        ToolBar(main, mp, row=row_button_bar)
        SerialConnectionBar(main, controller, data_manager, row=row_serial_con_bar)
        FilterBar(main, controller, data_manager, row=row_filter_bar)
        # main area
        main_split_area = ttk.PanedWindow(main, orient="vertical")
        main_split_area.grid(row=row_main_area, column=0, sticky="nsew", columnspan=4)
        
        data_split_area = ttk.PanedWindow(main_split_area, orient="horizontal")
        # data_split_area = Frame(main_split_area)
        # data_split_area.columnconfigure(0, weight=5)
        # data_split_area.columnconfigure(0, weight=0, minsize=100)
        
        dt = DeviceTable(data_split_area, controller, data_manager)
        dd = DeviceDetails(data_split_area, controller, data_manager)
        lo = LogOutputPanel(main_split_area, controller)

        main_split_area.add(data_split_area, weight=5)
        main_split_area.add(lo.root, weight=1)

        data_split_area.add(dt.root, weight=5)
        data_split_area.add(dd.root, weight=0)
        # dt.root.grid(row=0, column=0, sticky="nsew")
        # dd.root.grid(row=0, column=1, sticky="nsew")

        StatusBar(main, controller, data_manager, row=row_status_bar)

        
        main.after(500, self.on_loaded)

        ## start main loop
        main.mainloop()

        
        


    def _init_window(self):
        self.main.title(DEFAULT_WINDOW_TITLE)
        self.main.geometry("1400x600")  # set starting size of window
        # self.main.attributes('-fullscreen', True)
        # self.main.state('zoomed') # opens window maximized
        self.main.config(bg="lightgrey")
        self.main.protocol("WM_DELETE_WINDOW", self.on_closing)
        filename = os.path.join(os.getcwd(), 'icons', 'Faenza-system-search.png')
        self.main.wm_iconphoto(False, tk.PhotoImage(file=filename))

    def on_loaded(self) -> None:
        self.controller.fire_event(ControllerEventType.WINDOW_LOADED, {})

    def on_closing(self) -> None:
        self.controller.fire_event(ControllerEventType.WINDOW_CLOSED, {})
        self.main.destroy()