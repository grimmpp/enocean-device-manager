import tkinter as tk
from tkinter import *
from tkinter import ttk
import webbrowser
from tkinterhtml import HtmlFrame

from .sponsor_button import SponsorButton

from ..data.app_info import ApplicationInfo as AppInfo


class AboutWindow():

    def __init__(self, main:Tk):
        popup = Toplevel(main)
        popup.wm_title("About")

        f = Frame(popup)

        l = tk.Label(popup, text="About Device Manager", font='Arial 14 bold')
        l.pack(side=TOP, fill="x", pady=10)

        l = tk.Label(popup, text="Version: "+AppInfo.get_version(), anchor="w")
        l.pack(side=TOP, fill="x", pady=2, padx=5)

        text = "GitHub: grimmpp/enocean-device-manager"
        l = tk.Label(popup, text=text, fg="blue", cursor="hand2", anchor="w")
        l.pack(side=TOP, fill="x", pady=2, padx=5)
        l.bind("<Button-1>", lambda e: self.callback(AppInfo.get_home_page()))

        text = "Report a bug or ask for features!"
        l = tk.Label(popup, text=text, fg="blue", cursor="hand2", anchor="w")
        l.pack(side=TOP, fill="x", pady=2, padx=5)
        l.bind("<Button-1>", lambda e: self.callback(AppInfo.get_home_page()+"/issues"))

        l = tk.Label(popup, text="Author: "+AppInfo.get_author(), anchor="w")
        l.pack(side=TOP, fill="x", pady=2, padx=5)

        l = tk.Label(popup, text="License: "+AppInfo.get_license(), anchor="w")
        l.pack(side=TOP, fill="x", pady=2, padx=5)

        b = SponsorButton(popup)
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
        w = 300
        h = 250
        x = main.winfo_x() + main.winfo_width()/2 - w/2
        y = main.winfo_y() + main.winfo_height()/2 - h/2
        popup.geometry('%dx%d+%d+%d' % (w, h, x, y))

        main.wait_window(popup)

    def callback(self, url):
        webbrowser.open_new(url)