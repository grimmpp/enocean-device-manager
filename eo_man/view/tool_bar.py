import tkinter as tk
import os
from tkinter import *
from PIL import Image, ImageTk
from idlelib.tooltip import Hovertip
import webbrowser

from .donation_button import DonationButton
from .menu_presenter import MenuPresenter
from ..icons.image_gallary import ImageGallery


class ToolBar():
    # icon list
    # https://commons.wikimedia.org/wiki/Comparison_of_icon_sets
    def __init__(self, main: Tk, menu_presenter:MenuPresenter, row:int):
        self.main = main

        f = Frame(main, bd=1)#, relief=SUNKEN)
        f.grid(row=row, column=0, columnspan=1, sticky=W+E+N+S, pady=2, padx=2)

        b = self._create_img_button(f, "Save to current file", ImageGallery.get_save_file_icon(), menu_presenter.save_file )
        b = self._create_img_button(f, "Save as file", ImageGallery.get_save_file_as_icon(), lambda: menu_presenter.save_file(save_as=True) )
        b = self._create_img_button(f, "Open file", ImageGallery.get_open_folder_icon(), menu_presenter.load_file)
        b = self._create_img_button(f, "Export Home Assistant Configuration", ImageGallery.get_ha_logo(), menu_presenter.export_ha_config)


        # placed at the right end
        b = DonationButton(f, relief=GROOVE, small_icon=True).pack(side=RIGHT, padx=(0,2), pady=2)
        b = self._create_img_button(f, "GitHub: EnOcean Device Manager Repository", ImageGallery.get_github_icon(), menu_presenter.open_eo_man_repo)
        b.pack(side=RIGHT, padx=(0,2), pady=2)
        b = self._create_img_button(f, "GitHub: EnOcean Device Manager Documentation", ImageGallery.get_help_icon(), menu_presenter.open_eo_man_documentation)
        b.pack(side=RIGHT, padx=(0,2), pady=2)

    def _create_img_button(self, f:Frame, tooltip:str, image:ImageTk.PhotoImage, command) -> Button:
        b = Button(f, image=image, relief=GROOVE, cursor="hand2", command=command)
        Hovertip(b,tooltip,300)
        b.image = image
        b.pack(side=LEFT, padx=(2,0), pady=2)
        return b
    