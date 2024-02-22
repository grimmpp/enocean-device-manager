from tkinter import *
from tkinter import ttk
import webbrowser
from idlelib.tooltip import Hovertip

from ..icons.image_gallary import ImageGallery

class DonationButton(ttk.Button):

    def __init__(self, master=None, cnf={}, **kw):
        if 'small_icon' in kw and kw['small_icon']:
            image = ImageGallery.get_paypal_icon()
        else:
            image = ImageGallery.get_paypal_me_icon()
        
        super().__init__(master, image=image, cursor="hand2", command=self.open_payapl_me) # , relief=kw.get('relief', FLAT))
        self.image = image

        Hovertip(self,"Donate to support this project!",300)

        self.bind('<Return>', lambda e: self.open_payapl_me())

    def open_payapl_me(self):
        webbrowser.open_new(r"https://paypal.me/grimmpp")