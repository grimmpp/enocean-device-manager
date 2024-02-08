import sys
import os
from typing import Final

PACKAGE_NAME: Final = 'eo_man'

# load same path like calling the app via 'python -m eo-man'
file_dir = os.path.join( os.path.dirname(__file__), '..')
sys.path.append(file_dir)
__import__(PACKAGE_NAME)
__package__ = PACKAGE_NAME

from eo_man import load_dep_homeassistant
load_dep_homeassistant()

from .data.data_manager import DataManager
from .view.main_panel import MainPanel
from .controller.app_bus import AppBus, AppBusEventType

import logging
from tkinter import *


def main():
   # init application message BUS
   app_bus = AppBus()

   # init LOGGING
   logging.basicConfig(format='%(message)s ', level=logging.INFO)
   LOGGER = logging.getLogger(PACKAGE_NAME)
   LOGGER.setLevel(logging.DEBUG)
   LOGGER.info("Start Application eo-man")
   # add print log messages for log message view on command line as debug
   def print_log_event(e:dict):
       log_level = e.get('log-level', 'INFO')
       log_level_int = logging.getLevelName(log_level)
       if log_level_int >= LOGGER.getEffectiveLevel():
           LOGGER.log(log_level_int, str(e['msg']))
   app_bus.add_event_handler(AppBusEventType.LOG_MESSAGE, print_log_event)
   
   # init DATA MANAGER
   data_manager = DataManager(app_bus)

   filename = None
   if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]) and (sys.argv[1].endswith('.eodm') or sys.argv[1].endswith('.yaml')):
       filename = sys.argv[1]
       e = {'msg': f"Initially load data from file {filename}", 'color': 'darkred'}
       app_bus.fire_event(AppBusEventType.LOG_MESSAGE, e)
       data_manager.load_application_data_from_file(filename)

   root = Tk()
   MainPanel(root, app_bus, data_manager)

if __name__ == "__main__":
    main()
