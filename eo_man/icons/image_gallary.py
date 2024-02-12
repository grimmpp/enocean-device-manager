import os
from PIL import Image, ImageTk

class ImageGallery():

    @classmethod
    def get_image(cls, filename, size:tuple[int:int]=(32,32)):
        img = Image.open(os.path.join(os.path.dirname(__file__), filename))
        if size is not None:
            img = img.resize(size, Image.LANCZOS)
        return ImageTk.PhotoImage(img)

    @classmethod
    def get_ha_logo(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("Home_Assistant_Logo.png", size)
    
    @classmethod
    def get_open_folder_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("Oxygen480-status-folder-open.png", size)
    
    @classmethod
    def get_save_file_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("Oxygen480-actions-document-save.png", size)
    
    @classmethod
    def get_save_file_as_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("Oxygen480-actions-document-save-as.png", size)
    
    @classmethod
    def get_help_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("Oxygen480-actions-help.png", size)
    
    @classmethod
    def get_paypal_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("paypal_icon.png", size)
    
    @classmethod
    def get_paypal_me_icon(cls, size:tuple[int:int]=(214,20)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("paypal_me_badge.png", size)
    
    @classmethod
    def get_about_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("Breathe-about.png", size)

    @classmethod
    def get_github_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("github_icon.png", size)