import tkinter as tk
from tkinter import ttk
from tkinter import *
from tkinter.font import *
import webbrowser
from tkinterhtml import HtmlFrame
from idlelib.tooltip import Hovertip

from .donation_button import DonationButton

from ..data.app_info import ApplicationInfo as AppInfo


class AboutWindow():

    def __init__(self, main:Tk):
        popup = Toplevel(main)
        popup.wm_title("About")
        self.popup = popup

        self.label_font = Font(name="Arial", underline=True, size=10)

        l = tk.Label(popup, text="About EnOcean Device Manager", font='Arial 14 bold')
        l.pack(side=TOP, fill="x", pady=10)

        l = tk.Label(popup, text="Version: "+AppInfo.get_version(), font="Arial 10", anchor="w")
        l.pack(side=TOP, fill="x", pady=2, padx=5)

        self.get_label_link(text="PyPI: Package Name: "+__package__.split('.')[0], link=r"https://pypi.org/project/eo-man")
        
        self.get_label_link(text="GitHub: grimmpp/enocean-device-manager", link=AppInfo.get_home_page())

        self.get_label_link(text="GitHub: EnOcean Device Manager Documentation", link=r"https://github.com/grimmpp/enocean-device-manager/tree/main/docs")

        self.get_label_link(text="GitHub: Report a bug or ask for features!", link=AppInfo.get_home_page()+"/issues")

        self.get_label_link(text="Author: "+AppInfo.get_author(), link=r"https://github.com/grimmpp")

        self.get_label_link(text="License - "+AppInfo.get_license(), link=r"https://github.com/grimmpp/enocean-device-manager/blob/main/LICENSE")

        b = DonationButton(popup)
        b.pack(side=TOP, pady=(8,0), padx=5)
        b.focus()

        b = ttk.Button(popup, text="OK", command=popup.destroy)
        b.bind('<Return>', lambda e: popup.destroy())
        b.pack(side=TOP, fill="x", pady=(10,2), padx=10 )
        # b.focus()

        popup.wm_attributes('-toolwindow', 'True')
        popup.resizable (width=False, height=False)
        popup.transient(main)
        popup.grab_set()

        # center
        w = 340
        h = 310
        x = main.winfo_x() + main.winfo_width()/2 - w/2
        y = main.winfo_y() + main.winfo_height()/2 - h/2
        popup.geometry('%dx%d+%d+%d' % (w, h, x, y))

        main.wait_window(popup)

    def callback(self, url):
        webbrowser.open(url)

    def get_label_link(self, text:str, link:str, tooltip:str=None) -> Label:
        if tooltip is None:
            tooltip=link

        l = tk.Label(self.popup, text=text, fg="blue", font=self.label_font, cursor="hand2", anchor="w")
        l.pack(side=TOP, fill="x", pady=2, padx=5)
        l.bind("<Button-1>", lambda e: self.callback(link))
        Hovertip(l,tooltip,300)
