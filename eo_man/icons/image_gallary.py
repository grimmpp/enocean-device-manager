import os
from PIL import Image, ImageTk

# icon list
# https://commons.wikimedia.org/wiki/Comparison_of_icon_sets

class ImageGallery():

    # is needed to keep a reference to the images otherwise they will not displayed in the icons
    _images:dict[str:ImageTk.PhotoImage] = {}

    @classmethod
    def get_image(cls, filename, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        id = f"{filename}_{size[0]}_{size[0]}"
        if id not in cls._images:
            with Image.open(os.path.join(os.path.dirname(__file__), filename)) as img:
                if size is not None:
                    _img = img.resize(size, Image.LANCZOS)
                img = ImageTk.PhotoImage(_img)
                cls._images[id] = img

        return cls._images[id]

    @classmethod
    def get_eo_man_logo(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("Faenza-system-search.png", size)

    @classmethod
    def get_blank(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("blank.png", size)

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
    def get_info_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return cls.get_about_icon(size)

    @classmethod
    def get_github_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("github_icon.png", size)
    
    @classmethod
    def get_software_update_available_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("Software-update-available.png", size)
    
    @classmethod
    def get_fam14_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("fam14.png", size)
    
    @classmethod
    def get_usb300_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("usb300.png", size)
    
    @classmethod
    def get_fam_usb_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("fam-usb2.png", size)
    
    @classmethod
    def get_ftd14_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("ftd14.png", size)
    
    @classmethod
    def get_fgw14_usb_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("fgw14-usb.png", size)
    
    @classmethod
    def get_wireless_network_in_color_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("wireless-network-colored.png", size)
    
    @classmethod
    def get_wireless_network_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("wireless-network-bw.png", size)
    
    @classmethod
    def get_wireless_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("wireless.png", size)
    
    @classmethod
    def get_send_mail(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("mail-send-receive.png", size)
    
    @classmethod
    def get_forward_mail(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("mail-forward.png", size)
    
    @classmethod
    def get_pct14_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("pct14.png", size)
    
    @classmethod
    def get_eul_gateway_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("EUL_device.png", size)
    
    @classmethod
    def get_mgw_piotek_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("mgw_piotek.png", size)
    
    @classmethod
    def get_clear_icon(cls, size:tuple[int:int]=(32,32)) -> ImageTk.PhotoImage:
        return ImageGallery.get_image("Oxygen480-actions-edit-clear.png", size)