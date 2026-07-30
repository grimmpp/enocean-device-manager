from tkinter import *
from tkinter import ttk

from ..controller.app_bus import AppBus, AppBusEventType
from ..data.const import *
from ..data.homeassistant.const import CONF_ID, CONF_NAME
from ..data.filter import DataFilter
from ..data.data_manager import DataManager, Device
from ..data import data_helper
from ..icons.image_gallary import ImageGallery

from eltakobus.util import b2s
from eltakobus.message import EltakoMessage, RPSMessage, Regular1BSMessage, Regular4BSMessage, EltakoWrappedRPS


class DeviceTable():

    ICON_SIZE = (20,20)
    NON_BUS_DEVICE_LABEL:str="Distributed Devices"
    BLINK_INTERVAL_IN_MS:int=500
    BLINK_TOGGLES:int=4         # number of background changes => 2 blinks

    def __init__(self, main: Tk, app_bus:AppBus, data_manager:DataManager):

        self.blinking_enabled = True
        self._related_rows:set = set()          # rows of devices related to the selected one
        self._blinking_rows:dict = {}           # row -> remaining background changes
        self._blink_highlighted_rows:set = set()# rows currently highlighted by the blinking
        self.pane = ttk.Frame(main, padding=2)
        # self.pane.grid(row=0, column=0, sticky=W+E+N+S)
        self.root = self.pane

        # Scrollbar
        yscrollbar = ttk.Scrollbar(self.pane, orient=VERTICAL)
        yscrollbar.pack(side=RIGHT, fill=Y)

        xscrollbar = ttk.Scrollbar(self.pane, orient=HORIZONTAL)
        xscrollbar.pack(side=BOTTOM, fill=X)

        # Treeview
        columns = ("Address", "External Address", "Device Type", "Key Function", "Comment", "Export to HA Config", "HA Platform", "Device EEP", "Sender Address", "Sender EEP", "Signal (dBm)")
        self.SIGNAL_COL = len(columns) - 1  # index of the "Signal (dBm)" column
        self.treeview = ttk.Treeview(
            self.pane,
            show="tree headings",
            selectmode="browse",
            yscrollcommand=yscrollbar.set,
            xscrollcommand=xscrollbar.set,
            columns=(0,1,2,3,4,5,6,7,8,9,10),
        )
        self.treeview.pack(expand=True, fill=BOTH)
        yscrollbar.config(command=self.treeview.yview)
        xscrollbar.config(command=self.treeview.xview)

        def sort_rows_in_treeview(tree:ttk.Treeview, col_i:int, descending:bool, partent:str=''):
            data = [(tree.set(item, col_i), item) for item in tree.get_children(partent)]
            data.sort(reverse=descending)
            for index, (val, item) in enumerate(data):
                tree.move(item, partent, index)
            
            for item in tree.get_children(partent):
                sort_rows_in_treeview(tree, col_i, descending, item)

        def sort_treeview(tree:ttk.Treeview, col:int, descending:bool):
            i = columns.index(col)
            for item in tree.get_children(''):
                sort_rows_in_treeview(tree, i, descending, item)
            tree.heading(i, command=lambda c=col, d=(not descending): sort_treeview(tree, c, d))

        self.treeview.column('#0', anchor="w", width=250, minwidth=250)#, stretch=NO)
        for col in columns:
            # Treeview headings
            i = columns.index(col)
            if col in ['Key Function']:
                self.treeview.column(i, anchor="w", width=250, minwidth=250)#, stretch=NO)
            elif col in ['Signal (dBm)']:
                self.treeview.column(i, anchor="w", width=150, minwidth=150)#, stretch=NO)
            else:
                self.treeview.column(i, anchor="w", width=80, minwidth=80)#, stretch=NO)
            self.treeview.heading(i, text=col, anchor="center", command=lambda c=col, d=False: sort_treeview(self.treeview, c, d))
        
        # self.menu = Menu(main, tearoff=0)
        # self.menu.add_command(label="Cut")
        # self.menu.add_command(label="Copy")
        # self.menu.add_command(label="Paste")
        # self.menu.add_command(label="Reload")
        # self.menu.add_separator()
        # self.menu.add_command(label="Rename")

        # Tk does not guarantee which tag wins if a row has both tags. Therefore
        # only one of them is ever set on a row (see _apply_row_background).
        self.treeview.tag_configure('related_devices', background='lightgreen')
        self.treeview.tag_configure('blinking', background='lightblue')

        # self.treeview.bind('<ButtonRelease-1>', self.on_selected)
        self.treeview.bind('<<TreeviewSelect>>', self.on_selected)
        # self.treeview.bind("<Button-3>", self.show_context_menu)

        self.check_if_wireless_network_exists()

        self.current_data_filter:DataFilter = None
        self.app_bus = app_bus
        self.app_bus.add_event_handler(AppBusEventType.DEVICE_SCAN_STATUS, self.device_scan_status_handler)
        self.app_bus.add_event_handler(AppBusEventType.UPDATE_DEVICE_REPRESENTATION, self.update_device_representation_handler)
        self.app_bus.add_event_handler(AppBusEventType.UPDATE_SENSOR_REPRESENTATION, self.update_sensor_representation_handler)
        self.app_bus.add_event_handler(AppBusEventType.LOAD_FILE, self._reset)
        self.app_bus.add_event_handler(AppBusEventType.SET_DATA_TABLE_FILTER, self._set_data_filter_handler)
        self.app_bus.add_event_handler(AppBusEventType.SERIAL_CALLBACK, self._serial_callback_handler)

        self.data_manager = data_manager

        # initial loading
        if self.data_manager.selected_data_filter_name is not None:
            self._set_data_filter_handler(self.data_manager.data_fitlers[self.data_manager.selected_data_filter_name])
        for d in self.data_manager.devices.values():
            parent = self.NON_BUS_DEVICE_LABEL if not d.is_bus_device() else None
            self.update_device_handler(d, parent)


    def _set_data_filter_handler(self, filter):
        self.current_data_filter = filter

        self._reset(None)
        for d in self.data_manager.devices.values():
            if d.bus_device:
                self.update_device_handler(d)
            else:
                self.update_device_handler(d, parent=self.NON_BUS_DEVICE_LABEL)


    def _reset(self, data):
        for item in self.treeview.get_children():
            self.treeview.delete(item)
        self._related_rows.clear()
        self._blinking_rows.clear()
        self._blink_highlighted_rows.clear()
        self.check_if_wireless_network_exists()


    def on_selected(self, event):
        device_external_id = self.treeview.focus()
        device = self.data_manager.get_device_by_id(device_external_id)
        if device is not None:
            self.app_bus.fire_event(AppBusEventType.SELECTED_DEVICE, device)

        self.mark_related_elements(device_external_id)


    def _apply_row_background(self, iid:str) -> None:
        """sets the background of a row: blinking wins, otherwise the marking of related devices is shown"""
        if not self.treeview.exists(iid):
            return

        if iid in self._blink_highlighted_rows:
            tags = ('blinking',)
        elif iid in self._related_rows:
            tags = ('related_devices',)
        else:
            tags = ()

        self.treeview.item(iid, tags=tags)


    def mark_related_elements(self, device_external_id:str) -> None:
        """highlights all devices which are entered in the memory of the selected device and vice versa"""
        related_rows = {d.external_id for d in self.data_manager.get_related_devices(device_external_id)}

        affected_rows = self._related_rows | related_rows
        self._related_rows = related_rows

        for iid in affected_rows:
            self._apply_row_background(iid)


    def show_context_menu(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()


    def insert_device(self, device:Device):
        v=("", b2s(device.address[0]), "", "")
        self.treeview.insert(parent="", index="end", text=device.id_string, values=v)

        
    def device_scan_status_handler(self, status:str):
        if status in ['STARTED']:
            #TODO: disable treeview or menue of it
            # self.treeview.config(state=DISABLED)
            pass
        elif status in ['FINISHED']:
            #TODO: enable treeview or menue of it
            # self.treeview.config(state=NORMAL)
            pass


    def add_fam14(self, d:Device):
        if d.is_fam14():
            if not self.treeview.exists(d.base_id):
                text = ""
                comment = ""
                text = d.name
                comment = d.comment if d.comment is not None else "" 
                in_ha = d.use_in_ha
                self.treeview.insert(parent="", 
                                     index=0, 
                                     iid=d.external_id, 
                                     text=" " + text, 
                                     values=("", "", "", "", comment, in_ha, "", "", ""),
                                     image=ImageGallery.get_fam14_icon(self.ICON_SIZE),
                                     open=True)
            else:
                self.treeview.item(d.base_id, 
                                   text=" " + d.name, 
                                   values=("", "", "", "", d.comment, d.use_in_ha, "", "", ""),
                                   image=ImageGallery.get_fam14_icon(self.ICON_SIZE), 
                                   open=True)


    def check_if_wireless_network_exists(self):
        id = self.NON_BUS_DEVICE_LABEL
        if not self.treeview.exists(id):
            self.treeview.insert(parent="", 
                                 index="end", 
                                 iid=id, 
                                 text=" " + self.NON_BUS_DEVICE_LABEL, 
                                 values=("", "", "", "", "", "", "", "", ""), 
                                 image=ImageGallery.get_wireless_icon(self.ICON_SIZE),
                                 open=True)


    def update_device_representation_handler(self, d:Device):
        self.update_device_handler(d)


    def update_device_handler(self, d:Device, parent:str=None):

        if self.current_data_filter is not None and not self.current_data_filter.filter_device(d):
            return

        if not d.is_fam14():
            in_ha = d.use_in_ha
            ha_pl = "" if d.ha_platform is None else d.ha_platform
            eep = "" if d.eep is None else d.eep
            device_type = "" if d.device_type is None else d.device_type
            key_func = "" if d.key_function is None else d.key_function
            comment = "" if d.comment is None else d.comment
            sender_adr = "" if 'sender' not in d.additional_fields else d.additional_fields['sender'][CONF_ID]
            sender_eep = "" if 'sender' not in d.additional_fields else d.additional_fields['sender'][CONF_EEP]
            
            if d.is_usb300():
                image = ImageGallery.get_usb300_icon(self.ICON_SIZE)
            elif d.is_fam_usb():
                image = ImageGallery.get_fam_usb_icon(self.ICON_SIZE)
            elif d.is_fgw14_usb():
                image = ImageGallery.get_fgw14_usb_icon(self.ICON_SIZE)
            elif d.is_ftd14():
                image = ImageGallery.get_ftd14_icon(self.ICON_SIZE)
            elif d.is_EUL_Wifi_gw():
                image = ImageGallery.get_eul_gateway_icon(self.ICON_SIZE)
            elif d.is_mgw():
                image = ImageGallery.get_mgw_piotek_icon(self.ICON_SIZE)
            else:
                image = ImageGallery.get_blank(self.ICON_SIZE)

            _parent = d.base_id if parent is None else parent
            if not self.treeview.exists(_parent): self.add_fam14(self.data_manager.devices[_parent])
            if not self.treeview.exists(d.external_id):
                self.treeview.insert(parent=_parent, 
                                     index="end", 
                                     iid=d.external_id, 
                                     text=" " + d.name, 
                                     values=(d.address, d.external_id, device_type, key_func, comment, in_ha, ha_pl, eep, sender_adr, sender_eep), 
                                     open=True)
                self.treeview.item(d.external_id, image=image)
            else:
                # update device
                self.treeview.item(d.external_id, 
                                   text=" " + d.name, 
                                   values=(d.address, d.external_id, device_type, key_func, comment, in_ha, ha_pl, eep, sender_adr, sender_eep), 
                                   image=image,
                                   open=True)
                if self.treeview.parent(d.external_id) != _parent:
                    self.treeview.move(d.external_id, _parent, 0)
        else:
            self.add_fam14(d)
        # self.trigger_blinking(d.external_id)
            

    def _serial_callback_handler(self, data:dict):
        message:EltakoMessage = data['msg']
        current_base_id:str = data['base_id']

        if type(message) in [RPSMessage, Regular1BSMessage, Regular4BSMessage, EltakoWrappedRPS]:
            if isinstance(message.address, int):
                adr = data_helper.a2s(message.address)
            else:
                adr = b2s(message.address)

            # resolve the treeview row (iid) the telegram belongs to
            ext_id = None
            if not adr.startswith('00-00-00-'):
                ext_id = adr
            elif current_base_id is not None:
                d:Device = self.data_manager.find_device_by_local_address(adr, current_base_id)
                if d is not None:
                    ext_id = d.external_id

            if ext_id is not None:
                self.trigger_blinking(ext_id)

                # show the signal strength of the received telegram (ESP3 radio only)
                rssi = data.get('rssi', None)
                if rssi is not None and self.treeview.exists(ext_id):
                    self.treeview.set(ext_id, self.SIGNAL_COL, data_helper.format_rssi(rssi))


    def trigger_blinking(self, external_id:str):
        if not self.blinking_enabled or not self.treeview.exists(external_id):
            return

        # a telegram arriving while the row is still blinking just restarts the sequence
        if external_id in self._blinking_rows:
            self._blinking_rows[external_id] = self.BLINK_TOGGLES
            return

        self._blinking_rows[external_id] = self.BLINK_TOGGLES
        self.treeview.after(0, lambda ext_id=external_id: self._blink_step(ext_id))


    def _blink_step(self, ext_id:str):
        remaining = self._blinking_rows.get(ext_id, 0)

        if remaining <= 0 or not self.treeview.exists(ext_id):
            self._blinking_rows.pop(ext_id, None)
            self._blink_highlighted_rows.discard(ext_id)
            # brings back the background the row had before blinking
            # (green if it is marked as related device)
            self._apply_row_background(ext_id)
            return

        self._blinking_rows[ext_id] = remaining - 1
        if ext_id in self._blink_highlighted_rows:
            self._blink_highlighted_rows.discard(ext_id)
        else:
            self._blink_highlighted_rows.add(ext_id)
        self._apply_row_background(ext_id)

        self.treeview.after(self.BLINK_INTERVAL_IN_MS, lambda: self._blink_step(ext_id))


    def update_sensor_representation_handler(self, d:Device):
        self.update_device_handler(d, parent=self.NON_BUS_DEVICE_LABEL)