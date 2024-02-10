import os
from tkinter import *
from PIL import Image, ImageTk
import webbrowser
from idlelib.tooltip import Hovertip

class SponsorButton(Button):

    def __init__(self, master=None, cnf={}, **kw):
        img = Image.open(os.path.join(os.path.dirname(__file__), "../icons/support_this_project.png"))
        img = img.resize((214, 20), Image.LANCZOS)
        eimg = ImageTk.PhotoImage(img)

        super().__init__(master, image=eimg, relief=FLAT, command=lambda: webbrowser.open_new(r"https://paypal.me/grimmpp"))
        self.image = eimg

        Hovertip(self,"Support this project!",300)