import tkinter as tk
from tkinter import *
from image_gallary import ImageGallery

# Create the main window
window = tk.Tk()

# Create the menu bar
menu_bar = tk.Menu(window)

# Create the menu Menu1
menu_1 = tk.Menu(menu_bar, tearoff=0)

# Create a photo image
item_1_icon = ImageGallery.get_ha_logo(size=(16,16))

# Add items for Menu1
# menu_1.add_command(label="Item1", image=ImageGallery.get_open_folder_icon(size=(16,16)), compound="left", command=lambda: print("test"), accelerator="STRG+5")
menu_1.add_command(label="Item2", image=item_1_icon, compound=LEFT)
menu_1.add_command(label="Item3", image=ImageGallery.get_ha_logo(size=(16,16)), compound=LEFT)

# Add the menu to the menu bar
menu_bar.add_cascade(label="Menu1", menu=menu_1)

# Attach the menu bar to the main window
window.config(menu=menu_bar)

# Start the Tkinter event loop
window.mainloop()