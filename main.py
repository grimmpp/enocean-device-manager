import os
import sys
import logging
from tkinter import *
from view.main_panel import *
from controller import AppController

def main():
   # TODO: does not load module logging
   # logging.baicConfig(format='%(message)s', level=logging.INFO)

   controller = AppController()
   data_manager = DataManager(controller)

   filename = None
   if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]) and sys.argv[1].endswith('.eodm'):
       filename = sys.argv[1]
       data_manager.load_application_data_from_file(filename)

   root = Tk()
   MainPanel(root, controller, data_manager)

if __name__ == "__main__":
    main()
