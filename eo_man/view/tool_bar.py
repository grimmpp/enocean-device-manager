import threading
import tkinter as tk
from tkinter import ttk
import os
from tkinter import *
from tkinter import messagebox
from PIL import Image, ImageTk
from idlelib.tooltip import Hovertip
import webbrowser
import subprocess

from eo_man import LOGGER

from .donation_button import DonationButton
from .menu_presenter import MenuPresenter
from ..icons.image_gallary import ImageGallery
from ..data.app_info import ApplicationInfo as AppInfo


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
        
        self._add_separater(f)
        
        b = self._create_img_button(f, "Export Home Assistant Configuration", ImageGallery.get_ha_logo(), menu_presenter.export_ha_config)

        self._add_separater(f)

        b = self._create_img_button(f, "Send Message", ImageGallery.get_forward_mail(), menu_presenter.show_send_message_window)

        # placed at the right end
        b = DonationButton(f, relief=GROOVE, small_icon=True).pack(side=RIGHT, padx=(0,2), pady=2)
        b = self._create_img_button(f, "GitHub: EnOcean Device Manager Repository", ImageGallery.get_github_icon(), menu_presenter.open_eo_man_repo)
        b.pack(side=RIGHT, padx=(0,2), pady=2)
        b = self._create_img_button(f, "GitHub: EnOcean Device Manager Documentation", ImageGallery.get_help_icon(), menu_presenter.open_eo_man_documentation)
        b.pack(side=RIGHT, padx=(0,2), pady=2)

        if not AppInfo.is_version_up_to_date():
            new_v = AppInfo.get_lastest_available_version()
            b = self._create_img_button(f, f"New Software Version 'v{new_v}' is available.", ImageGallery.get_software_update_available_icon(), self.show_how_to_update)
            b.pack(side=RIGHT, padx=(0,2), pady=2)

    def _add_separater(self, f:Frame):
        ttk.Separator(f, orient=VERTICAL).pack(side=LEFT, padx=4)


    def _create_img_button(self, f:Frame, tooltip:str, image:ImageTk.PhotoImage, command) -> Button:
        b = ttk.Button(f, image=image, cursor="hand2", command=command) #, relief=GROOVE)
        Hovertip(b,tooltip,300)
        b.image = image
        b.pack(side=LEFT, padx=(2,0), pady=2)
        return b
    
    def show_how_to_update(self):
        base_path = os.environ.get('VIRTUAL_ENV', '')
        if base_path != '':
            base_path = os.path.join(base_path, 'Scripts')
        
        new_version = AppInfo.get_lastest_available_version()
        
        msg  = f"A new version 'v{new_version}' of 'EnOcean Device Manager' is available. \n\n"
        msg += f"You can update this application by entering \n"
        msg += f"'{os.path.join(base_path, 'pip')}' install eo_man --upgrade'\n"
        msg += f"into the command line."

        messagebox.showinfo("Update Available", msg)