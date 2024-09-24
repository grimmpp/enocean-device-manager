import tkinter as tk
from tkinter import ttk
from tkinter import *
from tkinter.font import *
import webbrowser
from tkinterhtml import HtmlFrame
from PIL import Image, ImageTk
from idlelib.tooltip import Hovertip
from tkscrolledframe import ScrolledFrame

from ..data.const import *

from .donation_button import DonationButton

from ..data.app_info import ApplicationInfo as AppInfo
from ..data.data_helper import EEP_MAPPING


class DeviceInfoWindow():

    def __init__(self, main:Tk):
        popup = Toplevel(main)
        popup.wm_title("Supported Devices")
        self.popup = popup

        self.label_font = Font(name="Arial", underline=True, size=10)

        l = tk.Label(popup, text="Device Information", font='Arial 14 bold')
        l.pack(side=TOP, fill="x", pady=10)

        scrolledFrame = ScrolledFrame(popup, use_ttk=True)
        scrolledFrame.pack(side=LEFT, fill=BOTH, expand=2)

        # Bind the arrow keys and scroll wheel
        scrolledFrame.bind_arrow_keys(popup)
        scrolledFrame.bind_scroll_wheel(popup)

        table = scrolledFrame.display_widget(ttk.Treeview)
        table.pack(expand=True, fill=BOTH)

        table['columns'] = ('#1','#2', '#3', '#4', '#5', '#6', '#7')
        table["show"] = "headings"
        table.heading('#1', text='Brand')
        table.heading('#2', text='Device')
        table.heading('#3', text='Description')
        table.heading('#4', text='EEP (Sensor)')
        table.heading('#5', text='Sender EEP (Controller)')
        table.heading('#6', text='HA Platform')
        table.heading('#7', text='Documentation')

        for m in EEP_MAPPING:
            table.insert('', tk.END, values=(
                m.get('brand', ''), 
                m.get('hw-type', ''),
                m.get('description', ''),
                m.get(CONF_EEP, ''),
                m.get('sender_eep', ''),
                m.get(CONF_TYPE, ''),
                m.get('docs', '')
            ))
            


        popup.wm_attributes('-toolwindow', 'True')
        popup.resizable (width=True, height=True)
        popup.transient(main)

        popup.state('zoomed')

        main.wait_window(popup)
