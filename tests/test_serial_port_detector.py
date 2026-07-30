"""Tests for the detection of the gateway type behind a serial port.

The detection has no positive test for every gateway, it works by exclusion, so
the order of the single tests carries the meaning and must not change silently.
The communicators are replaced by fakes, no hardware is needed.
"""

import asyncio
import threading
import types

from eo_man import load_dep_homeassistant
load_dep_homeassistant()

from eo_man.controller import serial_port_detector as spd
from eo_man.controller.app_bus import AppBus, AppBusEventType
from eo_man.controller.serial_port_detector import SerialPortDetector
from eo_man.data.const import GatewayDeviceType as GDT


class PortInfoMock():

    def __init__(self, device:str, vid:int=0x0403):
        self.device = device
        self.vid = vid


class CommunicatorMock():
    """Replaces ESP3SerialCommunicator and RS485SerialInterfaceV2."""

    def __init__(self, connects:bool=True, suppress_echo:bool=False, esp3_base_id=None):
        self.is_serial_connected = threading.Event()
        self.suppress_echo = suppress_echo
        self.stopped = False
        self._connects = connects
        self._esp3_base_id = esp3_base_id

    def start(self):
        if self._connects:
            self.is_serial_connected.set()

    @property
    def async_base_id(self):
        async def get_base_id():
            return self._esp3_base_id
        return get_base_id()

    def stop(self):
        self.stopped = True

    def join(self, timeout=None):
        pass

    def set_callback(self, callback):
        pass


def _install_mocks(monkeypatch, ports:list, esp3=None, rs485=None, fam_usb_base_id:str=None) -> dict:
    """esp3/rs485 are factories (port, baud_rate) -> CommunicatorMock."""
    monkeypatch.setattr(spd.serial.tools.list_ports, 'comports', lambda: ports)
    monkeypatch.setattr(spd.serial, 'Serial', lambda *a, **kw: types.SimpleNamespace(close=lambda: None))

    created = {'esp3': [], 'rs485': [], 'fam_usb_tests': []}

    def create_esp3(port, **kwargs):
        communicator = esp3(port, 57600) if esp3 else CommunicatorMock()
        created['esp3'].append(communicator)
        return communicator

    def create_rs485(port, baud_rate=None, **kwargs):
        communicator = rs485(port, baud_rate) if rs485 else CommunicatorMock()
        created['rs485'].append(communicator)
        return communicator

    monkeypatch.setattr(spd, 'ESP3SerialCommunicator', create_esp3)
    monkeypatch.setattr(spd, 'RS485SerialInterfaceV2', create_rs485)

    async def async_get_base_id_for_fam_usb(self, fam_usb, callback):
        created['fam_usb_tests'].append(fam_usb)
        return fam_usb_base_id

    monkeypatch.setattr(SerialPortDetector, 'async_get_base_id_for_fam_usb',
                        async_get_base_id_for_fam_usb)
    return created


def _detect(**kwargs) -> dict:
    return asyncio.run(SerialPortDetector(AppBus()).async_get_gateway2serial_port_mapping(**kwargs))


def test_fam14_is_detected_by_the_echo_of_its_adapter(monkeypatch):
    created = _install_mocks(monkeypatch, [PortInfoMock('COM1')],
                             rs485=lambda port, baud: CommunicatorMock(suppress_echo=True))

    result = _detect()

    assert result[GDT.EltakoFAM14.value] == ['COM1']
    assert result['all'] == ['COM1']
    # the echo is the cheapest test, nothing else must be tried afterwards
    assert created['fam_usb_tests'] == []


def test_fam_usb_is_detected_before_the_fgw14(monkeypatch):
    """The FGW14 test matches every port which is reachable and does not echo, so
    a FAM-USB would be reported as FGW14 if it was not tested first."""
    _install_mocks(monkeypatch, [PortInfoMock('COM1')], fam_usb_base_id='FF-AA-BB-CC')

    result = _detect()

    assert result[GDT.EltakoFAMUSB.value] == ['COM1']
    assert result[GDT.EltakoFGW14USB.value] == []


def test_fam_usb_is_not_tested_on_a_port_without_usb_vendor_id(monkeypatch):
    """A FAM-USB is a USB stick. Its test costs a full timeout, so it is skipped
    for built-in serial ports, bluetooth ports and the like."""
    created = _install_mocks(monkeypatch, [PortInfoMock('/dev/ttyS0', vid=None)],
                             fam_usb_base_id='FF-AA-BB-CC')

    result = _detect()

    assert created['fam_usb_tests'] == []
    # FAM14 and FGW14 are still tested, they can be behind such a port
    assert result[GDT.EltakoFGW14USB.value] == ['/dev/ttyS0']


def test_esp3_gateway_is_detected_by_its_base_id(monkeypatch):
    _install_mocks(monkeypatch, [PortInfoMock('COM1')],
                   esp3=lambda port, baud: CommunicatorMock(esp3_base_id=[0xFF, 0xAA, 0xBB, 0xCC]))

    result = _detect()

    assert result[GDT.ESP3.value] == ['COM1']


def test_port_is_still_tested_for_fam14_when_the_esp3_test_cannot_connect(monkeypatch):
    """The esp3 test runs first with 57600 baud. If its communicator cannot open
    the port the remaining tests must still run for that port."""
    _install_mocks(monkeypatch, [PortInfoMock('COM1')],
                   esp3=lambda port, baud: CommunicatorMock(connects=False),
                   # answers only with 57600 baud, so the fam14 test of the first
                   # round with 9600 baud does not claim the port already
                   rs485=lambda port, baud: CommunicatorMock(connects=baud == 57600,
                                                             suppress_echo=True))

    result = _detect()

    assert result[GDT.EltakoFAM14.value] == ['COM1']


def test_a_port_without_any_gateway_is_not_reported(monkeypatch):
    _install_mocks(monkeypatch, [PortInfoMock('COM1')],
                   rs485=lambda port, baud: CommunicatorMock(connects=False))

    result = _detect()

    assert result['all'] == []


def test_every_detected_gateway_is_published_immediately(monkeypatch):
    """The port list of the UI is updated while the detection is still running."""
    _install_mocks(monkeypatch, [PortInfoMock('COM1'), PortInfoMock('COM2')],
                   rs485=lambda port, baud: CommunicatorMock(suppress_echo=True))

    published = []
    result = _detect(callback=lambda r: published.append(list(r['all'])))

    assert published == [['COM1'], ['COM1', 'COM2']]
    assert result[GDT.EltakoFAM14.value] == ['COM1', 'COM2']


def test_progress_reaches_100_percent(monkeypatch):
    _install_mocks(monkeypatch, [PortInfoMock('COM1'), PortInfoMock('COM2'),
                                 PortInfoMock('COM3')])

    app_bus = AppBus()
    progress = []
    handler_id = app_bus.add_event_handler(AppBusEventType.DEVICE_ITERATION_PROGRESS,
                                          lambda p: progress.append(round(p)))
    try:
        asyncio.run(SerialPortDetector(app_bus).async_get_gateway2serial_port_mapping())
    finally:
        app_bus.remove_event_handler_by_id(handler_id)

    # one step per port and baud rate, 0 resets the progress bar at the end
    assert progress == [17, 33, 50, 67, 83, 100, 0]


def test_communicators_are_closed_again(monkeypatch):
    created = _install_mocks(monkeypatch, [PortInfoMock('COM1')],
                             esp3=lambda port, baud: CommunicatorMock(connects=False))

    _detect()

    assert all(c.stopped for c in created['esp3']), "esp3 communicator was not stopped"
    assert all(c.stopped for c in created['rs485']), "rs485 communicator was not stopped"
