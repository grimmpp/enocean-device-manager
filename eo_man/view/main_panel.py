import logging

from tkinter import *
from tkinter import ttk

from ..icons.image_gallary import ImageGallery

from ..controller.app_bus import AppBus, AppBusEventType
from ..controller.serial_controller import SerialController
from ..controller.gateway_registry import GatewayRegistry

from ..data.data_manager import DataManager

from ..view import DEFAULT_WINDOW_TITLE
from ..view.device_details import DeviceDetails
from ..view.device_table import DeviceTable
from ..view.filter_bar import FilterBar
from ..view.log_output import LogOutputPanel
from ..view.menu_presenter import MenuPresenter
from ..view.serial_communication_bar import SerialConnectionBar
from ..view.status_bar import StatusBar
from ..view.tool_bar import ToolBar

class MainPanel():

    def __init__(self, app_bus:AppBus, data_manager: DataManager):
        self.main = Tk()
        self.app_bus = app_bus
        ## init main window
        self._init_window()

        ## define grid
        row_button_bar = 0
        row_serial_con_bar = 1
        row_filter_bar = 2
        row_main_area = 3
        row_status_bar = 4
        self.main.rowconfigure(row_button_bar, weight=0, minsize=38)      # button bar
        self.main.rowconfigure(row_serial_con_bar, weight=0, minsize=38)      # serial connection bar
        self.main.rowconfigure(row_filter_bar, weight=0, minsize=38)      # table filter bar
        self.main.rowconfigure(row_main_area, weight=5, minsize=100)     # treeview
        # main.rowconfigure(2, weight=1, minsize=30)    # logview
        self.main.rowconfigure(row_status_bar, weight=0, minsize=30)      # status bar
        self.main.columnconfigure(0, weight=1, minsize=100)

        gateway_registry = GatewayRegistry(app_bus)
        serial_controller = SerialController(app_bus, gateway_registry)

        ## init presenters
        mp = MenuPresenter(self.main, app_bus, data_manager, serial_controller)
        
        ToolBar(self.main, mp, row=row_button_bar)
        SerialConnectionBar(self.main, app_bus, data_manager, serial_controller, row=row_serial_con_bar)
        FilterBar(self.main, app_bus, data_manager, row=row_filter_bar)
        # main area
        main_split_area = ttk.PanedWindow(self.main, orient=VERTICAL)
        main_split_area.grid(row=row_main_area, column=0, sticky=NSEW, columnspan=4)
        
        data_split_area = ttk.PanedWindow(main_split_area, orient=HORIZONTAL)
        # data_split_area = Frame(main_split_area)
        # data_split_area.columnconfigure(0, weight=5)
        # data_split_area.columnconfigure(0, weight=0, minsize=100)
        
        dt = DeviceTable(data_split_area, app_bus, data_manager)
        dd = DeviceDetails(self.main, data_split_area, app_bus, data_manager)
        lo = LogOutputPanel(main_split_area, app_bus, data_manager)

        main_split_area.add(data_split_area, weight=5)
        main_split_area.add(lo.root, weight=2)

        data_split_area.add(dt.root, weight=5)
        data_split_area.add(dd.root, weight=0)
        # dt.root.grid(row=0, column=0, sticky="nsew")
        # dd.root.grid(row=0, column=1, sticky="nsew")

        StatusBar(self.main, app_bus, data_manager, row=row_status_bar)

        self.main.after(1, lambda: self.main.focus_force())

        ## start main loop
        self.main.mainloop()

        
        


    def _init_window(self):
        self.main.title(DEFAULT_WINDOW_TITLE)

        #style
        style = ttk.Style()
        style.configure("TButton", relief="sunken", background='green')
        style_theme = 'xpnative' # 'clam'
        self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Available style themes: {ttk.Style().theme_names()}", 'log-level': 'DEBUG'})
        try:
            style.theme_use(style_theme)
        except:
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Cannot load style theme {style_theme}!", 'log-level': 'WARNING'})

        self.main.geometry("1400x600")  # set starting size of window
        # self.main.attributes('-fullscreen', True)
        # self.main.state('zoomed') # opens window maximized

        self.main.config(bg="lightgrey")
        self.main.protocol("WM_DELETE_WINDOW", self.on_closing)

        # icon next to title in window frame
        self.main.wm_iconphoto(False, ImageGallery.get_eo_man_logo())

        # icon in taskbar
        icon = ImageGallery.get_eo_man_logo()
        self.main.iconphoto(True, icon, icon)

    def on_loaded(self) -> None:
        self.app_bus.fire_event(AppBusEventType.WINDOW_LOADED, {})

    def on_closing(self) -> None:
        self.app_bus.fire_event(AppBusEventType.WINDOW_CLOSED, {})
        logging.info("Close Application eo-man")
        logging.info("========================\n")
        self.main.destroy()