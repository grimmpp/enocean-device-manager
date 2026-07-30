import io
import threading
import time

import pytest

from eo_man import load_dep_homeassistant
load_dep_homeassistant()

from eltakobus.eep import G5_3F_7F, F6_02_01
from eltakobus.util import AddressExpression, b2s

from eo_man.controller import cover_travel_tester
from eo_man.controller.app_bus import AppBus, AppBusEventType
from eo_man.controller.cover_travel_tester import (
    Column, Cover, CoverStepType, CoverTestStep, CoverTravelTester, ReportPrinter, Table,
    COVER_COMMAND_UP, COVER_COMMAND_DOWN, COVER_COMMAND_STOP,
)


# =============================================================================
# MARK: - configuration parsing
# =============================================================================

def test_parse_movement_sequence():
    sequence = [CoverTestStep.parse(s) for s in ['up:60', 'pause:5', 'AB:12.5', 'stop', 'wait:1']]

    assert [s.type for s in sequence] == [CoverStepType.UP, CoverStepType.PAUSE, CoverStepType.DOWN,
                                          CoverStepType.STOP, CoverStepType.PAUSE]
    assert [s.duration for s in sequence] == [60.0, 5.0, 12.5, 0.0, 1.0]
    assert str(sequence[0]) == 'UP 60.0s'


def test_parse_movement_sequence_rejects_invalid_entries():
    with pytest.raises(ValueError):
        CoverTestStep.parse('sideways:5')
    with pytest.raises(ValueError):
        CoverTestStep.parse('up')          # duration is mandatory for movements
    with pytest.raises(ValueError):
        CoverTestStep.parse('down:-3')


def test_parse_cover_ids():
    # bus actuators are addressed via the sender ids which this app also uses for Home Assistant
    assert Cover.parse('00-00-00-05') == Cover('00-00-00-05', '00-00-B0-05')
    # an explicitly given sender id wins
    assert Cover.parse('FF-AA-BB-01:00-00-B0-07') == Cover('FF-AA-BB-01', '00-00-B0-07')

    with pytest.raises(ValueError):
        Cover.parse('not-an-address')


def test_device_type_of_command_line_is_mapped_to_the_gateway_display_name():
    # the serial controller expects display names, the command line uses short names
    assert CoverTravelTester._resolve_device_type('fgw14usb') == 'FGW14(-USB) (ESP2)'
    assert CoverTravelTester._resolve_device_type('fam-usb') == 'FAM-USB (ESP2)'
    assert CoverTravelTester._resolve_device_type('esp3-gateway') == 'ESP3 Gateway'
    # display names and unknown values are passed through
    assert CoverTravelTester._resolve_device_type('FAM14 (ESP2)') == 'FAM14 (ESP2)'
    assert CoverTravelTester._resolve_device_type('something-else') == 'something-else'


def test_tester_requires_covers_and_sequence():
    with pytest.raises(ValueError):
        CoverTravelTester(AppBus(), 'COM1', 'fgw14-usb', cover_ids=[], sequence=['up:1'],
                          serial_controller=SerialControllerMock())
    with pytest.raises(ValueError):
        CoverTravelTester(AppBus(), 'COM1', 'fgw14-usb', cover_ids=['00-00-00-05'], sequence=[],
                          serial_controller=SerialControllerMock())


# =============================================================================
# MARK: - simulated test run
# =============================================================================

class SerialControllerMock():
    """Replaces the gateway. Every command which is sent is handed over to the
    connected cover simulations which then answer with status telegrams."""

    def __init__(self, app_bus: AppBus = None):
        self.app_bus = app_bus
        self.sent_messages = []
        self.covers = []
        self.stopped = False

    def establish_serial_connection(self, serial_port: str, device_type: str, **kwargs) -> None:
        pass

    def is_serial_connection_active(self) -> bool:
        return not self.stopped

    def stop_serial_connection(self) -> None:
        self.stopped = True

    def send_message(self, msg) -> None:
        self.sent_messages.append(msg)
        for cover in self.covers:
            cover.process_command(msg)

    def receive(self, msg) -> None:
        self.app_bus.fire_event(AppBusEventType.SERIAL_CALLBACK,
                                {'msg': msg, 'base_id': '00-00-00-00', 'gateway_id': 'mock', 'rssi': None})


class CoverSimulation():
    """A very simple FSB: it moves for the configured time and afterwards
    reports the travel time and - if it ran into it - the end position."""

    def __init__(self, serial_controller: SerialControllerMock, cover: Cover,
                 travel_time_up: float, travel_time_down: float):
        self.serial_controller = serial_controller
        self.cover = cover
        self.travel_times = {COVER_COMMAND_UP: travel_time_up, COVER_COMMAND_DOWN: travel_time_down}
        self.actuator_address = AddressExpression.parse(cover.actuator_id)[0]
        self._timer: threading.Timer = None
        self._started_at: float = None
        self._direction: int = None

    def process_command(self, msg) -> None:
        if b2s(msg.address) != self.cover.sender_id:
            return

        command = msg.data[2]
        if command == COVER_COMMAND_STOP:
            self.stop(reached_end_position=False)
        elif command in self.travel_times:
            self._cancel()
            self._direction = command
            self._started_at = time.time()
            # runtime given in the command telegram (0 = configured runtime of the actuator)
            requested = msg.data[1] / 10.0
            runtime = requested if requested > 0 else self.travel_times[command]
            self._timer = threading.Timer(runtime, self.stop, kwargs={'reached_end_position': requested == 0})
            self._timer.start()

    def stop(self, reached_end_position: bool = False) -> None:
        if self._direction is None:
            return
        self._cancel()
        travelled = time.time() - self._started_at
        direction, self._direction = self._direction, None

        self.serial_controller.receive(
            G5_3F_7F(time=int(round(travelled * 10)), direction=direction).encode_message(self.actuator_address))
        if reached_end_position:
            state = 0x70 if direction == COVER_COMMAND_UP else 0x50
            self.serial_controller.receive(G5_3F_7F(state=state).encode_message(self.actuator_address))

    def _cancel(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None


def _build_tester(sequence: list, command_mode: str = 'stop', travel_up: float = .4, travel_down: float = .6,
                  verbose: int = 0):
    app_bus = AppBus()
    serial_controller = SerialControllerMock(app_bus)
    # the report is written into a buffer instead of the console
    printer = ReportPrinter(stream=io.StringIO(), use_color=False, use_unicode=True)
    tester = CoverTravelTester(app_bus, 'COM-MOCK', 'fgw14-usb',
                               cover_ids=['00-00-00-05', '00-00-00-07'],
                               sequence=sequence,
                               message_delay=0,
                               command_mode=command_mode,
                               verbose=verbose,
                               serial_controller=serial_controller,
                               printer=printer)
    tester.gateway_init_delay = 0
    tester.settle_time = .3
    serial_controller.covers = [CoverSimulation(serial_controller, c, travel_up, travel_down)
                                for c in tester.covers]
    return tester, serial_controller


def test_all_covers_get_the_same_commands():
    tester, serial_controller = _build_tester(['up:1', 'pause:.2', 'down:1'])
    tester.start_test()

    commands = [(b2s(m.address), m.data[2]) for m in serial_controller.sent_messages]
    # both covers reach their end position within the interval, so no STOP is needed
    assert commands == [('00-00-B0-05', COVER_COMMAND_UP), ('00-00-B0-07', COVER_COMMAND_UP),
                        ('00-00-B0-05', COVER_COMMAND_DOWN), ('00-00-B0-07', COVER_COMMAND_DOWN)]


def test_travel_times_are_measured_per_direction():
    tester, _ = _build_tester(['up:1.2', 'pause:.2', 'down:1.2'], travel_up=.4, travel_down=.7)
    movements = tester.start_test()

    assert len(movements) == 4                                   # 2 covers x 2 movements
    for movement in movements:
        expected = .4 if movement.step.type == CoverStepType.UP else .7
        assert movement.reported_travel_time == pytest.approx(expected, abs=.15)
        assert movement.effective_travel_time == pytest.approx(expected, abs=.15)
        assert movement.reached_end_position
        assert movement.direction_ok
        assert not movement.was_interrupted
        assert movement.first_reaction is not None


def test_stop_command_terminates_the_movement_and_travel_time_is_measured():
    # the interval is shorter than the runtime of the cover -> the test sends STOP
    tester, serial_controller = _build_tester(['down:.3', 'pause:.3'], travel_down=5)
    movements = tester.start_test()

    assert [m.data[2] for m in serial_controller.sent_messages] == [
        COVER_COMMAND_DOWN, COVER_COMMAND_DOWN, COVER_COMMAND_STOP, COVER_COMMAND_STOP]
    for movement in movements:
        assert movement.stop_command_time is not None
        assert movement.stopped_by == 'STOP of test'
        assert movement.reported_travel_time == pytest.approx(.3, abs=.15)
        assert not movement.reached_end_position


def test_explicit_stop_step_replaces_the_automatic_stop():
    # 'down:.3,stop' must not send two STOP commands
    tester, serial_controller = _build_tester(['down:.3', 'stop:.2'], travel_down=5)
    movements = tester.start_test()

    assert [m.data[2] for m in serial_controller.sent_messages] == [
        COVER_COMMAND_DOWN, COVER_COMMAND_DOWN, COVER_COMMAND_STOP, COVER_COMMAND_STOP]
    for movement in movements:
        assert movement.stopped_by == 'STOP of test'


def test_timed_mode_puts_the_travel_time_into_the_command_telegram():
    tester, serial_controller = _build_tester(['down:.5', 'pause:.4'], command_mode='timed', travel_down=5)
    movements = tester.start_test()

    # .5s -> 5 * 100ms in DB2, no STOP command is needed
    assert [(m.data[1], m.data[2]) for m in serial_controller.sent_messages] == [
        (5, COVER_COMMAND_DOWN), (5, COVER_COMMAND_DOWN)]
    for movement in movements:
        assert movement.reported_travel_time == pytest.approx(.5, abs=.15)


def test_timed_mode_falls_back_to_stop_for_long_durations(monkeypatch):
    # a travel time above the limit does not fit into the command telegram, so the
    # movement has to be terminated by a STOP command of the test
    monkeypatch.setattr(cover_travel_tester, 'MAX_COMMAND_TRAVEL_TIME', .2)
    tester, serial_controller = _build_tester(['down:.4'], command_mode='timed', travel_down=60)
    movements = tester.start_test()

    # travel time 0 = runtime of the actuator, terminated by STOP
    assert [(m.data[1], m.data[2]) for m in serial_controller.sent_messages] == [
        (0, COVER_COMMAND_DOWN), (0, COVER_COMMAND_DOWN), (0, COVER_COMMAND_STOP), (0, COVER_COMMAND_STOP)]
    for movement in movements:
        assert movement.stopped_by == 'STOP of test'
        assert movement.reported_travel_time == pytest.approx(.4, abs=.15)


def test_interfering_switch_is_recorded_and_travel_time_until_intervention_is_kept():
    tester, serial_controller = _build_tester(['up:2', 'pause:.4'], travel_up=5)

    switch_address = AddressExpression.parse('00-00-00-42')[0]

    def interfere():
        time.sleep(.5)
        # somebody presses a wall switch which stops both covers
        serial_controller.receive(F6_02_01(rocker_first_action=2, energy_bow=1,
                                          rocker_second_action=0, second_action=0).encode_message(switch_address))
        for cover in serial_controller.covers:
            cover.stop(reached_end_position=False)

    threading.Thread(target=interfere, daemon=True).start()
    movements = tester.start_test()

    for movement in movements:
        assert movement.was_interrupted
        assert movement.first_interference.address == '00-00-00-42'
        assert movement.travel_time_until_interference == pytest.approx(.5, abs=.2)
        assert movement.stopped_by == 'switch 00-00-00-42'
        # the travel time until the intervention is still available for the report
        assert movement.reported_travel_time == pytest.approx(.5, abs=.2)


def test_switch_press_during_a_pause_is_no_interference():
    tester, serial_controller = _build_tester(['up:.6', 'pause:1'], travel_up=.2)

    def interfere():
        time.sleep(.8)      # cover already reached its end position
        serial_controller.receive(F6_02_01(rocker_first_action=2, energy_bow=1,
                                          rocker_second_action=0, second_action=0
                                          ).encode_message(AddressExpression.parse('00-00-00-42')[0]))

    threading.Thread(target=interfere, daemon=True).start()
    movements = tester.start_test()

    for movement in movements:
        assert not movement.was_interrupted
        assert movement.reached_end_position


def test_missing_reaction_of_a_cover_is_reported():
    tester, serial_controller = _build_tester(['up:.3'])
    # only the first cover answers
    serial_controller.covers = serial_controller.covers[:1]

    movements = tester.start_test()

    answering = [m for m in movements if m.cover.actuator_id == '00-00-00-05']
    silent = [m for m in movements if m.cover.actuator_id == '00-00-00-07']

    assert all(m.first_reaction is not None for m in answering)
    assert all(m.first_reaction is None for m in silent)
    assert all(m.measured_travel_time is None for m in silent)
    assert all(m.stopped_by == 'no feedback' for m in silent)


def test_own_command_echo_is_not_counted_as_interference():
    tester, serial_controller = _build_tester(['up:.6'], travel_up=.2)

    def echo():
        time.sleep(.05)
        # gateways can echo the telegrams which were sent by this test
        for msg in list(serial_controller.sent_messages):
            serial_controller.receive(msg)

    threading.Thread(target=echo, daemon=True).start()
    movements = tester.start_test()

    for movement in movements:
        assert not movement.was_interrupted
        assert all(e.cover.actuator_id == movement.cover.actuator_id for e in movement.events)


def test_csv_file_contains_all_telegrams(tmp_path):
    tester, _ = _build_tester(['up:.5', 'pause:.2'], travel_up=.2)
    tester.start_test()

    report = tmp_path / "cover_test.csv"
    tester.write_telegrams_to_csv(str(report))

    lines = report.read_text(encoding='utf-8').strip().split('\n')
    assert lines[0].startswith('time [s];source;telegram;address')
    # 2 commands + 2 travel reports + 2 end positions
    assert len(lines) == 1 + 6


# =============================================================================
# MARK: - report output
# =============================================================================

def test_report_contains_all_sections_and_a_verdict():
    tester, _ = _build_tester(['up:.5', 'pause:.2'], travel_up=.2)
    tester.start_test()

    report = '\n'.join(tester.out.lines)
    for section in ['COVER TRAVEL TIME TEST', 'COMMANDS AND REACTION OF THE COVERS',
                    'TRAVEL TIMES PER COVER AND DIRECTION', 'HINTS FOR CONFIGURING THE RUNTIME',
                    'INTERFERENCES']:
        assert section in report, section
    assert 'RESULT: all 2 movements behaved as requested.' in report


def test_verdict_names_the_problems():
    tester, serial_controller = _build_tester(['up:.3'])
    serial_controller.covers = []       # no cover answers

    tester.start_test()

    assert 'RESULT: 0 of 2 movements behaved as requested (2x no reaction).' in '\n'.join(tester.out.lines)


def test_telegrams_are_only_logged_when_verbose_is_set():
    quiet, _ = _build_tester(['up:.5', 'pause:.2'], travel_up=.2, verbose=0)
    quiet.start_test()
    quiet_report = '\n'.join(quiet.out.lines)

    verbose, _ = _build_tester(['up:.5', 'pause:.2'], travel_up=.2, verbose=1)
    verbose.start_test()
    verbose_report = '\n'.join(verbose.out.lines)

    assert 'TELEGRAM LOG' not in quiet_report
    assert 'cover reached TOP END POSITION' not in quiet_report
    # the result itself is shown in both cases
    assert 'TRAVEL TIMES PER COVER AND DIRECTION' in quiet_report

    assert 'TELEGRAM LOG' in verbose_report
    assert 'cover reached TOP END POSITION' in verbose_report


def test_raw_esp2_data_is_only_collected_for_double_verbose():
    tester, _ = _build_tester(['up:.4'], travel_up=.2, verbose=1)
    tester.start_test()
    assert all(e.esp2 == '' for e in tester._events)

    tester, _ = _build_tester(['up:.4'], travel_up=.2, verbose=2)
    tester.start_test()
    assert all(len(e.esp2) > 0 for e in tester._events)
    assert 'ESP2: ' in '\n'.join(tester.out.lines)


def test_report_is_written_to_file(tmp_path):
    tester, _ = _build_tester(['up:.4'], travel_up=.2)
    tester.start_test()

    report = tmp_path / "cover_test.txt"
    tester.write_report_to_file(str(report))

    assert 'COVER TRAVEL TIME TEST' in report.read_text(encoding='utf-8')


def test_printer_falls_back_to_ascii_characters():
    unicode_printer = ReportPrinter(stream=io.StringIO(), use_color=False, use_unicode=True)
    ascii_printer = ReportPrinter(stream=io.StringIO(), use_color=False, use_unicode=False)

    assert (unicode_printer.thin, unicode_printer.vertical, unicode_printer.arrow) == ('─', '│', '→')
    assert (ascii_printer.thin, ascii_printer.vertical, ascii_printer.arrow) == ('-', '|', '->')


def test_table_aligns_and_truncates_cells():
    printer = ReportPrinter(stream=io.StringIO(), use_color=False, use_unicode=True)
    table = Table(printer, [Column('name', 6), Column('value', 4, '>')])

    table.print_header()
    table.print_row(['abcdefgh', 12])
    table.print_row(['ab', None])

    assert printer.lines == ['name   │ value', '─' * 13, 'abcde… │   12', 'ab     │    -']
