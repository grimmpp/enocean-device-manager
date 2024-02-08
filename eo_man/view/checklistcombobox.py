import tkinter as tk # Python 3 only
import tkinter.ttk as ttk
import tkinter.font as tkfont
import numpy as np

# GUI features to test (X means completed):
#   1.) Both 'normal' and 'readonly'
#      X Pressing Tab at any time (popdown or no) moves to the next widget
#      X Pressing Tab with an item highlighted selects that item and then moves to the next widget
#      X Pressing up/down arrows when the popdown menu is down moves the selection up/down
#      X Pressing up/down on top/bottom selections scrolls the view down by 1 line
#      X Pressing Escape with the popdown visible hides the popdown
#      X Scrollwheel when popdown is down scrolls by 4 units (Listbox source code)
#      X Clicking the trough of the scrollwheel moves the view by 1 "page"
#      X When the popdown window appears, the view is set automatically to where the current 
#        selection is. If the current selection is not in view, the view is set such that
#        the selection is centered (using integer math). If the selection is in view, no
#        scrolling is done and the selection is not centered. If the selection is only 1 item
#        away from being in view, the view is set such that the item is in view, but is either
#        at the very top or very bottom depending on which side it was closest to.
#      X PageUp/PageDown keys do the same thing as the scrollwheel trough
#      X A scrollbar is placed in the dropdown menu when the number of values in the list
#        exceeds the height of the list (= height of the combobox)
#      X There is 1 pixel of whitespace between the listbox items and the popdown frame
#      X There are 2 pixels of whitespace between the scrollbar and the listbox items
#      X The Enter key does the same thing as clicking on the currently highlighted item
#      X Control+Home and Control+End go to the top and bottom of the listbox respectively
#      X Click+Drag should work the same as regular Drag, but when the button is released, the
#        highlighted item is selected. This is true while INSIDE the popdown menu. When OUTSIDE,
#        the canvas should be scrolled "automatically" up or down
#   2.) state = 'normal'
#      X When a selection is made, the text in the Entry widget is highlighted
#      X Can click inside the Entry widget without creating the popdown
#      X Can type anything into the Entry widget
#      X Text does not change in Entry widget until a selection is made
#      X Tabbing in to the widget highlights the text in the Entry widget
#   3.) state = 'disabled'
#      X Clicking the widget does nothing
#      X Cannot tab into the widget
#      X Colors change to a 'disabled' theme
#   4.) state = 'readonly'
#      X Clicking the Entry widget makes the popdown appear
#      X Entire Entry widget space is highlighted after making a selection
#      X Typing does nothing
#      X Tabbing into the widget highlights the entire Entry widget


class ChecklistCombobox(ttk.Combobox):
    """
    ChecklistCombobox v1.1
    Author: Roger Hatfull
    November 2020
    
    This widget is a regular ttk.Combobox, but instead of a Listbox in the popdown
    window, there is a list of checkboxes. It is designed to function almost
    identically to a ttk.Combobox, except for some fringe cases. Learning from
    mistakes made in tkinter, this widget is fully customizable to the extent that
    tkinter allows.
    
    The standard Listbox widget from ttk.Combobox is unfortunately inseparable from
    the popdown menu because a majority of the tcl code for ttk.Combobox would need
    to be replaced. This would mangle any other regular ttk.Combobox widgets
    attached to the Tk() instance. Instead, we simply put stuff on top of the
    Listbox.
    
    Here is a tree of widgets that are accessible to the user. Tree depth indicates
    widget stacking. For example, ChecklistCombobox.popdown is a subwidget (child)
    of ChecklistCombobox.
    
    Tree                                              Widget type
     ChecklistCombobox                                 ttk.Combobox
        ChecklistCombobox.popdown                      tk.Toplevel
           ChecklistCombobox.popdown_frame             special popdown frame widget
              ChecklistCombobox.listbox                tk.Listbox
              ChecklistCombobox.scrollbar              ttk.Scrollbar
              ChecklistCombobox.canvas                 tk.Canvas
                 ChecklistCombobox.checkbutton_frame   tk.Frame
                    ChecklistCombobox.checkbuttons     list with length = len(values)
                       tk.Checkbutton
    
    Any of these widgets can be accessed by the user by simply calling them. For
    example, to change the height of all the checkbuttons, you can do,
        ```
        cb = ChecklistCombobox(root,values=('1','2','3','4'))
        for button in cb.checkbuttons:
            button.configure(height=2)
        ```
    Equivalently, you can do,
        ```
        cb = ChecklistCombobox(root,values=('1','2','3','4'))
        cb.configure(checkbutton_height=2)
        ```
    This is because this class handles the configure method in a special way. The
    keywords are parsed and then passed to the appropriate widgets based on the
    prefix they are given. Supported prefixes are,
        ```
        popdown_
        popdown_frame_
        scrollbar_
        canvas_
        checkbutton_frame_
        checkbutton_
        checkbutton_selected_
        ```
    Prefix `checkbutton_selected_` can be used to specify the Checkbutton attributes
    when they are highlighted, but only the `background`, `foreground`,
    `selectcolor`, `activeforeground`, and `activebackground`.
    Be careful when using `popdown_frame_` and `scrollbar_` because they are special 
    widgets exclusive to the Combobox Popdown menu. You can list their options by 
    doing `print(cb.popdown_frame.configure())`. All other prefixes work in the way 
    you would expect. Given some option X from the tkinter widget documentation, you 
    can change the option using,
        ```
        ChecklistCombobox.configure(prefix_X)
        ```
    You can even configure the checkbuttons separately by giving an array-like
    (`list`, `tuple`, or `numpy.ndarray`) argument where the elements have the same
    order as the `values` keyword.

    So as to avoid confusion, the original ttk.Combobox tcl source code which this
    code was based on has been included at the bottom of this code.

    Also near the bottom of this code is a short test program you can use simply by
    running `python checklistcombobox.py`.
    """
    
    def __init__(self,master=None,**kw):
        self.values = kw.pop('values',None)
        if self.values is None: self.values = []
        if not isinstance(self.values,(list,tuple,np.ndarray)): self.values = list(self.values)
        
        ### Create the widgets
        # Create the Combobox
        ttk.Combobox.__init__(self,master,values=self.values)
        self.tk.eval('ttk::combobox::ConfigureListbox %s' % (self)) # This updates the listbox in the popdown
        
        # Break the Combobox down into its constituent parts
        self.popdown = tk.Toplevel()
        self.popdown.withdraw()
        self.popdown._w = '%s.popdown' % (self)
        self.popdown_frame = tk.Frame()
        self.popdown_frame._w = '%s.popdown.f' % (self)
        self.listbox = tk.Listbox()
        self.listbox._w = '%s.popdown.f.l' % (self)
        self.scrollbar = tk.Scrollbar()
        self.scrollbar_repeatdelay = self.scrollbar.cget('repeatdelay')
        self.scrollbar_repeatinterval = self.scrollbar.cget('repeatinterval')
        self.scrollbar._w = '%s.popdown.f.sb' % (self)
        
        # Create the checkbuttons
        self.canvas_frame = tk.Frame(self.popdown_frame) # Frame in front of canvas for borders
        self.canvas = tk.Canvas(self.canvas_frame) # Canvas for scrolling
        self.checkbutton_frame = tk.Frame(self.canvas) # Checkbutton container
        self.checkbuttons = []
        self.variables = []
        self.selection = None
        if len(self.values) > 0: self.create_checkbuttons()
            
        
        ### Grid the widgets
        self.checkbutton_frame.grid_propagate(0)
        self.checkbutton_frame.columnconfigure(0,weight=1)
        self.canvas_frame.grid_propagate(0)
        self.canvas_frame.columnconfigure(0,weight=1)
        #for i,button in enumerate(self.checkbuttons): 
        #    button.grid(row=i,column=0,sticky='news')
        self.canvas.grid(row=0,column=0,sticky='news')
        self.checkbutton_frame.grid(row=0,column=0,sticky='news')
        self.canvas.create_window((0,0),window=self.checkbutton_frame,anchor='nw')
        self.canvas_frame.grid(row=0,column=0,padx=1,pady=1,sticky='news')
        
        
        ### Initialize
        self.listbox.configure(yscrollcommand='') # Break connection between listbox and scrollbar
        self.configure(**kw) # Do initial configuration
        
        
        # Make sure the popdown is ready to go the first time
        self.last_clicked_button = None
        self.autoscrolling = False
        self.mouse_has_entered_popdown = False
        self.afterId = None
        self.b1_motion_entered_popdown = False
        self.configure_popdown() # Initial configuration
        self.topbutton = 0
        if len(self.cget('values')) > self.cget('height'):
            self.bottombutton = self.cget('height')-1
        else:
            self.bottombutton = len(self.checkbuttons)-1
        
        self.previous_button_kw = {}
        if self.checkbuttons:
            self.selection = 0
            for key in self.checkbuttons[self.selection].keys():
                self.previous_button_kw[key] = self.checkbuttons[self.selection].cget(key)
            # Select the button
            self.checkbuttons[self.selection].configure(bg=self.checkbutton_selected_background[self.selection],
                                                        fg=self.checkbutton_selected_foreground[self.selection],
                                                        selectcolor=self.checkbutton_selected_selectcolor[self.selection],
                                                        activebackground=self.checkbutton_selected_activebackground[self.selection],
                                                        activeforeground=self.checkbutton_selected_activeforeground[self.selection])
            
            
        ### Create keybindings
        
        self.listbox.bind("<Down>",self.on_down) # Down arrow
        self.listbox.bind("<Up>",self.on_up) # Up arrow
        self.listbox.bind("<Prior>",lambda event: self.scroll(event,amount=-1,units='pages')) # PageUp
        self.listbox.bind("<Next>",lambda event: self.scroll(event,amount=1,units='pages')) # PageDown
        self.listbox.bind("<Control-Home>",lambda event: self.select(self.checkbuttons[0]))
        self.listbox.bind("<Control-End>",lambda event: self.select(self.checkbuttons[-1]))
        self.listbox.bind("<KeyPress-Return>",self.on_carraige_return) # Enter
        self.listbox.bind("<Motion>",self.do_nothing) # Mouse motions
        self.listbox.bind("<KeyPress-Tab>",self.on_lb_tab) # Tab
        self.listbox.bind("<<PrevWindow>>",self.on_lb_prevwindow) # Relates to the Tab key
        self.listbox.bind("<MouseWheel>",self.do_nothing)
        #self.listbox.bind("<Map>",self.do_nothing) # This almost works
        self.bind("<MouseWheel>",self.do_nothing) # MouseWheel on Entry widget in this case is nonsensical
        if self.tk.eval('if {[tk windowingsystem] eq "x11"} {expr {1}} else {expr {0}}'):
            self.bind("<ButtonPress-4>",self.do_nothing)
            self.bind("<ButtonPress-5>",self.do_nothing)
        self.popdown.bind("<MouseWheel>",self.on_popdown_mousewheel)
        self.bind("<ButtonPress-1>",lambda event: self.popdown.focus_set()) # Don't let the focus get set on the entry widget before mapping, to avoid "flickering"
        #self.listbox.bind("<Map>",self.configure_popdown) # When the listbox is mapped, reconfigure the popdown
        self.popdown_frame.bind("<Configure>",self.configure_popdown)
        #self.popdown_frame.bind("<Map>",self.scroll_to_last_clicked_button)
        self.popdown.bind("<Unmap>",self.popdown_unmap)
        self.bind("<FocusOut>",self.popdown_unmap)
        
        self.popdown.bind("<Motion>",self.on_motion)
        self.popdown.bind("<B1-Motion>",self.on_b1_motion)
        
        #self.scrollbar.bind("<ButtonPress-1>",self.on_scrollbar_click_press)
        #self.scrollbar.bind("<ButtonRelease-1>",self.on_scrollbar_click_release)
        
    def __getattribute__(self,attr):
        # Custom configure function
        if attr == 'configure' or attr == 'config':
            return self.custom_configure
        return super(ChecklistCombobox,self).__getattribute__(attr)
    
    def custom_configure(self,cnf=None,**kw):
        self.checkbutton_selected_background = kw.get('checkbutton_selected_background',[self.listbox.cget('selectbackground')]*len(self.checkbuttons))
        self.checkbutton_selected_foreground = kw.get('checkbutton_selected_foreground',[self.listbox.cget('selectforeground')]*len(self.checkbuttons))
        self.checkbutton_selected_selectcolor = kw.get('checkbutton_selected_selectcolor',self.checkbutton_selected_background)
        self.checkbutton_selected_activebackground = kw.get('checkbutton_selected_activebackground',self.checkbutton_selected_background)
        self.checkbutton_selected_activeforeground = kw.get('checkbutton_selected_activeforeground',self.checkbutton_selected_foreground)
        
        kw['popdown_bg'] = kw.get('popdown_bg',kw.get('popdown_background',self.listbox.cget('background')))
        kw['popdown_background'] = kw['popdown_bg']
        kw['popdown_highlightthickness'] = kw.get('popdown_highlightthickness',0)
        kw['popdown_highlightbackground'] = kw.get('popdown_highlightbackground',self.listbox.cget('highlightbackground'))
        kw['canvas_bg'] = kw.get('canvas_bg',kw['popdown_bg'])
        kw['canvas_background'] = kw['canvas_bg']
        kw['canvas_highlightthickness'] = kw.get('canvas_highlightthickness',0)
        kw['canvas_yscrollcommand'] = kw.get('canvas_yscrollcommand',self.scrollbar.set)
        kw['canvas_frame_highlightthickness'] = kw.get('canvas_frame_highlightthickness',1)
        kw['canvas_frame_highlightbackground'] = kw.get('canvas_frame_highlightbackground',kw['popdown_bg'])
        kw['scrollbar_command'] = kw.get('scrollbar_command',self.canvas.yview)
        
        kw['checkbutton_text'] = kw.get('checkbutton_text')
        if self.values: kw['checkbutton_text'] = self.values
        
        kw['checkbutton_font'] = kw.get('checkbutton_font',self.listbox.cget('font'))
        kw['checkbutton_anchor'] = kw.get('checkbutton_anchor','w')
        kw['checkbutton_bd'] = kw.get('checkbutton_bd',0)
        kw['checkbutton_highlightthickness'] = kw.get('checkbutton_highlightthickness',0)
        kw['checkbutton_padx'] = kw.get('checkbutton_padx',0)
        kw['checkbutton_pady'] = kw.get('checkbutton_pady',0)
        kw['checkbutton_bg'] = kw.get('checkbutton_bg',kw.get('checkbutton_background',kw['popdown_bg']))
        kw['checkbutton_fg'] = kw.get('checkbutton_fg',kw.get('checkbutton_foreground',self.listbox.cget('foreground')))
        kw['checkbutton_background'] = kw['checkbutton_bg']
        kw['checkbutton_foreground'] = kw['checkbutton_fg']
        kw['checkbutton_variable'] = kw.get('checkbutton_variable',self.variables)
        kw['checkbutton_overrelief'] = kw.get('checkbutton_overrelief','flat')
        kw['checkbutton_activebackground'] = kw.get('checkbutton_activebackground',kw['checkbutton_bg'])
        kw['checkbutton_activeforeground'] = kw.get('checkbutton_activeforeground',kw['checkbutton_fg'])
        kw['checkbutton_selectcolor'] = kw.get('checkbutton_selectcolor',kw['checkbutton_bg'])
        
        # Catch some keywords that are exclusive to this class
        popdown_kw = {}
        popdown_frame_kw = {}
        scrollbar_kw = {}
        canvas_kw = {}
        canvas_frame_kw = {}
        checkbutton_frame_kw = {}
        checkbutton_kw = {}
        checkbutton_selected_kw = {}
        combobox_kw = {}
        for key, value in kw.items():
            keysplit = key.split("_")
            if keysplit[0] == 'checkbutton':
                if keysplit[1] == 'frame':
                    checkbutton_frame_kw["".join(keysplit[2:])] = value
                if self.checkbuttons:
                    if keysplit[1] == 'selected':
                        checkbutton_selected_kw["".join(keysplit[2:])] = value
                    else:
                        checkbutton_kw["".join(keysplit[1:])] = value
            elif keysplit[0] == 'popdown':
                if keysplit[1] == 'frame':
                    popdown_frame_kw["".join(keysplit[2:])] = value
                else:
                    popdown_kw["".join(keysplit[1:])] = value
            elif keysplit[0] == 'canvas':
                if keysplit[1] == 'frame':
                    canvas_frame_kw["".join(keysplit[2:])] = value
                else:
                    canvas_kw["".join(keysplit[1:])] = value
            elif keysplit[0] == 'scrollbar':
                scrollbar_kw["".join(keysplit[1:])] = value
            else:
                # Intercept the all-important "values" keyword
                if key == 'values':
                    self.values = value
                    self.create_checkbuttons()
                combobox_kw[key] = value
            """
            if keysplit[0] == 'checkbutton' and keysplit[1] == 'frame':
                checkbutton_frame_kw["".join(keysplit[2:])] = value
            elif self.checkbuttons and keysplit[0] == 'checkbutton' and keysplit[1] == 'selected':
                checkbutton_selected_kw["".join(keysplit[2:])] = value
            elif keysplit[0] == 'checkbutton':
                if self.checkbuttons:
                    checkbutton_kw["".join(keysplit[1:])] = value
                    
            elif keysplit[0] == 'popdown' and keysplit[1] != 'frame':
                popdown_kw["".join(keysplit[1:])] = value
            elif keysplit[0] == 'popdown' and keysplit[1] == 'frame':
                popdown_frame_kw["".join(keysplit[2:])] = value
                
            elif keysplit[0] == 'canvas' and keysplit[1] != 'frame':
                canvas_kw["".join(keysplit[1:])] = value
            elif keysplit[0] == 'canvas' and keysplit[1] == 'frame':
                canvas_frame_kw["".join(keysplit[2:])] = value
            elif keysplit[0] == 'scrollbar':
                scrollbar_kw["".join(keysplit[1:])] = value
            else:
                combobox_kw[key] = value
            """
        
        # Massage checkbutton_kw
        for key,value in checkbutton_kw.items():
            if not isinstance(value,(list,tuple,np.ndarray)):
                checkbutton_kw[key] = [value]*len(self.checkbuttons)
            elif len(value) != len(self.checkbuttons):
                raise ValueError("Array-like argument for configuring Checkbuttons is length '"+str(len(value))+"', but expected length '"+str(len(self.checkbuttons))+"'")
        for key,value in checkbutton_selected_kw.items():
            myvalue = value
            if not isinstance(value,(list,tuple,np.ndarray)):
                myvalue = [value]*len(self.checkbuttons)
            elif len(value) != len(self.checkbuttons):
                raise ValueError("Array-like argument for configuring Checkbuttons is length '"+str(len(value))+"', but expected length '"+str(len(self.checkbuttons))+"'")
            if key == "background": self.checkbutton_selected_background = myvalue
            elif key == "foreground": self.checkbutton_selected_foreground = myvalue
            elif key == "selectcolor": self.checkbutton_selected_selectcolor = myvalue
            elif key == "activebackground": self.checkbutton_selected_activebackground = myvalue
            elif key == "activeforeground": self.checkbutton_selected_activeforeground = myvalue
            else: raise TypeError("Unrecognized keyword argument '"+str(key)+"'")
            
        # Send all the kw to the right places
        self._configure('configure',cnf,combobox_kw)
        self.popdown.configure(**popdown_kw)
        self.popdown_frame.configure(**popdown_frame_kw)
        self.scrollbar.configure(**scrollbar_kw)
        self.canvas.configure(**canvas_kw)
        self.canvas_frame.configure(**canvas_frame_kw)
        self.checkbutton_frame.configure(**checkbutton_frame_kw)
        
        for i,button in enumerate(self.checkbuttons):
            my_kw = {}
            for key,value in checkbutton_kw.items():
                my_kw[key] = value[i]
            button.configure(**my_kw)
    def current(self,newindex=None):
        # We need to modify this function to work in an expected fashion for this widget
        # "If newindex is specified, sets the combobox value to the element position 
        # newindex. Otherwise, returns the index of the current value or -1 if the current 
        # value is not in the values list."
        # We will allow newindex to be an array-like object
        if newindex is not None: # Check all the checkbuttons in newindex
            if isinstance(newindex,(list,tuple,np.ndarray)):
                for i in newindex:
                    self.checkbuttons[i].event_generate("<ButtonRelease-1>")
            else:
                self.checkbuttons[newindex].event_generate("<ButtonRelease-1>")
        else:
            retarr = self.get()
            if len(retarr) == 0:
                return -1
            elif len(retarr) == 1:
                if retarr[0] == '':
                    return -1
                else:
                    return self.cget('values').index(retarr[0])
            else:
                return [self.cget('values').index(i) for i in self.get()]
    def get(self, do_not_filter:bool=True):
        if do_not_filter:
            return super().get()

        # Normally this returns the current value of the Combobox. However, we should
        # return a list of the values associated with the checked Checkboxes instead.
        # These are always stored in the Entry widget text anyway.
        all_text = [b.cget('text') for b,v in zip(self.checkbuttons,self.variables) if v.get() == 1]
        if len(all_text) > 1:
            return all_text
        elif len(all_text) == 1:
            return all_text[0]
        else:
            return '' # Empty string
    def set(self,value):
        # Normally this sets the text in the Combobox to "value". We will now allow the
        # user to pass in an array-like variable for "value", and we will activate all
        # checkbuttons that are in "value". Also will select the last item in "value".
        if isinstance(value,(list,tuple,np.ndarray)):
            # First, find all the buttons that are to be set
            check = [str(v) for v in value]
            idx = -1
            my_button = None
            for button in self.checkbuttons:
                if button.cget('text') in check:
                    button.select()
                    if check.index(button.cget('text')) > idx:
                        idx = check.index(button.cget('text'))
                        my_button = button
                else:
                    button.deselect()
            if my_button is not None and not self.popdown.winfo_ismapped():
                self.select(my_button)
                self.last_clicked_button = my_button
            return super(ChecklistCombobox,self).set(", ".join(value))
        else:
            return super(ChecklistCombobox,self).set(value)
    def select(self,button):
        if button not in self.checkbuttons: return
        if self.selection is not None and button == self.checkbuttons[self.selection]: return
        idx = self.checkbuttons.index(button)
        # Unhighlight the previously selected button
        if self.selection is not None:
            self.checkbuttons[self.selection].configure(**self.previous_button_kw)
        self.previous_button_kw = {}
        for key in button.keys():
            self.previous_button_kw[key] = button.cget(key)
        # Highlight the newly selected button
        button.configure(bg=self.checkbutton_selected_background[idx],
                         fg=self.checkbutton_selected_foreground[idx],
                         selectcolor=self.checkbutton_selected_selectcolor[idx],
                         activebackground=self.checkbutton_selected_activebackground[idx],
                         activeforeground=self.checkbutton_selected_activeforeground[idx])
        self.selection = self.checkbuttons.index(button)
        
        # Scroll if needed when making the new selection
        visible_bottom = self.canvas.winfo_height()-self.checkbutton_frame.winfo_y()
        visible_top = -self.checkbutton_frame.winfo_y()
        button_height = button.winfo_height()
        button_y0 = button.winfo_y()
        button_y1 = button_y0+button_height
        if button_y1 > visible_bottom:
            self.scroll(amount=int((button_y1-visible_bottom)/button_height))
        elif button_y0 < visible_top:
            self.scroll(amount=-int((visible_top-button_y0)/button_height))
            
    def create_checkbuttons(self):
        # Destroy unwanted checkbuttons
        if len(self.values) < len(self.checkbuttons):
            for button in self.checkbuttons[len(values):]:
                self.checkbuttons.pop(button)
                #button.grid_forget()
                button.destroy()
        else:
            # Create new checkbuttons if we need to
            for i in range(len(self.checkbuttons),len(self.values)):
                self.checkbuttons.append(tk.Checkbutton())
                self.checkbuttons[-1]._w = '%s%s' % (self.checkbutton_frame,self.checkbuttons[-1])
                self.tk.eval('checkbutton %s' % (self.checkbuttons[-1]))
                self.variables.append(tk.IntVar())
        # Reassign all the buttons' text and grid them down
        for i,button in enumerate(self.checkbuttons):
            button.configure(text=self.values[i])
            button.grid(row=i,column=0,sticky='news')
            # Assign keybindings
            for button in self.checkbuttons:
                button.bind("<ButtonRelease-1>",self.on_checkbutton_click_release)
                button.bind("<Button-1>",self.on_checkbutton_click_press)
        
        self.configure()
        
        if self.checkbuttons and self.selection is not None:
            self.previous_button_kw = {}
            for key in self.checkbuttons[self.selection].keys():
                self.previous_button_kw[key] = self.checkbuttons[self.selection].cget(key)
            # Select the button
            self.checkbuttons[self.selection].configure(bg=self.checkbutton_selected_background[self.selection],
                                                        fg=self.checkbutton_selected_foreground[self.selection],
                                                        selectcolor=self.checkbutton_selected_selectcolor[self.selection],
                                                        activebackground=self.checkbutton_selected_activebackground[self.selection],
                                                        activeforeground=self.checkbutton_selected_activeforeground[self.selection])
        
        
        
    
    ### Scroll keybindings
    """
    def on_scrollbar_click_release(self,event):
        try:
            self.afterId = self.after_cancel(self.afterId)
        except:
            pass # Doesn't matter if this fails
    def on_scrollbar_click_press(self,event=None):
        # Set the scroll increment based on what the next visible button will be
        button_pressed = self.scrollbar.identify(event.x,event.y).split(".")[-1]
        print(self.scrollbar.identify(event.x,event.y))
        print(self.scrollbar.get())
        if button_pressed == 'downarrow':
            self.scroll(amount=1)
            self.update()
            self.afterId = self.after(self.scrollbar_repeatdelay,self.scrollbar_autoscroll_down)
        elif button_pressed == 'uparrow':
            self.scroll(amount=-1)
            self.update()
            self.afterId = self.after(self.scrollbar_repeatdelay,self.scrollbar_autoscroll_up)
        elif button_pressed == 'trough':
            # Need to scroll by the same amount as mousewheel
            1+1
        return 'break'
    """
    def scrollbar_autoscroll_down(self):
        self.scroll(amount=1)
        self.update()
        self.afterId = self.after(self.scrollbar_repeatinterval,self.scrollbar_autoscroll_down)
    def scrollbar_autoscroll_up(self):
        self.scroll(amount=-1)
        self.update()
        self.afterId = self.after(self.scrollbar_repeatinterval,self.scrollbar_autoscroll_up)
    def on_popdown_mousewheel(self,event):
        # The values for how much to scroll by come from the Listbox tcl source code.
        if event.num == 4: # They say this is for Linux machines
            self.scroll(event,amount=-5)
        elif event.num == 5: # They say this is for Linux machines
            self.scroll(event,amount=5)
        elif event.delta == 120:
            self.scroll(event,amount=-4)
        elif event.delta == -120:
            self.scroll(event,amount=4)
        return "break"
    def scroll(self,event=None,amount=1,units='units'):
        if len(self.cget('values')) > self.cget('height'): # If there is a scrollbar
            """
            #print("Scrolling")
            if units == 'units':
                true_amount = amount
            elif units == 'pages':
                if self.tk.eval('if {[tk windowingsystem] eq "x11"} {expr {1}} else {expr {0}}'): # Windows
                    true_amount = amount*4
                else: # Linux
                    true_amount = amount*5
            old_topbutton = self.topbutton
            old_bottombutton = self.bottombutton
            if true_amount < 0: # Scrolling up
                if self.topbutton + true_amount < 0:
                    self.topbutton = 0
                    self.bottombutton = self.topbutton + self.cget('height')-1
                else:
                    self.bottombutton += true_amount
                    self.topbutton += true_amount
                scrollincrement = 0
                for button in self.checkbuttons[self.topbutton:old_topbutton+1]:
                    button.update()
                    scrollincrement += button.winfo_height()
                scrollincrement /= float(len(self.checkbuttons[self.topbutton:old_topbutton+1]))
            else: # Scrolling down; hide buttons from the top based on their heights
                print(self.bottombutton,true_amount)
                if self.bottombutton + true_amount > len(self.cget('values'))-1:
                    self.bottombutton = len(self.cget('values'))-1
                    self.topbutton = self.bottombutton - (self.cget('height')-1)
                else:
                    self.bottombutton += true_amount
                    self.topbutton += true_amount
                scrollincrement = 0
                for button in self.checkbuttons[old_topbutton:self.topbutton]:
                    button.update()
                    scrollincrement += button.winfo_height()
                scrollincrement /= float(len(self.checkbuttons[old_topbutton:self.topbutton]))
            print(self.topbutton,self.bottombutton,scrollincrement)
            self.canvas.config(yscrollincrement=scrollincrement)
            """
            return self.canvas.yview_scroll(amount,units)
    def on_down(self,event=None):
        if self.selection is None:
            self.select(self.checkbuttons[self.topbutton])
        elif self.selection < len(self.checkbuttons)-1:
            self.select(self.checkbuttons[self.selection+1])
        return "break"
    def on_up(self,event=None):
        if self.selection is None:
            self.select(self.checkbuttons[self.bottombutton])
        elif self.selection > 0:
            self.select(self.checkbuttons[self.selection-1])
        return "break"
    
    
    ### Key bindings
    def do_nothing(self,*args,**kwargs): return "break"
    def on_lb_tab(self,event):
        self.on_checkbutton_click_release(event) # Simulate the pressing of the currently selected button
        self.tk.eval('set newFocus [tk_focusNext %s] \n\
        if {$newFocus ne ""} {\n\
        ttk::combobox::Unpost %s \n\
        update \n\
        ttk::traverseTo $newFocus \n\
        }' % (self,self))
        return "break"
    def on_lb_prevwindow(self,event):
        self.on_checkbutton_click_release(event) # Simulate the pressing of the currently selected button
        self.tk.eval('set newFocus [tk_focusPrev %s] \n\
        if {$newFocus ne ""} {\n\
        ttk::combobox::Unpost %s \n\
        update \n\
        ttk::traverseTo $newFocus \n\
        }' % (self,self))
        return "break"
    def on_carraige_return(self,event):
        if self.selection is not None:
            self.checkbuttons[self.selection].event_generate("<ButtonRelease-1>")
        return "break"
    def on_motion(self,event):
        if event.widget in [str(b) for b in self.checkbuttons]: # It was a button
            for button in self.checkbuttons: # Check all the buttons to see if we are inside one
                y0 = button.winfo_rooty()
                y1 = y0+button.winfo_height()
                if y0 < event.y_root and event.y_root < y1:
                    self.select(button)
    def on_b1_motion(self,event):
        y = event.y_root - self.popdown.winfo_rooty()
        x = event.x_root - self.popdown.winfo_rootx()
        if not self.b1_motion_entered_popdown:
            if y < self.popdown.winfo_height() and y >= 0 and \
               x < self.popdown.winfo_width()  and x >= 0:
                self.b1_motion_entered_popdown = True
        if self.b1_motion_entered_popdown:
            if y >= self.popdown.winfo_height() and self.scrollbar.get()[1] != 1.:
                if not self.autoscrolling:
                    self.autoscrolling = True
                    self.autoscan('down')
            elif y < 0  and self.scrollbar.get()[0] != 0.:
                if not self.autoscrolling:
                    self.autoscrolling = True
                    self.autoscan('up')
            else:
                self.cancel_autoscan()
                self.on_motion(event)
    def autoscan(self,direction):
        if not self.autoscrolling: return
        cy0 = self.canvas.winfo_rooty()
        if direction == 'down':
            if self.scrollbar.get()[1] == 1.:
                self.cancel_autoscan()
                return
            # Select the button beneath the last one visible if possible
            cy1 = cy0+self.canvas.winfo_height()
            for i,button in enumerate(self.checkbuttons):
                by1 = button.winfo_rooty()+button.winfo_height()
                if by1-cy1==0 and i < len(self.checkbuttons)-1:
                    self.select(self.checkbuttons[i+1])
        elif direction == 'up':
            if self.scrollbar.get()[0] == 0.:
                self.cancel_autoscan()
                return
            for i,button in enumerate(self.checkbuttons):
                by0 = button.winfo_rooty()
                if by0-cy0==0 and i > 0:
                    self.select(self.checkbuttons[i-1])
        else:
            raise ValueError("'direction' must be either 'up' or 'down'")
        self.afterId = self.after(50,lambda direction=direction: self.autoscan(direction))
    def cancel_autoscan(self,event=None):
        self.autoscrolling = False
        if self.afterId is not None:
            self.afterId = self.after_cancel(self.afterId)
    def on_checkbutton_click_press(self,event):
        buttons = [b._w for b in self.checkbuttons]
        button = self.checkbuttons[buttons.index(event.widget)]
        self.select(button)
    def on_checkbutton_click_release(self,event):
        self.cancel_autoscan()
        button = self.checkbuttons[self.selection]
        variable = self.variables[self.selection]
        if variable.get() == 0:
            button.select()
            self.last_clicked_button = button
            self.event_generate("<<ComboboxSelected>>",when='mark')
        else:
            button.deselect()
        all_text = [b.cget('text') for b,v in zip(self.checkbuttons,self.variables) if v.get() == 1]
        self.set(all_text)
        self.selection_range(0,'end')
        self.icursor('end')
        return "break"
        
    ### Misc
    def configure_popdown(self,event=None):
        # Set the dimensions of the widgets in the popdown list such that the default Listbox
        # is entirely covered up.
        self.canvas.update()
        self.canvas_frame.update()
        self.checkbutton_frame.update()
        borders = np.array([
            self.popdown.cget('highlightthickness'),
            self.checkbutton_frame.cget('highlightthickness'),
            self.canvas_frame.cget('highlightthickness'),
        ],dtype=int)
        visible_height = 0
        total_height = 0
        for i,button in enumerate(self.checkbuttons):
            button.update()
            bheight = button.winfo_height()
            if i < self.cget('height'): visible_height += bheight
            total_height += bheight
        
        w = self.canvas.winfo_width()
        self.canvas.config(height=visible_height+2*borders[1])
        self.checkbutton_frame.config(height=total_height+2*borders[1],width=w)
        self.canvas_frame.config(height=visible_height+2*np.sum(borders[1:3]))
        if len(self.cget('values')) > self.cget('height'): # If we will have a scrollbar
            self.canvas.config(scrollregion=(0,0,w,total_height))
            self.canvas.config(yscrollincrement=total_height/float(len(self.checkbuttons)))
            self.canvas_frame.grid_configure(padx=(1,0))
            if self.get() == '':
                self.last_clicked_button = self.checkbuttons[0]
                self.canvas.yview_moveto(0.0)
            self.b1_motion_entered_popdown = False
        else:
            self.canvas_frame.grid_configure(padx=1)
        self.checkbutton_frame.update()
        self.popdown_frame.update()
        self.popdown.update()
        #print(visible_height, total_height, self.popdown.winfo_height(), self.popdown_frame.winfo_height())
        
    def popdown_unmap(self,event):
        if event.widget != self.popdown._w: return # Only if the widget is the popdown
        self.autoscrolling = False
        self.mouse_has_entered_popdown = False
    def scroll_to_last_clicked_button(self,event):
        # It depends on how far away our current view is from the last clicked button.
        # If in our view, the last clicked button is above the view and the top button 
        # is > 2 buttons away, the view must be centered on the last clicked button. 
        # Otherwise, the view is made such that the last clicked button appears at the
        # top. Same, but reversed if the last clicked button is below the view.
        if event.widget != self.popdown_frame._w: return # Only if the widget is the popdown_frame
        if not self.scrollbar.winfo_ismapped(): return # Only if the scrollbar is mapped
        button = self.last_clicked_button
        #print(event.widget)
        visible_height = self.canvas.winfo_height()
        total_height = self.checkbutton_frame.winfo_height()
        by0 = button.winfo_y()
        by1 = by0 + button.winfo_height()
        y0 = self.canvas.winfo_rooty()
        y1 = y0 + visible_height
        topbutton = None
        bottombutton = None
        for b in self.checkbuttons:
            if b.winfo_rooty() - y0 == 0:
                topbutton = b
            if b.winfo_rooty() + b.winfo_height() == y1:
                bottombutton = b
        if topbutton is None or bottombutton is None:
            raise Exception("Something went wrong when trying to figure out where the top and bottom buttons in the view are. Perhaps this is a problem with border thicknesses?")
        
        dt = self.checkbuttons.index(button) - self.checkbuttons.index(topbutton)
        db = self.checkbuttons.index(bottombutton) - self.checkbuttons.index(button)
        if dt >= 0 and db < 0: # Gotta scroll the view down
            if db >= -2: # If the bottom button is > 2 buttons away from the last clicked button
                # Scroll the view to place the last clicked button at the bottom of the view
                self.canvas.yview_moveto((by1-visible_height)/total_height)
            else: # Scroll the view to center the last clicked button
                self.canvas.yview_moveto((by1 - 0.5*visible_height)/total_height)
        elif dt < 0 and db >= 0: # Gotta scroll the view up
            if dt >= -2: # If the top button is > 2 buttons away from the last clicked button
                # Scroll the view to place the last clicked button at the top of the view
                self.canvas.yview_moveto(by0/total_height)
            else: # Scroll the view to center the last clicked button
                self.canvas.yview_moveto((by1 - 0.5*visible_height)/total_height)
        # Otherwise, don't do anything
        # Select the last clicked button
        self.select(button)
        
        
# Here is a little test program you can use if you want to :)
if __name__ == "__main__":
    root = tk.Tk()
    values = ('1','2','3','4','5','6','7','8','9','10','11','12','13','14','15','16')
    cb_orig = ttk.Combobox(root,state='readonly',width=100,height=6,values=values)
    cb_orig.grid(row=0,column=0)
    
    cb_orig.bind("<<ComboboxSelected>>",lambda event: print("Selected"))
    #cb_orig.set(1)
    
    cb = ChecklistCombobox(root,state='readonly',checkbutton_height=1,width=100,height=6,values=values)
    cb.grid(row=0,column=1)
    
    def set_custom_look():
        cb.popdown.config(highlightthickness=2)
        cb.canvas_frame.config(highlightthickness=3,highlightbackground='red')
        cb.checkbutton_frame.config(highlightthickness=4,highlightbackground='cyan')
        cb.checkbuttons[2].config(highlightthickness=5)
    
    b = tk.Button(root,text="Set",command=set_custom_look)
    b.grid(row=1,column=0)
    
    root.mainloop()






# Original ttk.Combobox tcl source code
"""
# 
# $Id: combobox.tcl,v 1.2 2008/04/18 12:36:52 ac Exp $ 
# 
# Combobox bindings. 
# 
# Each combobox $cb has a child $cb.popdown, which contains 
# a listbox $cb.popdown.l and a scrollbar.  The listbox -listvariable 
# is set to a namespace variable, which is used to synchronize the 
# combobox values with the listbox values. 
# 
# <<NOTE-WM-TRANSIENT>>: 
# 
#	Need to set [wm transient] just before mapping the popdown 
#	instead of when it's created, in case a containing frame 
#	has been reparented [#1818441]. 
# 
#	On Windows: setting [wm transient] prevents the parent 
#	toplevel from becoming inactive when the popdown is posted 
#	(Tk 8.4.8+) 
# 
#	On X11: WM_TRANSIENT_FOR on override-redirect windows 
#	may be used by compositing managers and by EWMH-aware 
#	window managers (even though the older ICCCM spec says 
#	it's meaningless). 
# 
#	On OSX: [wm transient] does utterly the wrong thing. 
#	Instead, we use [MacWindowStyle "help" "noActivates hideOnSuspend"]. 
#	The "noActivates" attribute prevents the parent toplevel 
#	from deactivating when the popdown is posted, and is also 
#	necessary for "help" windows to receive mouse events. 
#	"hideOnSuspend" makes the popdown disappear (resp. reappear) 
#	when the parent toplevel is deactivated (resp. reactivated). 
#	(see [#1814778]).  Also set [wm resizable 0 0], to prevent 
#	TkAqua from shrinking the scrollbar to make room for a grow box 
#	that isn't there. 
# 
#	In order to work around other platform quirks in TkAqua, 
#	[grab] and [focus] are set in <Map> bindings instead of 
#	immediately after deiconifying the window. 
# 
 
namespace eval ttk::combobox { 
    variable Values	;# Values($cb) is -listvariable of listbox widget 
    variable State 
    set State(entryPress) 0 
} 
 
### Combobox bindings. 
# 
# Duplicate the Entry bindings, override if needed: 
# 
 
ttk::copyBindings TEntry TCombobox 
 
bind TCombobox <KeyPress-Down> 		{ ttk::combobox::Post %W } 
bind TCombobox <KeyPress-Escape> 	{ ttk::combobox::Unpost %W } 
 
bind TCombobox <ButtonPress-1> 		{ ttk::combobox::Press "" %W %x %y } 
bind TCombobox <Shift-ButtonPress-1>	{ ttk::combobox::Press "s" %W %x %y } 
bind TCombobox <Double-ButtonPress-1> 	{ ttk::combobox::Press "2" %W %x %y } 
bind TCombobox <Triple-ButtonPress-1> 	{ ttk::combobox::Press "3" %W %x %y } 
bind TCombobox <B1-Motion>		{ ttk::combobox::Drag %W %x } 
 
bind TCombobox <MouseWheel> 	{ ttk::combobox::Scroll %W [expr {%D/-120}] } 
if {[tk windowingsystem] eq "x11"} { 
    bind TCombobox <ButtonPress-4>	{ ttk::combobox::Scroll %W -1 } 
    bind TCombobox <ButtonPress-5>	{ ttk::combobox::Scroll %W  1 } 
} 
 
bind TCombobox <<TraverseIn>> 		{ ttk::combobox::TraverseIn %W } 
 
### Combobox listbox bindings. 
# 
bind ComboboxListbox <ButtonRelease-1>	{ ttk::combobox::LBSelected %W } 
bind ComboboxListbox <KeyPress-Return>	{ ttk::combobox::LBSelected %W } 
bind ComboboxListbox <KeyPress-Escape>  { ttk::combobox::LBCancel %W } 
bind ComboboxListbox <KeyPress-Tab>	{ ttk::combobox::LBTab %W next } 
bind ComboboxListbox <<PrevWindow>>	{ ttk::combobox::LBTab %W prev } 
bind ComboboxListbox <Destroy>		{ ttk::combobox::LBCleanup %W } 
bind ComboboxListbox <Motion>		{ ttk::combobox::LBHover %W %x %y } 
bind ComboboxListbox <Map>		{ focus -force %W } 
 
switch -- [tk windowingsystem] { 
    win32 { 
	# Dismiss listbox when user switches to a different application. 
	# NB: *only* do this on Windows (see #1814778) 
	bind ComboboxListbox <FocusOut>		{ ttk::combobox::LBCancel %W } 
    } 
} 
 
### Combobox popdown window bindings. 
# 
bind ComboboxPopdown	<Map>		{ ttk::combobox::MapPopdown %W } 
bind ComboboxPopdown	<Unmap>		{ ttk::combobox::UnmapPopdown %W } 
bind ComboboxPopdown	<ButtonPress> \ 
			{ ttk::combobox::Unpost [winfo parent %W] } 
 
### Option database settings. 
# 
 
option add *TCombobox*Listbox.font TkTextFont 
option add *TCombobox*Listbox.relief flat 
option add *TCombobox*Listbox.highlightThickness 0 
 
## Platform-specific settings. 
# 
switch -- [tk windowingsystem] { 
    x11 { 
	option add *TCombobox*Listbox.background white 
    } 
    aqua { 
	option add *TCombobox*Listbox.borderWidth 0 
    } 
} 
 
### Binding procedures. 
# 
 
## Press $mode $x $y -- ButtonPress binding for comboboxes. 
#	Either post/unpost the listbox, or perform Entry widget binding, 
#	depending on widget state and location of button press. 
# 
proc ttk::combobox::Press {mode w x y} { 
    variable State 
    set State(entryPress) [expr { 
	   [$w instate {!readonly !disabled}] 
	&& [string match *textarea [$w identify $x $y]] 
    }] 
 
    focus $w 
    if {$State(entryPress)} { 
	switch -- $mode { 
	    s 	{ ttk::entry::Shift-Press $w $x 	; # Shift } 
	    2	{ ttk::entry::Select $w $x word 	; # Double click} 
	    3	{ ttk::entry::Select $w $x line 	; # Triple click } 
	    ""	- 
	    default { ttk::entry::Press $w $x } 
	} 
    } else { 
	Post $w 
    } 
} 
 
## Drag -- B1-Motion binding for comboboxes. 
#	If the initial ButtonPress event was handled by Entry binding, 
#	perform Entry widget drag binding; otherwise nothing. 
# 
proc ttk::combobox::Drag {w x}  { 
    variable State 
    if {$State(entryPress)} { 
	ttk::entry::Drag $w $x 
    } 
} 
 
## TraverseIn -- receive focus due to keyboard navigation 
#	For editable comboboxes, set the selection and insert cursor. 
# 
proc ttk::combobox::TraverseIn {w} { 
    $w instate {!readonly !disabled} { 
	$w selection range 0 end 
	$w icursor end 
    } 
} 
 
## SelectEntry $cb $index -- 
#	Set the combobox selection in response to a user action. 
# 
proc ttk::combobox::SelectEntry {cb index} { 
    $cb current $index 
    $cb selection range 0 end 
    $cb icursor end 
    event generate $cb <<ComboboxSelected>> -when mark 
} 
 
## Scroll -- Mousewheel binding 
# 
proc ttk::combobox::Scroll {cb dir} { 
    $cb instate disabled { return } 
    set max [llength [$cb cget -values]] 
    set current [$cb current] 
    incr current $dir 
    if {$max != 0 && $current == $current % $max} { 
	SelectEntry $cb $current 
    } 
} 
 
## LBSelected $lb -- Activation binding for listbox 
#	Set the combobox value to the currently-selected listbox value 
#	and unpost the listbox. 
# 
proc ttk::combobox::LBSelected {lb} { 
    set cb [LBMaster $lb] 
    LBSelect $lb 
    Unpost $cb 
    focus $cb 
} 
 
## LBCancel -- 
#	Unpost the listbox. 
# 
proc ttk::combobox::LBCancel {lb} { 
    Unpost [LBMaster $lb] 
} 
 
## LBTab -- Tab key binding for combobox listbox. 
#	Set the selection, and navigate to next/prev widget. 
# 
proc ttk::combobox::LBTab {lb dir} { 
    set cb [LBMaster $lb] 
    switch -- $dir { 
	next	{ set newFocus [tk_focusNext $cb] } 
	prev	{ set newFocus [tk_focusPrev $cb] } 
    } 
 
    if {$newFocus ne ""} { 
	LBSelect $lb 
	Unpost $cb 
	# The [grab release] call in [Unpost] queues events that later 
	# re-set the focus.  [update] to make sure these get processed first: 
	update 
	ttk::traverseTo $newFocus 
    } 
} 
 
## LBHover -- <Motion> binding for combobox listbox. 
#	Follow selection on mouseover. 
# 
proc ttk::combobox::LBHover {w x y} { 
    $w selection clear 0 end 
    $w activate @$x,$y 
    $w selection set @$x,$y 
} 
 
## MapPopdown -- <Map> binding for ComboboxPopdown 
# 
proc ttk::combobox::MapPopdown {w} { 
    [winfo parent $w] state pressed 
    ttk::globalGrab $w 
} 
 
## UnmapPopdown -- <Unmap> binding for ComboboxPopdown 
# 
proc ttk::combobox::UnmapPopdown {w} { 
    [winfo parent $w] state !pressed 
    ttk::releaseGrab $w 
} 
 
### 
# 
 
namespace eval ::ttk::combobox { 
    # @@@ Until we have a proper native scrollbar on Aqua, use 
    # @@@ the regular Tk one.  Use ttk::scrollbar on other platforms. 
    variable scrollbar ttk::scrollbar 
    if {[tk windowingsystem] eq "aqua"} { 
	set scrollbar ::scrollbar 
    } 
} 
 
## PopdownWindow -- 
#	Returns the popdown widget associated with a combobox, 
#	creating it if necessary. 
# 
proc ttk::combobox::PopdownWindow {cb} { 
    variable scrollbar 
 
    if {![winfo exists $cb.popdown]} { 
	set popdown [PopdownToplevel $cb.popdown] 
 
	$scrollbar $popdown.sb \ 
	    -orient vertical -command [list $popdown.l yview] 
	listbox $popdown.l \ 
	    -listvariable ttk::combobox::Values($cb) \ 
	    -yscrollcommand [list $popdown.sb set] \ 
	    -exportselection false \ 
	    -selectmode browse \ 
	    -activestyle none \ 
	    ; 
 
	bindtags $popdown.l \ 
	    [list $popdown.l ComboboxListbox Listbox $popdown all] 
 
	grid $popdown.l $popdown.sb -sticky news 
	grid columnconfigure $popdown 0 -weight 1 
	grid rowconfigure $popdown 0 -weight 1 
    } 
    return $cb.popdown 
} 
 
## PopdownToplevel -- Create toplevel window for the combobox popdown 
# 
#	See also <<NOTE-WM-TRANSIENT>> 
# 
proc ttk::combobox::PopdownToplevel {w} { 
    toplevel $w -class ComboboxPopdown 
    wm withdraw $w 
    switch -- [tk windowingsystem] { 
	default - 
	x11 { 
	    $w configure -relief solid -borderwidth 1 
	    wm overrideredirect $w true 
	} 
	win32 { 
	    $w configure -relief solid -borderwidth 1 
	    wm overrideredirect $w true 
	} 
	aqua { 
	    $w configure -relief solid -borderwidth 0 
	    tk::unsupported::MacWindowStyle style $w \ 
	    	help {noActivates hideOnSuspend} 
	    wm resizable $w 0 0 
	} 
    } 
    return $w 
} 
 
## ConfigureListbox -- 
#	Set listbox values, selection, height, and scrollbar visibility 
#	from current combobox values. 
# 
proc ttk::combobox::ConfigureListbox {cb} { 
    variable Values 
 
    set popdown [PopdownWindow $cb] 
    set values [$cb cget -values] 
    set current [$cb current] 
    if {$current < 0} { 
	set current 0 		;# no current entry, highlight first one 
    } 
    set Values($cb) $values 
    $popdown.l selection clear 0 end 
    $popdown.l selection set $current 
    $popdown.l activate $current 
    $popdown.l see $current 
    set height [llength $values] 
    if {$height > [$cb cget -height]} { 
	set height [$cb cget -height] 
    	grid $popdown.sb 
    } else { 
	grid remove $popdown.sb 
    } 
    $popdown.l configure -height $height 
} 
 
## PlacePopdown -- 
#	Set popdown window geometry. 
# 
# @@@TODO: factor with menubutton::PostPosition 
# 
proc ttk::combobox::PlacePopdown {cb popdown} { 
    set x [winfo rootx $cb] 
    set y [winfo rooty $cb] 
    set w [winfo width $cb] 
    set h [winfo height $cb] 
    set postoffset [ttk::style lookup TCombobox -postoffset {} {0 0 0 0}] 
    foreach var {x y w h} delta $postoffset { 
    	incr $var $delta 
    } 
 
    set H [winfo reqheight $popdown] 
    if {$y + $h + $H > [winfo screenheight $popdown]} { 
	set Y [expr {$y - $H}] 
    } else { 
	set Y [expr {$y + $h}] 
    } 
    wm geometry $popdown ${w}x${H}+${x}+${Y} 
} 
 
## Post $cb -- 
#	Pop down the associated listbox. 
# 
proc ttk::combobox::Post {cb} { 
    # Don't do anything if disabled: 
    # 
    $cb instate disabled { return } 
 
    # ASSERT: ![$cb instate pressed] 
 
    # Run -postcommand callback: 
    # 
    uplevel #0 [$cb cget -postcommand] 
 
    set popdown [PopdownWindow $cb] 
    ConfigureListbox $cb 
    update idletasks 
    PlacePopdown $cb $popdown 
    # See <<NOTE-WM-TRANSIENT>> 
    switch -- [tk windowingsystem] { 
	x11 - win32 { wm transient $popdown [winfo toplevel $cb] } 
    } 
 
    # Post the listbox: 
    # 
    wm deiconify $popdown 
    raise $popdown 
} 
 
## Unpost $cb -- 
#	Unpost the listbox. 
# 
proc ttk::combobox::Unpost {cb} { 
    if {[winfo exists $cb.popdown]} { 
	wm withdraw $cb.popdown 
    } 
    grab release $cb.popdown ;# in case of stuck or unexpected grab [#1239190] 
} 
 
## LBMaster $lb -- 
#	Return the combobox main widget that owns the listbox. 
# 
proc ttk::combobox::LBMaster {lb} { 
    winfo parent [winfo parent $lb] 
} 
 
## LBSelect $lb -- 
#	Transfer listbox selection to combobox value. 
# 
proc ttk::combobox::LBSelect {lb} { 
    set cb [LBMaster $lb] 
    set selection [$lb curselection] 
    if {[llength $selection] == 1} { 
	SelectEntry $cb [lindex $selection 0] 
    } 
} 
 
## LBCleanup $lb -- 
#	<Destroy> binding for combobox listboxes. 
#	Cleans up by unsetting the linked textvariable. 
# 
#	Note: we can't just use { unset [%W cget -listvariable] } 
#	because the widget command is already gone when this binding fires). 
#	[winfo parent] still works, fortunately. 
# 
proc ttk::combobox::LBCleanup {lb} { 
    variable Values 
    unset Values([LBMaster $lb]) 
} 
 
#*EOF* 
"""