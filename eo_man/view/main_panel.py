import logging
import os
import threading

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

    # time granted to background work to end itself when the window is closed
    SHUTDOWN_TIMEOUT = 3.0

    def __init__(self, app_bus:AppBus, data_manager: DataManager):
        self.main = Tk()
        self.app_bus = app_bus
        self._is_closed = threading.Event()
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

        main_split_area.add(data_split_area, weight=3)
        main_split_area.add(lo.root, weight=1)

        data_split_area.add(dt.root, weight=5)
        data_split_area.add(dd.root, weight=0)
        # dt.root.grid(row=0, column=0, sticky="nsew")
        # dd.root.grid(row=0, column=1, sticky="nsew")

        StatusBar(self.main, app_bus, data_manager, row=row_status_bar)

        # table gets 75% and command log 25% of the main area on startup
        self.main.after(1, lambda: self._set_initial_sash_position(main_split_area, 0.75))

        self.main.after(1, lambda: self.main.focus_force())

        ## start main loop
        self.main.mainloop()

        # the window is gone - the process has to end as well
        self._shutdown()

        
        


    def _set_initial_sash_position(self, paned_window: ttk.PanedWindow, upper_ratio: float) -> None:
        """Place the sash so that the upper pane gets `upper_ratio` of the available height."""
        paned_window.update_idletasks()
        height = paned_window.winfo_height()
        if height < 50:
            # window not layouted yet - try again on the next idle cycle
            self.main.after(50, lambda: self._set_initial_sash_position(paned_window, upper_ratio))
            return
        try:
            paned_window.sashpos(0, int(height * upper_ratio))
        except Exception as e:
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Cannot set initial sash position: {e}", 'log-level': 'DEBUG'})

    def _init_window(self):
        self.main.title(DEFAULT_WINDOW_TITLE)

        #style
        style = ttk.Style()
        
        theme_names = style.theme_names()
        if 'xpnative' in theme_names:
            style_theme = 'xpnative'
        elif 'alt' in theme_names:
            style_theme = 'alt'
        else: 
            style_theme = 'default'

        self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Available style themes: {ttk.Style().theme_names()}", 'log-level': 'DEBUG'})
        try:
            style.theme_use(style_theme)
        except:
            self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Cannot load style theme {style_theme}!", 'log-level': 'WARNING'})

        self.main.geometry("1400x600")  # set starting size of window
        # self.main.attributes('-fullscreen', True)
        # self.main.state('zoomed') # opens window maximized

        self.main.protocol("WM_DELETE_WINDOW", self.on_closing)

        # icon next to title in window frame
        self.main.wm_iconphoto(False, ImageGallery.get_eo_man_logo())

        # icon in taskbar
        icon = ImageGallery.get_eo_man_logo()
        self.main.iconphoto(True, icon, icon)

    def on_loaded(self) -> None:
        self.app_bus.fire_event(AppBusEventType.WINDOW_LOADED, {})

    def on_closing(self) -> None:
        """Called when the window is closed with the x button of the title bar."""
        self._close()
        self.main.destroy()

    def _close(self) -> None:
        """Tells everybody to stop: serial connections, service discovery, running
        background work. Runs only once - the window can also be closed in ways
        which do not call on_closing (window manager, Cmd+Q, ...)."""
        if self._is_closed.is_set():
            return
        self._is_closed.set()

        self.app_bus.fire_event(AppBusEventType.WINDOW_CLOSED, {})
        logging.info("Close Application eo-man")
        logging.info("========================\n")

    def _shutdown(self) -> None:
        """Ends the process after the window was closed.

        Background work (device scan, file import, serial communication) runs in
        its own threads. Some of them - especially the serial interface of
        eltakobus - are no daemon threads, so the interpreter would wait for them
        and the application would stay alive without a window."""
        self._close()

        for thread in threading.enumerate():
            if thread is threading.current_thread() or thread.daemon or not thread.is_alive():
                continue
            logging.debug("Waiting for thread %s to stop.", thread.name)
            thread.join(self.SHUTDOWN_TIMEOUT)
            if thread.is_alive():
                logging.warning("Thread %s did not stop. The process is ended anyway.", thread.name)

        # A thread which ignores its stop flag must not keep the application
        # running, therefore the process is ended explicitly.
        logging.shutdown()
        os._exit(0)