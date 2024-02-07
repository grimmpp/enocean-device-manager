import sys
import os

file_dir = os.path.join( os.path.dirname(__file__), '..')
sys.path.append(file_dir)
__import__('eo-man')
__package__ = 'eo-man'

import logging
from tkinter import *

import os
import imp
dirname = os.path.join( os.path.dirname(__file__), 'data', 'homeassistant')
imp.load_package('homeassistant', dirname)

from .data.data_manager import DataManager
from .view.main_panel import MainPanel
from .controller.app_bus import AppBus

def main():
   # TODO: does not load module logging
   # logging.baicConfig(format='%(message)s', level=logging.INFO)

   app_bus = AppBus()
   data_manager = DataManager(app_bus)

   filename = None
   if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]) and (sys.argv[1].endswith('.eodm') or sys.argv[1].endswith('.yaml')):
       filename = sys.argv[1]
       data_manager.load_application_data_from_file(filename)

   root = Tk()
   MainPanel(root, app_bus, data_manager)

if __name__ == "__main__":
    main()
