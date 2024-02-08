import sys
import os

# load same path like calling the app via 'python -m eo-man'
file_dir = os.path.join( os.path.dirname(__file__), '..')
sys.path.append(file_dir)
__import__('eo-man')
__package__ = 'eo-man'

# import fake homeassistant package
file_dir = os.path.join( os.path.dirname(__file__), 'data')
sys.path.append(file_dir)
__import__('homeassistant')

from .data.data_manager import DataManager
from .view.main_panel import MainPanel
from .controller.app_bus import AppBus, AppBusEventType

import logging
from tkinter import *


def main():
   # init application message BUS
   app_bus = AppBus()

   # init LOGGING
   logging.basicConfig(format='%(message)s', level=logging.DEBUG)
   logging.info("Start Application eo-man")
   # add print log messages for log message view on command line as debug
   app_bus.add_event_handler(AppBusEventType.LOG_MESSAGE, lambda e: logging.debug(str(e['msg'])))
   
   # init DATA MANAGER
   data_manager = DataManager(app_bus)

   filename = None
   if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]) and (sys.argv[1].endswith('.eodm') or sys.argv[1].endswith('.yaml')):
       filename = sys.argv[1]
       data_manager.load_application_data_from_file(filename)

   root = Tk()
   MainPanel(root, app_bus, data_manager)

if __name__ == "__main__":
    main()
