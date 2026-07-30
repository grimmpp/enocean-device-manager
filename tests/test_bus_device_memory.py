"""Tests for the taught in sensors of a bus device (Device.memory_entries).

A device which is detected by only listening on the bus reports its model and its
address but not the sensors which are taught into it - they are stored in the
memory of the device. Whenever the memory is read out on the bus (e.g. by PCT14)
the rows are collected and the device is reported again including its sensors.
"""

from eo_man import load_dep_homeassistant
load_dep_homeassistant()

import asyncio

from eltakobus.device import FSR14_4x, SensorInfo
from eltakobus.message import EltakoDiscoveryReply, EltakoMemoryRequest, EltakoMemoryResponse

from eo_man.controller.app_bus import AppBus, AppBusEventType
from eo_man.controller.gateway_registry import GatewayRegistry
from eo_man.controller.serial_controller import SerialController
from eo_man.data.data_manager import DataManager
from eo_man.data.device import Device


BASE_ID = 'FF-CD-60-80'
MEMORY_SIZE = 127


def _build_controller():
    app_bus = AppBus()
    data_manager = DataManager(app_bus)
    serial_controller = SerialController(app_bus, GatewayRegistry(app_bus))
    serial_controller.current_base_id = BASE_ID
    return serial_controller, data_manager


def _discovery_reply(address:int=7, size:int=4) -> EltakoDiscoveryReply:
    """An FSR14_4x at bus address 7, so it occupies the addresses 7 - 10."""
    return EltakoDiscoveryReply(reported_address=address, reported_size=size,
                                memory_size=MEMORY_SIZE, model=b'\x04\x01\x21\x10', is_fam=False)


def _memory_with_sensors() -> list:
    """Memory of an FSR14: rows 8-11 are function group 1, rows 12-126 are
    function group 2. A row contains sensor id, key, key function and the
    channels of the device as bit mask."""
    memory = [bytes(8) for _ in range(MEMORY_SIZE)]
    memory[9] = bytes([0x00, 0x00, 0xB0, 0x07, 0, 51, 0x01, 0])      # channel 1
    memory[12] = bytes([0xFE, 0xDB, 0x0A, 0x1B, 5, 3, 0x01, 0])      # channel 1
    memory[13] = bytes([0xFE, 0xDB, 0xDA, 0x04, 6, 3, 0x02, 0])      # channel 2
    return memory


def _memory_read_out(reply:EltakoDiscoveryReply, memory:list, rows:list=None):
    """The telegrams which appear on the bus while the memory is read out."""
    for row in (range(len(memory)) if rows is None else rows):
        yield EltakoMemoryRequest(reply.reported_address, row)
        yield EltakoMemoryResponse(row, memory[row])


def _entries(device:Device) -> list:
    return [(m.memory_line, m.sensor_id_str, m.key, m.key_func, m.in_func_group)
            for m in device.memory_entries]


def test_device_detected_by_listening_on_the_bus_has_no_memory_entries():
    serial_controller, data_manager = _build_controller()

    serial_controller.process_discovery_message(_discovery_reply())

    bus_devices = sorted([d for d in data_manager.devices.values() if d.bus_device],
                         key=lambda d: d.address)
    # one device per channel of the FSR14_4x
    assert [d.address for d in bus_devices] == ['00-00-00-07', '00-00-00-08',
                                                '00-00-00-09', '00-00-00-0A']
    # the memory was not read out, so the taught in sensors are unknown
    assert all(d.memory_entries == [] for d in bus_devices)


def test_memory_read_out_on_the_bus_fills_the_memory_entries():
    serial_controller, data_manager = _build_controller()
    reply = _discovery_reply()
    serial_controller.process_discovery_message(reply)

    for message in _memory_read_out(reply, _memory_with_sensors()):
        serial_controller.process_memory_message(message)

    # the sensors are assigned to the channel they are programmed for
    assert _entries(data_manager.devices['FF-CD-60-87']) == [(9, '00-00-B0-07', 0, 51, 1),
                                                             (12, 'FE-DB-0A-1B', 5, 3, 2)]
    assert _entries(data_manager.devices['FF-CD-60-88']) == [(13, 'FE-DB-DA-04', 6, 3, 2)]
    assert _entries(data_manager.devices['FF-CD-60-89']) == []


def test_memory_rows_are_assigned_by_row_number_and_not_by_arrival_order():
    serial_controller, data_manager = _build_controller()
    reply = _discovery_reply()
    serial_controller.process_discovery_message(reply)

    rows = list(reversed(range(MEMORY_SIZE)))
    for message in _memory_read_out(reply, _memory_with_sensors(), rows=rows):
        serial_controller.process_memory_message(message)

    assert _entries(data_manager.devices['FF-CD-60-87']) == [(9, '00-00-B0-07', 0, 51, 1),
                                                             (12, 'FE-DB-0A-1B', 5, 3, 2)]


def test_incompletely_read_memory_is_not_reported():
    serial_controller, data_manager = _build_controller()
    reply = _discovery_reply()
    serial_controller.process_discovery_message(reply)

    # row 42 is missing, so the sensors cannot be determined reliably
    rows = [r for r in range(MEMORY_SIZE) if r != 42]
    for message in _memory_read_out(reply, _memory_with_sensors(), rows=rows):
        serial_controller.process_memory_message(message)

    assert data_manager.devices['FF-CD-60-87'].memory_entries == []


def test_memory_of_a_device_which_did_not_announce_itself_is_ignored():
    serial_controller, data_manager = _build_controller()
    reply = _discovery_reply()

    # no discovery reply was received before, so the model of the device is unknown
    for message in _memory_read_out(reply, _memory_with_sensors()):
        serial_controller.process_memory_message(message)

    assert 'FF-CD-60-87' not in data_manager.devices


# =============================================================================
# MARK: - device scan
# =============================================================================

def _report_scanned_device(app_bus:AppBus, reply:EltakoDiscoveryReply, memory:list,
                           force_overwrite:bool=False) -> None:
    """What _scan_for_devices_on_bus does after it has read the memory of a device."""
    device = FSR14_4x(reply)
    device.memory = memory
    asyncio.run(app_bus.async_fire_event(AppBusEventType.ASYNC_DEVICE_DETECTED,
                                         {'device': device, 'base_id': BASE_ID,
                                          'force_overwrite': force_overwrite}))


def test_device_scan_adds_the_memory_entries_to_an_already_known_device():
    """A device which is already known - detected by listening on the bus or loaded
    from a file - is not replaced by the scan result unless existing values may be
    overwritten. Its taught in sensors have to be taken over nevertheless."""
    serial_controller, data_manager = _build_controller()
    reply = _discovery_reply()
    serial_controller.process_discovery_message(reply)
    assert data_manager.devices['FF-CD-60-87'].memory_entries == []

    _report_scanned_device(serial_controller.app_bus, reply, _memory_with_sensors(),
                           force_overwrite=False)

    assert _entries(data_manager.devices['FF-CD-60-87']) == [(9, '00-00-B0-07', 0, 51, 1),
                                                            (12, 'FE-DB-0A-1B', 5, 3, 2)]
    assert _entries(data_manager.devices['FF-CD-60-88']) == [(13, 'FE-DB-DA-04', 6, 3, 2)]


def test_device_scan_keeps_the_values_of_an_already_known_device():
    serial_controller, data_manager = _build_controller()
    reply = _discovery_reply()
    serial_controller.process_discovery_message(reply)

    device = data_manager.devices['FF-CD-60-87']
    device.name = 'Living room'
    device.comment = 'do not overwrite me'

    _report_scanned_device(serial_controller.app_bus, reply, _memory_with_sensors(),
                           force_overwrite=False)

    assert data_manager.devices['FF-CD-60-87'] is device
    assert device.name == 'Living room'
    assert device.comment == 'do not overwrite me'
    assert len(device.memory_entries) == 2


# =============================================================================
# MARK: - Device
# =============================================================================

def test_devices_do_not_share_one_list_of_memory_entries():
    device1 = Device()
    device2 = Device()

    assert device1.memory_entries == []
    assert device1.memory_entries is not device2.memory_entries


def test_merging_does_not_drop_the_memory_entries_of_a_scanned_device():
    sensor = SensorInfo(sensor_id=b'\xfe\xdb\x0a\x1b', dev_type='FSR14_4x', dev_id=7,
                        dev_adr=b'\x00\x00\x00\x07', key=5, key_func=3, channel=1,
                        in_func_group=2, memory_line=12)
    scanned = Device(address='00-00-00-07', external_id='FF-CD-60-87', memory_entries=[sensor])
    # the same device, but only detected by listening on the bus
    listened = Device(address='00-00-00-07', external_id='FF-CD-60-87')

    Device.merge_devices(scanned, listened)

    assert scanned.memory_entries == [sensor]
