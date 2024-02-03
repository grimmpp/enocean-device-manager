import os
import sys
import logging
from tkinter import *
from data.data_manager import DataManager
from view.main_panel import MainPanel
from controller.app_bus import AppBus
from controller.serial_controller import SerialController

def main():
   # TODO: does not load module logging
   # logging.baicConfig(format='%(message)s', level=logging.INFO)

   app_bus = AppBus()
   data_manager = DataManager(app_bus)

   filename = None
   if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]) and sys.argv[1].endswith('.eodm'):
       filename = sys.argv[1]
       data_manager.load_application_data_from_file(filename)

   root = Tk()
   MainPanel(root, app_bus, data_manager)

if __name__ == "__main__":
    main()
