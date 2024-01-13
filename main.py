import os
import logging
from tkinter import *
from view.main_panel import *
from controller import AppController

def main():
   # TODO: does not load module logging
   # logging.baicConfig(format='%(message)s', level=logging.INFO)

   controller = AppController()
   data_manager = DataManager(controller)
   root = Tk()
   MainPanel(root, controller, data_manager)

if __name__ == "__main__":
    main()
