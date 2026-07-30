"""Tests that the device details and the device table scroll independently.

tkscrolledframe binds the scroll wheel and the arrow keys to the whole window, so
every scroll event of the application scrolled the detail form as well - scrolling
in the device table moved the details with it. The events are therefore only
handled when they happened inside the detail area.

Only the detail panel is needed, no hardware and no full window.
"""

import tkinter as tk
from tkinter import ttk
import pytest

from eo_man import load_dep_homeassistant
load_dep_homeassistant()

from eo_man.view.device_details import DeviceDetails

try:
    ROOT = tk.Tk()      # one single tk root for all tests, several roots crash on macOS
except tk.TclError:
    pytest.skip("no display available", allow_module_level=True)


class ScrolledFrameStub:
    """records what the form was asked to scroll"""

    def __init__(self):
        self.wheel_events = []
        self.canvas_scrolls = []
        self._canvas = self

    def _scroll_canvas(self, event):
        self.wheel_events.append(event)

    def yview_scroll(self, amount, what):
        self.canvas_scrolls.append(('y', amount))

    def xview_scroll(self, amount, what):
        self.canvas_scrolls.append(('x', amount))


class Event:
    def __init__(self, widget):
        self.widget = widget
        self.delta = -120
        self.num = 5


@pytest.fixture
def details():
    """DeviceDetails reduced to the parts which handle the scrolling"""
    d = DeviceDetails.__new__(DeviceDetails)
    d.root = tk.Frame(ROOT)                     # the detail area
    d.scrolled_frame = ScrolledFrameStub()

    yield d

    d.root.destroy()


def test_scrolling_inside_the_form_scrolls_the_form(details):
    field = tk.Entry(tk.Frame(details.root))    # a field somewhere in the form

    details._on_scroll_wheel(Event(field))

    assert len(details.scrolled_frame.wheel_events) == 1


def test_scrolling_in_the_device_table_does_not_scroll_the_form(details):
    device_table = ttk.Treeview(ROOT)

    details._on_scroll_wheel(Event(device_table))

    assert details.scrolled_frame.wheel_events == []


def test_scrolling_in_another_area_does_not_scroll_the_form(details):
    log_output = tk.Text(ROOT)

    details._on_scroll_wheel(Event(log_output))

    assert details.scrolled_frame.wheel_events == []


def test_a_table_inside_the_form_scrolls_itself_only(details):
    """the device memory table brings its own scrolling, both must not move at once"""
    memory_entries = ttk.Treeview(tk.Frame(details.root))

    details._on_scroll_wheel(Event(memory_entries))

    assert details.scrolled_frame.wheel_events == []


def test_arrow_keys_only_scroll_the_form_when_it_is_used(details):
    details._on_arrow_key(Event(ttk.Treeview(ROOT)), 1, 'y')
    assert details.scrolled_frame.canvas_scrolls == []

    details._on_arrow_key(Event(tk.Label(details.root, text='name')), 1, 'y')
    assert details.scrolled_frame.canvas_scrolls == [('y', 1)]


def test_arrow_keys_in_an_input_field_move_the_cursor(details):
    """otherwise the form jumps around while a value is edited"""
    details._on_arrow_key(Event(tk.Entry(details.root)), -1, 'x')
    details._on_arrow_key(Event(ttk.Combobox(details.root)), 1, 'y')

    assert details.scrolled_frame.canvas_scrolls == []
