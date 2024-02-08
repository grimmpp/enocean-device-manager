import tkinter as tk
from tkinter import *
from tkinter import ttk
from tkinter import messagebox

from .checklistcombobox import ChecklistCombobox

from ..controller.app_bus import AppBus, AppBusEventType
from ..data.data_manager import DataManager
from ..data import data_helper
from ..data.const import CONF_EEP
from ..data.filter import DataFilter


class FilterBar():
    
    def __init__(self, main: Tk, app_bus:AppBus, data_manager:DataManager, row:int):
        self.app_bus = app_bus
        self.data_manager = data_manager
        
        f = LabelFrame(main, text= "Tabel Filter", bd=1, relief=SUNKEN)
        f.grid(row=row, column=0, columnspan=1, sticky=W+E+N+S, pady=(0,2), padx=2)
        self.root = f

        # filter name
        col = 0
        l = Label(f, text="Filter Name:")
        l.grid(row=0, column=col, padx=(3,3), sticky=W)

        self.cb_filtername = ttk.Combobox(f, width="14") 
        self.cb_filtername.grid(row=1, column=col, padx=(0,3) )
        self.cb_filtername.bind('<Return>', lambda e: [self.load_filter(), self.add_filter(False), self.apply_filter(e, True)] )

        col += 1
        self.btn_save_filter = Button(f, text="Load", command=self.load_filter)
        self.btn_save_filter.grid(row=1, column=col, padx=(0,3))

        col += 1
        self.btn_save_filter = Button(f, text="Remove", command=self.remove_filter)
        self.btn_save_filter.grid(row=0, column=col, padx=(0,3) )

        self.btn_save_filter = Button(f, text="Add", command=self.add_filter)
        self.btn_save_filter.grid(row=1, column=col, padx=(0,3), sticky=W+E )

        # global filter
        col += 1
        l = Label(f, text="Global Filter:")
        l.grid(row=0, column=col, padx=(0,3), sticky=W)

        self.global_filter = Entry(f, width="14") 
        self.global_filter.grid(row=1, column=col, padx=(0,3) )
        self.global_filter.bind('<Return>', self.apply_filter)
        self.global_filter.bind("<KeyRelease>", lambda e: self.cb_filtername.set('') )

        # address
        col += 1
        l = Label(f, text="Address:")
        l.grid(row=0, column=col, padx=(0,3), sticky=W)

        self.cb_device_address = Entry(f, width="14") 
        self.cb_device_address.grid(row=1, column=col, padx=(0,3) )
        self.cb_device_address.bind('<Return>', self.apply_filter)
        self.cb_device_address.bind("<KeyRelease>", lambda e: self.cb_filtername.set('') )

        # external address
        col += 1
        l = Label(f, text="External Address:")
        l.grid(row=0, column=col, padx=(0,3), sticky=W)

        self.cb_external_address = Entry(f, width="14") 
        self.cb_external_address.grid(row=1, column=col, padx=(0,3) )
        self.cb_external_address.bind('<Return>', self.apply_filter)
        self.cb_external_address.bind("<KeyRelease>", lambda e: self.cb_filtername.set('') )

        # device type
        col += 1
        l = Label(f, text="Device Type:")
        l.grid(row=0, column=col, padx=(0,3), sticky=W)

        values = sorted(set([info['hw-type'] for info in data_helper.EEP_MAPPING]))
        self.cb_device_type = ChecklistCombobox(f, values=values, width="14") 
        self.cb_device_type.grid(row=1, column=col, padx=(0,3) )
        self.cb_device_type.bind('<Return>', self.apply_filter)
        self.cb_device_type.bind("<KeyRelease>", lambda e: self.cb_filtername.set('') )

        # eep
        col += 1
        l = Label(f, text="Device EEP:")
        l.grid(row=0, column=col, padx=(0,3), sticky=W)

        values = data_helper.get_eep_names()
        self.cb_device_eep = ChecklistCombobox(f, values=values, width="14") 
        self.cb_device_eep.grid(row=1, column=col, padx=(0,3))
        self.cb_device_eep.bind('<Return>', self.apply_filter)
        self.cb_device_eep.bind("<KeyRelease>", lambda e: self.cb_filtername.set('') )

        # used in ha
        col += 1
        self.var_in_ha = tk.IntVar()
        self.var_in_ha.set(1)
        self.cb_in_ha = ttk.Checkbutton(f, text="Used in HA", variable=self.var_in_ha)
        self.cb_in_ha.grid(row=1, column=col, padx=(0,3) )
        self.cb_in_ha.bind('<Return>', self.apply_filter)
        self.cb_in_ha.bind('<Button-1>', lambda e: self.cb_filtername.set('') )


        # button reset
        col += 1
        self.btn_clear_filter = Button(f, text="Reset", command=self.reset_filter)
        self.btn_clear_filter.grid(row=1, column=col, padx=(0,3) )

        col += 1
        self.btn_apply_filter = Button(f, text="Apply", command=self.apply_filter)
        self.btn_apply_filter.grid(row=1, column=col, padx=(0,3) )

        self.app_bus.add_event_handler(AppBusEventType.SET_DATA_TABLE_FILTER, self.on_set_filter_handler)
        self.app_bus.add_event_handler(AppBusEventType.ADDED_DATA_TABLE_FILTER, self.on_filter_added_handler)
        self.app_bus.add_event_handler(AppBusEventType.REMOVED_DATA_TABLE_FILTER, self.on_filter_removed_handler)

        ## initiall add all filters
        for d in self.data_manager.data_fitlers.values():
            self.on_filter_added_handler(d)
        selected_fn = self.data_manager.selected_data_filter_name
        if selected_fn is not None and len(selected_fn) > 0 and selected_fn in self.data_manager.data_fitlers.keys():
            self.on_set_filter_handler(self.data_manager.data_fitlers[selected_fn])
            self.apply_filter()



    def on_set_filter_handler(self, filter:DataFilter):
        self.set_widget_values(filter)

    def on_filter_added_handler(self, filter:DataFilter):
        # always take entire list to be in sync
        self.cb_filtername['values'] = sorted([k for k in self.data_manager.data_fitlers.keys()])

    def on_filter_removed_handler(self, filter:DataFilter):
        # always take entire list to be in sync
        self.cb_filtername['values'] = sorted([k for k in self.data_manager.data_fitlers.keys()])
        self.reset_filter()

    def add_filter(self, show_error_message:bool=True):
        filter_obj = self.get_filter_object()
        if filter_obj and len(filter_obj.name) > 1:
            self.data_manager.add_filter(filter_obj)
            
        elif show_error_message:
            messagebox.showerror(title="Error: Cannot add filter", message="Please, provdied a valid filter name!")

    def remove_filter(self):
        filter_obj = self.get_filter_object()
        if len(filter_obj.name) > 1:
            self.data_manager.remove_filter(filter_obj)
        else:
            messagebox.showerror(title="Error: Cannot remove filter", message="Please, provdied a valid filter name!")

    def set_widget_values(self, filter:DataFilter):
        if filter is not None:
            self.cb_filtername.set(filter.name)
            self.global_filter.delete(0, END)
            self.global_filter.insert(END, ', '.join(filter.global_filter))
            self.cb_device_address.delete(0, END)
            self.cb_device_address.insert(END, ', '.join(filter.device_address_filter))
            self.cb_external_address.delete(0, END)
            self.cb_external_address.insert(END, ', '.join(filter.device_external_address_filter))
            self.select_ChecklistCombobox(self.cb_device_type, filter.device_type_filter)
            self.select_ChecklistCombobox(self.cb_device_eep, filter.device_eep_filter)
        else:
            self.cb_filtername.set('')
            self.global_filter.delete(0, END)
            
            for cb in [self.cb_device_address, self.cb_external_address, self.cb_device_eep, self.cb_device_type]:
                cb.delete(0, END)
                if isinstance(cb, ChecklistCombobox):
                    for var in cb.variables:
                        var.set(0)

    def load_filter(self):
        filter_name = self.cb_filtername.get()
        if filter_name in self.data_manager.data_fitlers.keys():
            df:DataFilter = self.data_manager.data_fitlers[filter_name]
            self.set_widget_values(df)

            # load shall only present the values and not apply the filter
            # self.apply_filter()


    def select_ChecklistCombobox(self, widget:ChecklistCombobox, values:list[str]):
        widget.set(', '.join(values))
        for i in range(0,len(widget.checkbuttons)):
            widget.variables[i].set( 1 if widget.checkbuttons[i].cget('text') in values else 0 )

    def apply_filter(self, event=None, reset_for_no_filter_name:bool=False):
        filter = self.get_filter_object()
        # trigger reset if filter name is empty and if enter was pushed on filter name field
        if reset_for_no_filter_name:
            if filter is None or filter.name is None or len(filter.name) == 0:
                filter = None

        self.app_bus.fire_event(AppBusEventType.SET_DATA_TABLE_FILTER, filter)


    def reset_filter(self):
        self.app_bus.fire_event(AppBusEventType.SET_DATA_TABLE_FILTER, None)

    def get_str_array(self, widget:Widget) -> list[str]:
        widget_value = ''
        try:
            widget_value = widget.get()
        except:
            pass
        if isinstance(widget_value, str):
            return [g.strip() for g in widget_value.replace(';',',').split(',') if len(g.strip()) > 0 ]
        elif isinstance(widget_value, list):
            return [g.strip() for g in widget_value if len(g.strip()) > 0 ]
        else:
            return []


    def get_filter_object(self):

        filter_obj = DataFilter(
            name = self.cb_filtername.get(),
            global_filter=self.get_str_array(self.global_filter),
            device_address_filter=self.get_str_array(self.cb_device_address),
            device_external_address_filter=self.get_str_array(self.cb_external_address),
            device_type_filter=self.get_str_array(self.cb_device_type),
            device_eep_filter=self.get_str_array(self.cb_device_eep),
        )
        
        reset  = len(filter_obj.global_filter) == 0 
        reset &= len(filter_obj.device_address_filter) == 0 
        reset &= len(filter_obj.device_external_address_filter) == 0 
        reset &= len(filter_obj.device_type_filter) == 0 
        reset &= len(filter_obj.device_eep_filter) == 0 

        if reset: 
            return None
        else: 
            return filter_obj
        
        