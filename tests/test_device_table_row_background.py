"""Tests for the row backgrounds of the device table.

Two highlightings share the background of a row: the green marking of all devices
which are related to the selected device (entered in its memory or containing it in
their config) and the blue blinking of a row when a telegram of that device arrives.
Tk does not guarantee which tag wins if both are set on a row, therefore only one tag
is set at a time and the blinking has to restore the green marking when it is over.

Only the treeview and a data manager stub are needed, no hardware and no full window.
"""

import tkinter as tk
from tkinter import ttk
import pytest

from eo_man import load_dep_homeassistant
load_dep_homeassistant()

from eo_man.view.device_table import DeviceTable

try:
    ROOT = tk.Tk()      # one single tk root for all tests, several roots crash on macOS
except tk.TclError:
    pytest.skip("no display available", allow_module_level=True)


class Table(DeviceTable):
    """DeviceTable reduced to the parts needed for row background and blinking"""

    def __init__(self, treeview:ttk.Treeview, related:dict):
        self.treeview = treeview
        self.blinking_enabled = True
        self._related_rows = set()
        self._blinking_rows = {}
        self._blink_highlighted_rows = set()

        class DataManagerStub:
            def get_related_devices(self, device_external_id:str):
                return [type('Device', (), {'external_id': e}) for e in related.get(device_external_id, [])]

        self.data_manager = DataManagerStub()


@pytest.fixture
def table(request):
    related = getattr(request, 'param', {})

    treeview = ttk.Treeview(ROOT, show="tree")
    treeview.tag_configure('related_devices', background='lightgreen')
    treeview.tag_configure('blinking', background='lightblue')
    for iid in ('actuator', 'sensor_a', 'sensor_b'):
        treeview.insert('', 'end', iid=iid, text=iid)

    yield Table(treeview, related)

    treeview.destroy()


def get_tags(table:Table, iid:str) -> list:
    tags = table.treeview.item(iid)['tags']
    tags = [tags] if isinstance(tags, str) else list(tags)
    return [t for t in tags if t]        # tk may report an empty tag entry


def finish_blinking(table:Table, iid:str) -> None:
    for _ in range(DeviceTable.BLINK_TOGGLES + 1):
        table._blink_step(iid)


@pytest.mark.parametrize('table', [{'actuator': ['sensor_a', 'sensor_b']}], indirect=True)
def test_related_devices_are_marked(table):
    table.mark_related_elements('actuator')

    assert get_tags(table, 'sensor_a') == ['related_devices']
    assert get_tags(table, 'sensor_b') == ['related_devices']
    assert get_tags(table, 'actuator') == []

    # selecting a device without related devices removes the previous marking
    table.mark_related_elements('sensor_a')
    assert get_tags(table, 'sensor_a') == []
    assert get_tags(table, 'sensor_b') == []


@pytest.mark.parametrize('table', [{'actuator': ['sensor_a']}], indirect=True)
def test_blinking_restores_marking_of_related_device(table):
    table.mark_related_elements('actuator')

    table.trigger_blinking('sensor_a')
    ROOT.update()       # runs the scheduled first background change
    assert get_tags(table, 'sensor_a') == ['blinking']

    finish_blinking(table, 'sensor_a')
    assert get_tags(table, 'sensor_a') == ['related_devices']
    assert table._blinking_rows == {}


def test_blinking_of_unmarked_row_ends_without_background(table):
    table.trigger_blinking('sensor_b')
    ROOT.update()
    assert get_tags(table, 'sensor_b') == ['blinking']

    finish_blinking(table, 'sensor_b')
    assert get_tags(table, 'sensor_b') == []


@pytest.mark.parametrize('table', [{'actuator': ['sensor_a']}], indirect=True)
def test_marking_while_blinking_keeps_blinking_visible(table):
    table.trigger_blinking('sensor_a')
    ROOT.update()

    table.mark_related_elements('actuator')     # device gets selected while the row blinks
    assert get_tags(table, 'sensor_a') == ['blinking']

    finish_blinking(table, 'sensor_a')
    assert get_tags(table, 'sensor_a') == ['related_devices']


def test_further_telegram_restarts_blinking(table):
    table.trigger_blinking('sensor_a')
    ROOT.update()
    table._blink_step('sensor_a')

    table.trigger_blinking('sensor_a')
    assert table._blinking_rows['sensor_a'] == DeviceTable.BLINK_TOGGLES
