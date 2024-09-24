from functools import reduce

from tkinter import *
import tkinter as tk
from tkinter import Tk, ttk

from eltakobus.message import *
from eltakobus.eep import A5_08_01
from eltakobus.util import AddressExpression

from ..controller.app_bus import AppBus, AppBusEventType
from ..controller.serial_controller import SerialController
from ..data import data_helper
from ..data.data_manager import DataManager
from ..data.message_history import MessageHistoryEntry


class SendMessageWindow():

    ADDRESS_COLOR = "green"
    DATA_COLOR = "red"
    STATUS_COLOR = "blue"
    ORG_COLOR = "orange"

    def __init__(self, main:Tk, app_bus:AppBus, data_manager:DataManager, serial_controller:SerialController):
        self.main = main
        self.app_bus = app_bus
        self.data_manager = data_manager
        self.serial_controller = serial_controller

        self.app_bus.add_event_handler(AppBusEventType.CONNECTION_STATUS_CHANGE, self.on_connection_state_changed)

        self.popup = None

        self.data = {0: '01', 1: '00', 2:'00', 3:'09'}
        self.address = {0: '00', 1: '00', 2:'00', 3:'00'}
        self.status = '00'

        self.entered_keys = ''
        self.current_telegram = None

    def show_window(self):
        if self.popup:
            self.center_window()
            return
        
        self.popup = Toplevel(self.main, padx=4, pady=4)
        self.popup.wm_title("Send Message")

        self.col_widths = [90, 204, 8, 360, 28]
        for idx, w in enumerate(self.col_widths):
            self.popup.columnconfigure(idx, minsize=w)
        
        for idx in range(0,8):
            self.popup.rowconfigure(idx, weight=0)
        

        _pady = (4,0)
        _padx = (2,0)

        row = 0
        l = ttk.Label(self.popup, text="Message Type: ", foreground=self.ORG_COLOR)
        l.grid(row=row, column=0, sticky=W)

        self.l_msg_type = ttk.Label(self.popup, text='')
        self.l_msg_type.grid(row=row, column=1, sticky=W, pady=_pady, padx=_padx)
        self.cb_msg_type = ttk.Combobox(self.popup, state="readonly", width="18") 
        self.cb_msg_type['values'] = ['RPS (Org = 0x05)', '1BS (Org = 0x06)', '4BS (Org = 0x07)']
        self.cb_msg_type.set('4BS (Org = 0x07)')
        self.cb_msg_type.grid(row=row, column=1, sticky=W, pady=_pady, padx=_padx)
        self.cb_msg_type.bind('<<ComboboxSelected>>', self.on_message_type_changed)


        row += 1
        l = ttk.Label(self.popup, text="Data: ", foreground=self.DATA_COLOR)
        l.grid(row=row, column=0, sticky=W, pady=_pady, padx=_padx)

        # data fields
        f = ttk.Frame(self.popup)
        f.grid(row=row, column=1, sticky=W, pady=_pady, padx=_padx)
        self.cb_data_0 = ttk.Combobox(f, state="readonly", width="3")
        self.cb_data_1 = ttk.Combobox(f, state="readonly", width="3")
        self.cb_data_2 = ttk.Combobox(f, state="readonly", width="3")
        self.cb_data_3 = ttk.Combobox(f, state="readonly", width="3")
        for idx, cb_d in enumerate([self.cb_data_0, self.cb_data_1, self.cb_data_2, self.cb_data_3]):
            cb_d['values'] = [data_helper.a2s(i,1) for i in range(0,256)]
            cb_d.set(self.data[idx])
            cb_d.bind('<<ComboboxSelected>>', self.show_message )
            cb_d.bind('<FocusIn>', self.on_focus_combobox)
            cb_d.bind('<Key>', self.select_by_entered_keys)
            cb_d.bind('<Return>', lambda e: self.show_message(e, True))
            cb_d.pack(side=LEFT)

        
        row += 1
        l = ttk.Label(self.popup, text="Sender Id: ", foreground=self.ADDRESS_COLOR)
        l.grid(row=row, column=0, sticky=W, pady=_pady, padx=_padx)
        f = ttk.Frame(self.popup)
        f.grid(row=row, column=1, sticky=W, pady=_pady, padx=_padx)

        # address field
        self.cb_sender_id_0 = ttk.Combobox(f, state="readonly", width="3")
        self.cb_sender_id_1 = ttk.Combobox(f, state="readonly", width="3")
        self.cb_sender_id_2 = ttk.Combobox(f, state="readonly", width="3")
        self.cb_sender_id_3 = ttk.Combobox(f, state="readonly", width="3")
        for cb_s in [self.cb_sender_id_0, self.cb_sender_id_1, self.cb_sender_id_2, self.cb_sender_id_3]:
            cb_s['values'] = [data_helper.a2s(i,1) for i in range(0,256)]
            cb_s.bind('<<ComboboxSelected>>', self.show_message )
            cb_s.bind('<FocusIn>', self.on_focus_combobox)
            cb_s.bind('<Key>', self.select_by_entered_keys)
            cb_s.bind('<Return>', lambda e: self.show_message(e, True))
            cb_s.pack(side=LEFT)
        self.set_sender_ids()
        
        # status
        row += 1
        l = ttk.Label(self.popup, text="Status: ", foreground=self.STATUS_COLOR)
        l.grid(row=row, column=0, sticky=W, pady=_pady, padx=_padx)

        self.cb_status = ttk.Combobox(self.popup, width="3", state="readonly")
        self.cb_status['values'] = [data_helper.a2s(i,1) for i in range(0,256)]
        self.cb_status.set(self.status)
        self.cb_status.bind('<<ComboboxSelected>>', self.show_message )
        self.cb_status.bind('<FocusIn>', self.on_focus_combobox)
        self.cb_status.bind('<Key>', self.select_by_entered_keys)
        self.cb_status.bind('<Return>', lambda e: self.show_message(e, True))
        self.cb_status.grid(row=row, column=1, sticky=W, pady=_pady, padx=_padx)


        # out going message
        row += 1
        self.out_going_msg_boolvar = BooleanVar()
        self.out_going_msg_boolvar.set(True)
        cb = ttk.Checkbutton(self.popup, text="Out-Going Telegram", command=self.show_message, variable=self.out_going_msg_boolvar)
        cb.grid(row=row, sticky=W, column=1, pady=_pady, padx=_padx)


        row += 1
        l = ttk.Label(self.popup, text="")
        l.grid(row=row, column=0, sticky=W, columnspan=2, pady=_pady, padx=_padx)


        row += 1
        l = ttk.Label(self.popup, text="Telegram:")
        l.grid(row=row, column=0, sticky=W, columnspan=2, pady=_pady, padx=_padx)


        row += 1
        self.popup.rowconfigure(row, weight=1)
        self.f_telegram = ttk.Frame(self.popup)
        self.f_telegram.grid(row=row, column=0, sticky=NSEW, columnspan=2, pady=_pady, padx=_padx)


        row += 1
        l = ttk.Label(self.popup, text="")
        l.grid(row=row, column=0, sticky=W, columnspan=2, pady=_pady, padx=_padx)


        # close button
        row += 1
        b_close = ttk.Button(self.popup, text="Close", command=self.close)
        b_close.bind('<Return>', lambda e: self.close())
        b_close.grid(row=row, column=0, sticky=EW)

        # send button
        self.b_send = ttk.Button(self.popup, text="Send", command=lambda send=True: self.show_message(None, send))
        if not self.serial_controller.is_serial_connection_active():
            self.b_send.config(state=DISABLED)
        self.b_send.bind('<Return>', lambda event, send=True: self.show_message(event, send))
        self.b_send.grid(row=row, column=1, sticky=EW, padx=(0,8))


        ttk.Separator(self.popup, orient=VERTICAL).grid(column=2, row=0, rowspan=10, sticky=NSEW)

        # favourites

        row = 0
        l = ttk.Label(self.popup, text="Favourites")
        l.grid(row=row, column=3, sticky=W)

        row += 1
        rowspan = 7
        f = ttk.Frame(self.popup, width=self.col_widths[3])
        f.grid(row=row, rowspan=rowspan, column=3, sticky=NSEW)
        s = ttk.Style()
        s.configure('SendMessageWindow.Treeview', rowheight=38)
        scrollbar = ttk.Scrollbar(f)
        self.lb_fav_msg = ttk.Treeview(f, yscrollcommand=scrollbar.set, show="tree", height=4, selectmode='browse', style='SendMessageWindow.Treeview')
        scrollbar.configure(command=self.lb_fav_msg.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.lb_fav_msg.pack(side=LEFT, fill=BOTH, expand=True)    

        if self.data_manager.send_message_template_list:
            for history_entry in self.data_manager.send_message_template_list:
                msg = ESP2Message.parse(history_entry.message)
                org = msg.body[1]
                data = msg.body[2:6]
                address = msg.body[6:10]
                status = msg.body[10]
                outgoing = {(3 << 5) + 11: True, (0 << 5) + 11: False}[msg.body[0]]

                if org == 7:    msg = Regular4BSMessage(address, status, data, outgoing)
                elif org == 6:  msg = Regular1BSMessage(address, status, data[0:1], outgoing)
                elif org == 5:  msg = RPSMessage(address, status, data[0:1], outgoing)

                self.add_fav_msg(msg, history_entry.name)


        row += rowspan
        f = ttk.Frame(self.popup)
        f.grid(row=row, column=3, sticky=E+W)
        self.b_add_fav = ttk.Button(f, text="Add as", command=lambda: self.add_fav_msg(self.current_telegram) )
        self.b_add_fav.bind('<Return>', lambda e: self.add_fav_msg(self.current_telegram))
        self.b_add_fav.pack(side=LEFT, pady=(4,2), padx=(0,2))
        self.e_name = ttk.Entry(f)
        self.e_name.bind('<Return>', lambda e: self.add_fav_msg(self.current_telegram))
        self.e_name.pack(fill=X, pady=(4,2), padx=(0,16))

        row += 1
        f = ttk.Frame(self.popup)
        f.grid(row=row, column=3, sticky=E+W)

        self.b_remove_fav = ttk.Button(f, text="Remove", command=self.remove_fav_msg)
        self.b_remove_fav.bind('<Return>', lambda e: self.remove_fav_msg())
        self.b_remove_fav.pack(side=LEFT, pady=2, padx=(0,2))
        self.b_apply_fav = ttk.Button(f, text="Apply", command=self.apply_fav_msg)
        self.b_apply_fav.bind('<Return>', lambda e: self.apply_fav_msg())
        self.b_apply_fav.pack(fill=X, pady=2, padx=(0,16))


        self.show_message(None)

        # self.popup.wm_attributes('-toolwindow', 'True')
        self.popup.protocol("WM_DELETE_WINDOW", self.close)
        self.popup.resizable (width=False, height=False)
        
        self.popup.after(10, self.center_window)

        self.main.wait_window(self.popup)


    def remove_fav_msg(self):
        if self.lb_fav_msg.selection():
            for item in self.lb_fav_msg.selection():
                self.lb_fav_msg.delete(item)

        self.send_update_of_current_message_templates()
        

    def send_update_of_current_message_templates(self):
        entries = list()
        for c_id in self.lb_fav_msg.get_children():
           
            name = self.lb_fav_msg.item(c_id)['text'].split('\n')[0]
            msg = bytes.fromhex(c_id)

            entries.append(MessageHistoryEntry(name, msg))

        self.app_bus.fire_event(AppBusEventType.SEND_MESSAGE_TEMPLATE_LIST_UPDATED, entries)


    def add_fav_msg(self, msg:EltakoMessage,name:str=''):
        if msg:
            id = data_helper.b2s(msg.serialize(), separator='')

            text = ''
            if isinstance(msg, Regular4BSMessage): text += "4BS: "
            elif isinstance(msg, Regular1BSMessage): text += "1BS: "
            elif isinstance(msg, RPSMessage): text += "RPS: "

            text += f"Data: {data_helper.b2s(msg.data, ' ')}, "
            text += f"Address: {data_helper.b2s(msg.address, ' ')}, "
            text += "Status: {:02X}".format(msg.status)

            if not name and self.e_name.get():
                name = self.e_name.get()
                self.e_name.delete(0, END)

            text = f"{name}\n{text}"

            if not self.lb_fav_msg.exists(id):
                self.lb_fav_msg.insert(parent="", index="end", iid=id, text=text)
            else:
                self.lb_fav_msg.item(id, text=text)

            self.send_update_of_current_message_templates()

    def apply_fav_msg(self):
        if self.lb_fav_msg.selection():
            msg = ESP2Message.parse(bytes.fromhex(self.lb_fav_msg.selection()[0]))
            data = msg.body[2:6]
            address = msg.body[6:10]
            status = msg.body[10]
            outgoing = {(3 << 5) + 11: True, (0 << 5) + 11: False}[msg.body[0]]

            item_text = self.lb_fav_msg.item(self.lb_fav_msg.selection()[0])['text']
            if '4BS' in item_text:   self.cb_msg_type.set('4BS (Org = 0x07)')
            elif '1BS' in item_text: self.cb_msg_type.set('1BS (Org = 0x06)')
            elif 'RPS' in item_text: self.cb_msg_type.set('RPS (Org = 0x05)')
            self.on_message_type_changed()

            self.cb_data_0.set( "{:02X}".format(data[0]) )
            if '4BS' in item_text:
                self.cb_data_1.set( "{:02X}".format(data[1]) )
                self.cb_data_2.set( "{:02X}".format(data[2]) )
                self.cb_data_3.set( "{:02X}".format(data[3]) )

            self.cb_sender_id_3.set( "{:02X}".format(address[3]) )
            if str(self.cb_sender_id_0['state']) not in ['disabled']:
                self.cb_sender_id_0.set( "{:02X}".format(address[0]) )
                self.cb_sender_id_1.set( "{:02X}".format(address[1]) )
                self.cb_sender_id_2.set( "{:02X}".format(address[2]) )

            self.cb_status.set( "{:02X}".format(status) )
            self.out_going_msg_boolvar.set(outgoing)

            self.show_message()


    def on_focus_combobox(self, event=None):
        self.entered_keys = ''


    def select_by_entered_keys(self, event=None):

        if event.char.upper() not in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D', 'E', 'F']:
            return

        if event is not None:
            if len(self.entered_keys) < 2:
                self.entered_keys += event.char.upper()
            else:
                self.entered_keys = event.char.upper()

        cb:ttk.Combobox = self.popup.focus_get()
        if len(self.entered_keys) == 2:
            cb.set(self.entered_keys)
        elif len(self.entered_keys) == 1:
            for v in cb['values']:
                if v[0] == self.entered_keys:
                    cb.set(v)
                    break

        self.show_message()


    def on_message_type_changed(self, event=None):
        msg_type = self.cb_msg_type.get()
        for idx, cb_d in enumerate([self.cb_data_1, self.cb_data_2, self.cb_data_3]):
            if '4BS' not in msg_type:
                if cb_d.get() != '': self.data[idx+1] = cb_d.get()
                cb_d.config(state=DISABLED)
                cb_d.set('')
            else:
                cb_d.config(state="readonly")
                cb_d.set(self.data[idx+1])

        self.show_message(event)


    def center_window(self):
        if self.popup:
            w = reduce(lambda x, y: x + y, self.col_widths) # popup.winfo_width()
            h = self.popup.winfo_height()
            x = self.main.winfo_x() + self.main.winfo_width()/2 - w/2
            y = self.main.winfo_y() + self.main.winfo_height()/2 - h/2
            self.popup.geometry('%dx%d+%d+%d' % (w, h, x, y))
            self.popup.focus()
            self.popup.state(newstate=NORMAL)


    def close(self):
        if self.popup:
            self.popup.destroy()
            self.popup = None
    
    
    def set_sender_ids(self):
        # not wired gateway
        if not self.serial_controller.is_connected_gateway_device_bus():
            base_id = self.serial_controller.current_base_id
        else:
            base_id = '00-00-B0-00'
        
        if self.serial_controller.current_base_id and not self.serial_controller.is_connected_gateway_device_bus():
            base_id = self.serial_controller.current_base_id
            self.cb_sender_id_0.config(state="readonly")
            self.cb_sender_id_1.config(state="readonly")
            self.cb_sender_id_2.config(state="readonly")
            self.cb_sender_id_0.set( base_id.split('-')[0] )
            self.cb_sender_id_1.set( base_id.split('-')[1] )
            self.cb_sender_id_2.set( base_id.split('-')[2] )
            self.cb_sender_id_3.set(self.address[3])
            self.cb_sender_id_0.config(state=DISABLED)
            self.cb_sender_id_1.config(state=DISABLED)
            self.cb_sender_id_2.config(state=DISABLED)

            self.cb_sender_id_3['values'] = [data_helper.a2s(i+int(base_id.split('-')[3]) ,1) for i in range(0,128)]
            self.cb_sender_id_3.set(base_id.split('-')[3])

        else:
            self.cb_sender_id_0.config(state="readonly")
            self.cb_sender_id_1.config(state="readonly")
            self.cb_sender_id_2.config(state="readonly")

            self.cb_sender_id_3['values'] = [data_helper.a2s(i,1) for i in range(0,256)]
            
            self.cb_sender_id_0.set(self.address[0])
            self.cb_sender_id_1.set(self.address[1])
            self.cb_sender_id_2.set(self.address[2])
            self.cb_sender_id_3.set(self.address[3])


    def on_connection_state_changed(self, data):
        if self.popup:
            if data.get('connected'):
                self.b_send.config(state=NORMAL)
            else:
                self.b_send.config(state=DISABLED)
            self.set_sender_ids()


    def show_message(self, event=None, send:bool=False):
        msg_type = self.cb_msg_type.get()
        try:
            self.address[0] = self.cb_sender_id_0.get()
            self.address[1] = self.cb_sender_id_1.get()
            self.address[2] = self.cb_sender_id_2.get()
            self.address[3] = self.cb_sender_id_3.get()
            sender_id_str = '-'.join(self.address.values())
            sender_id = AddressExpression.parse( sender_id_str )[0]
            data_str = f"{self.cb_data_0.get()}-{self.cb_data_1.get()}-{self.cb_data_2.get()}-{self.cb_data_3.get()}".replace('---', '-00-00-00')
            data = AddressExpression.parse( data_str )[0]
            self.status = self.cb_status.get()
            status = int(self.cb_status.get(), 16)
            
            if '4BS' in msg_type:
                msg = Regular4BSMessage(sender_id, status, data, self.out_going_msg_boolvar.get())
            elif '1BS' in msg_type:
                data = data[0:1]
                msg = Regular1BSMessage(sender_id, status, data, self.out_going_msg_boolvar.get())
            elif 'RPS' in msg_type:
                data = data[0:1]
                msg = RPSMessage(sender_id, status, data, self.out_going_msg_boolvar.get())

            self.current_telegram = msg

            msg_text = b2a(msg.serialize()).upper()
            if '4BS' not in msg_type: msg_text = msg_text[0:15] + msg_text[24:]
            self.show_telegram_text(msg_text, msg_type)

            if send and self.serial_controller.is_serial_connection_active():
                self.serial_controller.send_message(msg)
                self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': f"Send Message: {str(msg)}", 'color':'green', 'log-level':'INFO'})
        except Exception as e:
            self.show_telegram_text('Invalid telegram!')
            self.current_telegram = None


    def show_telegram_text(self, text:str, msg_type:str=''):
        for widgets in self.f_telegram.winfo_children():
            widgets.destroy()

        if 'invalid' in text.lower():
            l = ttk.Label(self.f_telegram, text=text, foreground='red')
            l.pack(side=LEFT, anchor=NW, padx=(12,0))
        else:
            l = ttk.Label(self.f_telegram, text=text[0:9], foreground='darkgrey')
            l.pack(side=LEFT, anchor=NW, padx=(12,0))

            # org
            l = ttk.Label(self.f_telegram, text=text[9:12], foreground=self.ORG_COLOR, font = ('Sans','10','bold'))
            l.pack(side=LEFT, anchor=NW)

            # data
            data_end = 24
            if '4BS' not in msg_type: data_end = 12 + 3
            l = ttk.Label(self.f_telegram, text=text[12:data_end], foreground=self.DATA_COLOR)
            l.pack(side=LEFT, anchor=NW)

            # sender id
            sender_end = data_end + 12
            l = ttk.Label(self.f_telegram, text=text[data_end:sender_end], foreground=self.ADDRESS_COLOR)
            l.pack(side=LEFT, anchor=NW)

            # status
            l = ttk.Label(self.f_telegram, text=text[sender_end:sender_end+3], foreground=self.STATUS_COLOR)
            l.pack(side=LEFT, anchor=NW)

            # check sum
            l = ttk.Label(self.f_telegram, text=text[sender_end+3:sender_end+6], foreground='darkgrey')
            l.pack(side=LEFT, anchor=NW)