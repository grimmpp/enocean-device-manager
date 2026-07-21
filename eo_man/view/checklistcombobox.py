import tkinter as tk  # Python 3 only
import tkinter.ttk as ttk


class ChecklistCombobox(ttk.Menubutton):
    """
    A combobox-like widget that lets the user tick several values at once.

    Why this is not a ttk.Combobox
    ------------------------------
    The previous implementation (Roger Hatfull's ChecklistCombobox) worked by
    reaching into the private ttk.Combobox popdown internals (``.popdown.f.l``
    listbox, frame and scrollbar) and stacking check buttons on top of them.
    Tk 9.0 (shipped with Python 3.14) redesigned that popdown: on macOS it is
    now a native menu (``.popdown.menu``) with no Tk listbox at all, so the old
    approach raised ``invalid command name "...popdown.f.l"`` and could not be
    revived with a small patch.

    This version is built purely on public widgets -- a ``ttk.Menubutton`` whose
    menu contains one check-button entry per value. It depends on no ttk
    internals and therefore behaves the same on macOS (aqua), Windows and X11.

    Public API (kept compatible with the old widget so callers don't change):
        * constructor accepts ``values=`` and ``width=``
        * ``get()``            -> ``''`` / single ``str`` / ``list[str]`` of ticked values
        * ``set(value)``       -> tick the values in ``value`` (``str`` or list-like)
        * ``delete(first, last=None)`` -> clear the whole selection
        * ``variables``        -> ``list[tk.IntVar]`` aligned with ``values``
        * ``checkbuttons``     -> list of items exposing ``cget('text')`` /
                                  ``select()`` / ``deselect()``
        * ``values``           -> current list of selectable values
    """

    class _Item:
        """Lightweight stand-in for the old tk.Checkbutton objects, exposing
        only the parts callers actually use."""

        def __init__(self, text: str, var: tk.IntVar):
            self._text = text
            self._var = var

        def cget(self, key: str):
            if key == 'text':
                return self._text
            raise KeyError(key)

        def select(self):
            self._var.set(1)

        def deselect(self):
            self._var.set(0)

    def __init__(self, master=None, values=None, width=None, **kw):
        self.values = list(values) if values is not None else []
        self._textvar = tk.StringVar(master, value='')

        mb_kw = dict(textvariable=self._textvar, direction='below')
        if width is not None:
            mb_kw['width'] = int(width)
        mb_kw.update(kw)
        super().__init__(master, **mb_kw)

        self._menu = tk.Menu(self, tearoff=0)
        self['menu'] = self._menu

        self.variables: list[tk.IntVar] = []
        self.checkbuttons: list[ChecklistCombobox._Item] = []
        self._build_menu()

    # ------------------------------------------------------------------ #
    # Menu construction
    # ------------------------------------------------------------------ #
    def _build_menu(self):
        self._menu.delete(0, 'end')
        self.variables = []
        self.checkbuttons = []
        for text in self.values:
            var = tk.IntVar(self, value=0)
            self._menu.add_checkbutton(
                label=text,
                variable=var,
                onvalue=1,
                offvalue=0,
                command=self._on_toggle,
            )
            self.variables.append(var)
            self.checkbuttons.append(self._Item(text, var))
        self._refresh_text()

    def _on_toggle(self):
        self._refresh_text()
        self.event_generate('<<ComboboxSelected>>')

    def _refresh_text(self):
        selected = [t for t, v in zip(self.values, self.variables) if v.get() == 1]
        self._textvar.set(', '.join(selected))

    def _selected(self) -> list[str]:
        return [t for t, v in zip(self.values, self.variables) if v.get() == 1]

    # ------------------------------------------------------------------ #
    # Public API (compatible with the old widget / a ttk.Entry)
    # ------------------------------------------------------------------ #
    def get(self):
        selected = self._selected()
        if len(selected) > 1:
            return selected
        if len(selected) == 1:
            return selected[0]
        return ''

    def set(self, value):
        if isinstance(value, (list, tuple, set)):
            wanted = [str(v).strip() for v in value]
        else:
            wanted = [s.strip() for s in str(value).split(',') if s.strip()]
        for text, var in zip(self.values, self.variables):
            var.set(1 if text in wanted else 0)
        self._refresh_text()

    def delete(self, first=0, last=None):
        # Mirrors ttk.Entry.delete as used by the filter bar's reset: clear all.
        for var in self.variables:
            var.set(0)
        self._refresh_text()

    def set_values(self, values):
        """Repopulate the selectable values (like assigning a Combobox's -values)."""
        self.values = list(values)
        self._build_menu()


# A little test program you can run with `python checklistcombobox.py`
if __name__ == "__main__":
    root = tk.Tk()

    values = ('1', '2', '3', '4', '5', '6', '7', '8', '9', '10',
              '11', '12', '13', '14', '15', '16')

    cb = ChecklistCombobox(root, values=values, width=20)
    cb.grid(row=0, column=0, padx=10, pady=10)
    cb.bind('<<ComboboxSelected>>', lambda e: print("Selected:", cb.get()))

    tk.Button(root, text="Set 2,4,6", command=lambda: cb.set(['2', '4', '6'])).grid(row=1, column=0)
    tk.Button(root, text="Clear", command=lambda: cb.delete(0, 'end')).grid(row=2, column=0)
    tk.Button(root, text="Print get()", command=lambda: print(repr(cb.get()))).grid(row=3, column=0)

    root.mainloop()
