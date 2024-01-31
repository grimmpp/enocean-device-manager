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

from data.data import DataManager
from view.menu_presenter import MenuPresenter


class ToolBar():
    # icon list
    # https://commons.wikimedia.org/wiki/Comparison_of_icon_sets
    def __init__(self, main: Tk, menu_presenter:MenuPresenter, row:int):
        self.main = main

        f = Frame(main, bd=1)#, relief=SUNKEN)
        f.grid(row=row, column=0, columnspan=1, sticky=W+E+N+S, pady=2, padx=2)

        b = self._create_img_button(f, "Save to current file", "icons/Oxygen480-actions-document-save.png", menu_presenter.save_file )
        b = self._create_img_button(f, "Save as file", "icons/Oxygen480-actions-document-save-as.png", lambda: menu_presenter.save_file(save_as=True) )
        b = self._create_img_button(f, "Open file", "icons/Oxygen480-status-folder-open.png", menu_presenter.load_file)
        b = self._create_img_button(f, "Export Home Assistant Configuration", "icons/Home_Assistant_Logo.png", menu_presenter.export_ha_config)

    def _create_img_button(self, f:Frame, tooltip:str, img_filename:str, command) -> Button:
        img = Image.open(img_filename)
        img = img.resize((24, 24), Image.LANCZOS)
        eimg = ImageTk.PhotoImage(img)
        b = Button(f, image=eimg, relief=FLAT, command=command)
        Hovertip(b,tooltip,300)
        b.image = eimg
        b.pack(side=LEFT, padx=2, pady=2)
        return b