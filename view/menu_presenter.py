import os
from pathlib import Path
from tkinter import *
from tkinter import filedialog
from view.about_window import AboutWindow

class MenuPresenter():

    def __init__(self, main: Tk, controller):

        self.controller = controller

        self.menu_bar = Menu(main)
        filemenu = Menu(self.menu_bar, tearoff=0)
        filemenu.add_command(label="New")
        filemenu.add_command(label="Load File...", command=self._load_file)
        filemenu.add_command(label="Save")
        filemenu.add_command(label="Save as...")
        # filemenu.add_command(label="Close")
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=main.quit)
        self.menu_bar.add_cascade(label="File", menu=filemenu)
        
        # editmenu = Menu(self.menu_bar, tearoff=0)
        # editmenu.add_command(label="Undo")
        # editmenu.add_separator()
        # editmenu.add_command(label="Cut")
        # editmenu.add_command(label="Copy")
        # editmenu.add_command(label="Paste")
        # editmenu.add_command(label="Delete")
        # editmenu.add_command(label="Select All")
        # self.menu_bar.add_cascade(label="Edit", menu=editmenu)

        helpmenu = Menu(self.menu_bar, tearoff=0)
        # helpmenu.add_command(label="Help Index")
        helpmenu.add_command(label="About...", command=lambda: AboutWindow(main))
        self.menu_bar.add_cascade(label="Help", menu=helpmenu)

        main.config(menu=self.menu_bar)

    def _load_file(self):

        filename = filedialog.askopenfilename(initialdir=Path.home(), title="Select a Configuration File", filetypes=(("configuration", "*.yaml"), ("all files", "*.*")))
        