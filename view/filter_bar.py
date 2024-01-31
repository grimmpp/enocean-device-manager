import tkinter as tk
from tkinter import *
from tkinter import ttk
from tkinter import messagebox
from const import CONF_EEP
from data.filter import DataFilter

from view.checklistcombobox import ChecklistCombobox

from controller import AppController, ControllerEventType
from data.data import DataManager, EEP_MAPPING, get_eep_names


class FilterBar():

    
    def __init__(self, main: Tk, controller:AppController, data_manager:DataManager, row:int):
        self.controller = controller
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

        # address
        col += 1
        l = Label(f, text="Address:")
        l.grid(row=0, column=col, padx=(0,3), sticky=W)

        self.cb_device_address = Entry(f, width="14") 
        self.cb_device_address.grid(row=1, column=col, padx=(0,3) )
        self.cb_device_address.bind('<Return>', self.apply_filter)

        # external address
        col += 1
        l = Label(f, text="External Address:")
        l.grid(row=0, column=col, padx=(0,3), sticky=W)

        self.cb_external_address = Entry(f, width="14") 
        self.cb_external_address.grid(row=1, column=col, padx=(0,3) )
        self.cb_external_address.bind('<Return>', self.apply_filter)

        # device type
        col += 1
        l = Label(f, text="Device Type:")
        l.grid(row=0, column=col, padx=(0,3), sticky=W)

        values = sorted(set([info['hw-type'] for info in EEP_MAPPING]))
        self.cb_device_type = ChecklistCombobox(f, values=values, width="14") 
        self.cb_device_type.grid(row=1, column=col, padx=(0,3) )
        self.cb_device_type.bind('<Return>', self.apply_filter)

        # eep
        col += 1
        l = Label(f, text="Device EEP:")
        l.grid(row=0, column=col, padx=(0,3), sticky=W)

        values = get_eep_names()
        self.cb_device_eep = ChecklistCombobox(f, values=values, width="14") 
        self.cb_device_eep.grid(row=1, column=col, padx=(0,3))
        self.cb_device_eep.bind('<Return>', self.apply_filter)

        # used in ha
        col += 1
        self.var_in_ha = tk.IntVar()
        self.var_in_ha.set(1)
        self.cb_in_ha = ttk.Checkbutton(f, text="Used in HA", variable=self.var_in_ha)
        self.cb_in_ha.grid(row=1, column=col, padx=(0,3) )
        self.cb_in_ha.bind('<Return>', self.apply_filter)


        # button reset
        col += 1
        self.btn_clear_filter = Button(f, text="Reset", command=self.reset_filter)
        self.btn_clear_filter.grid(row=1, column=col, padx=(0,3) )

        col += 1
        self.btn_apply_filter = Button(f, text="Apply", command=self.apply_filter)
        self.btn_apply_filter.grid(row=1, column=col, padx=(0,3) )


    def add_filter(self):
        filter_obj = self.get_filter_object()
        if len(filter_obj.name) > 1:
            self.data_manager.add_filter(filter_obj)
            self.cb_filtername['values'] = sorted([k for k in self.data_manager.data_fitlers.keys()])
            
        else:
            messagebox.showerror(title="Error: Cannot add filter", message="Please, provdied a valid filter name!")

    def remove_filter(self):
        filter_obj = self.get_filter_object()
        if len(filter_obj.name) > 1:
            self.data_manager.remove_filter(filter_obj)
            self.cb_filtername['values'] = sorted([k for k in self.data_manager.data_fitlers.keys()])
            self.reset_filter()
        else:
            messagebox.showerror(title="Error: Cannot remove filter", message="Please, provdied a valid filter name!")

    def load_filter(self):
        filter_name = self.cb_filtername.get()
        if filter_name in self.data_manager.data_fitlers.keys():
            df:DataFilter = self.data_manager.data_fitlers[filter_name]
            self.global_filter.delete(0, END)
            self.global_filter.insert(END, ', '.join(df.global_filter))
            self.cb_device_address.delete(0, END)
            self.cb_device_address.insert(END, ', '.join(df.device_address_filter))
            self.cb_external_address.delete(0, END)
            self.cb_external_address.insert(END, ', '.join(df.device_external_address_filter))
            self.select_ChecklistCombobox(self.cb_device_type, df.device_type_filter)
            self.select_ChecklistCombobox(self.cb_device_eep, df.device_eep_filter)

            self.apply_filter()


    def select_ChecklistCombobox(self, widget:ChecklistCombobox, values:[str]):
        widget.set(', '.join(values))
        for i in range(0,len(widget.checkbuttons)):
            widget.variables[i].set( 1 if widget.checkbuttons[i].cget('text') in values else 0 )

    def apply_filter(self, event=None):
        self.controller.fire_event(ControllerEventType.SET_DATA_TABLE_FILTER, self.get_filter_object())


    def reset_filter(self):
        self.cb_filtername.set('')
        self.global_filter.delete(0, END)
        
        for cb in [self.cb_device_address, self.cb_external_address, self.cb_device_eep, self.cb_device_type]:
            cb.delete(0, END)
            if isinstance(cb, ChecklistCombobox):
                for var in cb.variables:
                    var.set(0)

        self.controller.fire_event(ControllerEventType.SET_DATA_TABLE_FILTER, None)

    def get_str_array(self, widget:Widget) -> [str]:
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
        
        