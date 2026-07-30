"""Tests for ending the application when the window is closed.

Background work runs in threads. A thread which is no daemon thread keeps the
interpreter running, so the application would stay alive without a window.
"""

import threading
import types

from eo_man import load_dep_homeassistant
load_dep_homeassistant()

from eltakobus.serial import RS485SerialInterfaceV2

from eo_man.controller import serial_controller
from eo_man.controller.app_bus import AppBus, AppBusEventType
from eo_man.controller.gateway_registry import GatewayRegistry
from eo_man.controller.lan_service_detector import LanServiceDetector
from eo_man.controller.serial_controller import SerialController
from eo_man.controller.serial_port_detector import SerialPortDetector
from eo_man.view.main_panel import MainPanel


def test_the_serial_interface_of_eltakobus_is_no_daemon_thread():
    """Assumption the shutdown handling is based on. If this ever changes the
    explicit daemon flags can be removed again."""
    bus = RS485SerialInterfaceV2('/dev/null', baud_rate=57600, auto_reconnect=False)

    assert bus.daemon is False


def test_closing_is_announced_only_once():
    app_bus = AppBus()
    closed = []
    handler_id = app_bus.add_event_handler(AppBusEventType.WINDOW_CLOSED, lambda d: closed.append(d))

    panel = MainPanel.__new__(MainPanel)      # no window needed for this
    panel.app_bus = app_bus
    panel._is_closed = threading.Event()
    try:
        panel._close()
        # _shutdown closes as well, the window can be closed without on_closing
        panel._close()
    finally:
        app_bus.remove_event_handler_by_id(handler_id)

    assert len(closed) == 1


def test_communicators_of_the_port_detection_are_daemon_threads():
    """A port which blocks while being probed must not keep the application alive."""
    class CommunicatorMock():
        def __init__(self):
            self.daemon = False
            self.started = False

        def start(self):
            self.started = True

    communicator = CommunicatorMock()
    SerialPortDetector(AppBus())._start(communicator)

    assert communicator.daemon is True
    assert communicator.started


def test_writing_sender_ids_runs_in_a_daemon_thread(monkeypatch):
    app_bus = AppBus()
    controller = SerialController(app_bus, GatewayRegistry(app_bus))

    created = []

    class ThreadMock():
        def __init__(self, *args, **kwargs):
            created.append(kwargs)

        def start(self):
            pass

    monkeypatch.setattr(serial_controller.threading, 'Thread', ThreadMock)
    controller.write_sender_id_to_devices({})

    assert len(created) == 1
    assert created[0].get('daemon') is True


def test_mdns_service_discovery_can_be_stopped_twice():
    closed = []
    detector = LanServiceDetector.__new__(LanServiceDetector)
    detector.zeroconf = types.SimpleNamespace(close=lambda: closed.append(1))

    detector.stop()
    detector.stop()

    assert closed == [1]


def test_closing_the_window_stops_the_mdns_service_discovery():
    app_bus = AppBus()
    registry = GatewayRegistry(app_bus)
    stopped = []
    registry.lan_service_detector.stop = lambda: stopped.append(1)

    app_bus.fire_event(AppBusEventType.WINDOW_CLOSED, {})

    assert stopped == [1]
