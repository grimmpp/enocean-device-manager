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
    # a colon instead of a comma between two entries must not silently drop the second one
    with pytest.raises(ValueError, match='comma'):
        CoverTestStep.parse('down:12:pause:2')


def test_parse_cover_ids():
    # bus actuators are addressed via the sender ids which this app also uses for Home Assistant
    assert Cover.parse('00-00-00-05:FE-D4-E9-47') == Cover('00-00-00-05', '00-00-B0-05', ('FE-D4-E9-47',))
    # an explicitly given sender id wins
    assert Cover.parse('FF-AA-BB-01:FE-D4-E9-47:00-00-B0-07') == \
        Cover('FF-AA-BB-01', '00-00-B0-07', ('FE-D4-E9-47',))
    # a cover can be operated by several switches
    assert Cover.parse('00-00-00-05:FE-D4-E9-47+FE-D4-E9-48').switch_ids == ('FE-D4-E9-47', 'FE-D4-E9-48')


def test_cover_id_works_without_a_taught_in_switch():
    # the switch is optional, the sender id of a bus actuator is derived from its address
    assert Cover.parse('00-00-00-05') == Cover('00-00-00-05', '00-00-B0-05', ())
    # no switch, but an explicitly given sender id
    assert Cover.parse('00-00-00-05::00-00-B0-07') == Cover('00-00-00-05', '00-00-B0-07', ())
    # the sender id in the switch position is the sender, not a switch
    assert Cover.parse('00-00-00-06:00-00-B0-06') == Cover('00-00-00-06', '00-00-B0-06', ())
    assert Cover.parse('FF-AA-BB-01:00-00-B0-07:00-00-B0-07') == Cover('FF-AA-BB-01', '00-00-B0-07', ())


def test_cover_id_rejects_ids_which_cannot_be_a_switch():
    # a switch list which contains the sender next to real switches is a mix-up
    with pytest.raises(ValueError, match='sender id'):
        Cover.parse('00-00-00-06:FE-D4-E9-47+00-00-B0-06')
    with pytest.raises(ValueError, match='actuator itself'):
        Cover.parse('00-00-00-06:00-00-00-06')


def test_cover_id_rejects_invalid_entries():
    with pytest.raises(ValueError, match='actuator id'):
        Cover.parse(':FE-D4-E9-47')
    with pytest.raises(ValueError):
        Cover.parse('not-an-address:FE-D4-E9-47')
    with pytest.raises(ValueError):
        Cover.parse('00-00-00-05:FE-D4-E9-47:00-00-B0-05:too-much')


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
        CoverTravelTester(AppBus(), 'COM1', 'fgw14-usb', cover_ids=['00-00-00-05:FE-D4-E9-47'], sequence=[],
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
                  verbose: int = 0, message_delay: float = 0, marker_switch_ids: list = None,
                  marker_double_press_time: float = .4):
    app_bus = AppBus()
    serial_controller = SerialControllerMock(app_bus)
    # the report is written into a buffer instead of the console
    printer = ReportPrinter(stream=io.StringIO(), use_color=False, use_unicode=True)
    tester = CoverTravelTester(app_bus, 'COM-MOCK', 'fgw14-usb',
                               cover_ids=['00-00-00-05:FE-D4-E9-47', '00-00-00-07:FE-D4-E9-48'],
                               sequence=sequence,
                               message_delay=message_delay,
                               command_mode=command_mode,
                               marker_switch_ids=marker_switch_ids,
                               marker_double_press_time=marker_double_press_time,
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


def test_message_delay_is_only_applied_between_the_commands():
    delay = .2
    tester, _ = _build_tester(['up:.8'], travel_up=.3, message_delay=delay)
    movements = tester.start_test()

    commands = [e for e in tester._events if e.outgoing]
    assert len(commands) == 2                                   # one command per cover
    # nothing is waited before the first command ...
    assert commands[0].time == pytest.approx(0, abs=.05)
    # ... and the delay happens between the two commands
    assert commands[1].time - commands[0].time == pytest.approx(delay, abs=.05)
    # the movements start when their own command is sent
    assert movements[1].start_time - movements[0].start_time == pytest.approx(delay, abs=.05)


def test_message_delay_defaults_to_100ms():
    tester = CoverTravelTester(AppBus(), 'COM1', 'fgw14usb', cover_ids=['00-00-00-05:FE-D4-E9-47'],
                               sequence=['up:1'],
                               serial_controller=SerialControllerMock(),
                               printer=ReportPrinter(stream=io.StringIO(), use_color=False))
    assert tester.message_delay == .1


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


ROCKER_BUTTON_VALUES = {'AI': 0, 'A0': 1, 'BI': 2, 'B0': 3}


def _press_switch(serial_controller, address: str, button: str = 'BI', pressed: bool = True):
    """Sends a rocker switch telegram. A real switch sends a press telegram with
    the button and afterwards a release telegram without it."""
    serial_controller.receive(
        F6_02_01(rocker_first_action=ROCKER_BUTTON_VALUES[button] if pressed else 0,
                 energy_bow=1 if pressed else 0, rocker_second_action=0,
                 second_action=0).encode_message(AddressExpression.parse(address)[0]))


def test_taught_in_switch_interrupts_only_the_cover_it_operates():
    # FE-D4-E9-47 is taught into cover 00-00-00-05 only
    tester, serial_controller = _build_tester(['up:2', 'pause:.4'], travel_up=5)

    def interfere():
        time.sleep(.5)
        _press_switch(serial_controller, 'FE-D4-E9-47')
        serial_controller.covers[0].stop(reached_end_position=False)

    threading.Thread(target=interfere, daemon=True).start()
    movements = tester.start_test()

    disturbed = next(m for m in movements if m.cover.actuator_id == '00-00-00-05')
    untouched = next(m for m in movements if m.cover.actuator_id == '00-00-00-07')

    assert disturbed.was_interrupted
    assert disturbed.first_interference.address == 'FE-D4-E9-47'
    assert disturbed.first_interference.is_known_switch
    assert disturbed.travel_time_until_interference == pytest.approx(.5, abs=.2)
    assert disturbed.stopped_by == 'switch FE-D4-E9-47'
    # the travel time until the intervention is still available for the report
    assert disturbed.reported_travel_time == pytest.approx(.5, abs=.2)

    # the other cover has nothing to do with that switch
    assert not untouched.was_interrupted
    assert 'FE-D4-E9-47' not in [e.address for e in untouched.events]


# =============================================================================
# MARK: - marker switch
# =============================================================================

def test_single_press_of_the_marker_switch_records_the_point_in_time():
    tester, serial_controller = _build_tester(['up:1.2'], travel_up=1, marker_switch_ids=['FF-11-22-33'])

    def mark():
        time.sleep(.5)
        _press_switch(serial_controller, 'FF-11-22-33')

    threading.Thread(target=mark, daemon=True).start()
    movements = tester.start_test()

    for movement in movements:
        assert len(movement.markers) == 1
        marker = movement.markers[0]
        assert marker.time - movement.start_time == pytest.approx(.5, abs=.15)
        assert not marker.is_manual_end_position
        # a marker switch is not taught into the actuator, so it cannot have stopped anything
        assert not movement.was_interrupted
        assert movement.manual_end_position_time is None


def test_double_press_of_the_marker_switch_is_a_manual_end_position():
    # the actuator runs 1.4s although the cover physically stands still after 0.6s
    tester, serial_controller = _build_tester(['up:2'], travel_up=1.4, marker_switch_ids=['FF-11-22-33'])

    def mark():
        time.sleep(.6)
        _press_switch(serial_controller, 'FF-11-22-33')
        time.sleep(.2)                      # within marker_double_press_time (.4s)
        _press_switch(serial_controller, 'FF-11-22-33')

    threading.Thread(target=mark, daemon=True).start()
    movements = tester.start_test()

    for movement in movements:
        # the first press of the pair is the moment the observer reacted
        assert movement.manual_end_position_time == pytest.approx(.6, abs=.15)
        assert movement.manual_end_position.is_manual_end_position
        assert not movement.was_interrupted
        # the actuator still reports its own (longer) runtime
        assert movement.reported_travel_time == pytest.approx(1.4, abs=.2)

    report = '\n'.join(tester.out.lines)
    assert 'END POSITION REACHED' in report
    assert 'MARKER SWITCH' in report


def test_two_slow_presses_are_two_separate_time_markers():
    tester, serial_controller = _build_tester(['up:1.6'], travel_up=1.5, marker_switch_ids=['FF-11-22-33'],
                                              marker_double_press_time=.3)

    def mark():
        time.sleep(.4)
        _press_switch(serial_controller, 'FF-11-22-33')
        time.sleep(.6)                      # longer than marker_double_press_time
        _press_switch(serial_controller, 'FF-11-22-33')

    threading.Thread(target=mark, daemon=True).start()
    movements = tester.start_test()

    for movement in movements:
        assert len(movement.markers) == 2
        assert all(not m.is_manual_end_position for m in movement.markers)
        assert movement.manual_end_position_time is None


def test_manual_end_position_is_used_for_the_runtime_recommendation():
    tester, serial_controller = _build_tester(['up:1.5', 'pause:.3'], travel_up=1.2,
                                              marker_switch_ids=['FF-11-22-33'])

    def mark():
        time.sleep(.5)
        _press_switch(serial_controller, 'FF-11-22-33')
        time.sleep(.15)
        _press_switch(serial_controller, 'FF-11-22-33')

    threading.Thread(target=mark, daemon=True).start()
    tester.start_test()

    report = '\n'.join(tester.out.lines)
    # the recommendation uses the manually measured 0.5s, not the 1.2s of the actuator
    assert 'up 0.5s' in report
    assert 'based on the end position which was signalled with the marker switch' in report


def test_markers_are_numbered_per_movement():
    tester, serial_controller = _build_tester(['up:1.4', 'pause:.3', 'down:1.4'], travel_up=1.3, travel_down=1.3,
                                              marker_switch_ids=['FF-11-22-33'], marker_double_press_time=.3)

    def mark():
        for _ in range(2):                          # two markers during the UP movement
            time.sleep(.5)
            _press_switch(serial_controller, 'FF-11-22-33')
        time.sleep(1.2)                             # DOWN movement started
        _press_switch(serial_controller, 'FF-11-22-33')

    threading.Thread(target=mark, daemon=True).start()
    movements = tester.start_test()

    up = [m for m in movements if m.step.type == CoverStepType.UP]
    down = [m for m in movements if m.step.type == CoverStepType.DOWN]
    assert all(len(m.markers) == 2 for m in up)
    assert all(len(m.markers) == 1 for m in down)

    # the numbering restarts with every movement
    lines = [l for l in tester.out.lines if 'FF-11-22-33 │' in l]
    numbers = [l.split('│')[4].strip() for l in lines]
    assert numbers == ['1', '2', '1', '2', '1', '1']


def test_release_telegrams_are_no_markers():
    # every press of a real switch is followed by a release telegram
    tester, serial_controller = _build_tester(['up:1.4'], travel_up=1.3, marker_switch_ids=['FF-11-22-33'])

    def mark():
        time.sleep(.5)
        _press_switch(serial_controller, 'FF-11-22-33', 'AI', pressed=True)
        time.sleep(.15)
        _press_switch(serial_controller, 'FF-11-22-33', 'AI', pressed=False)

    threading.Thread(target=mark, daemon=True).start()
    movements = tester.start_test()

    for movement in movements:
        # one press, not two entries
        assert len(movement.markers) == 1
        assert movement.markers[0].button == 'AI'
        assert movement.markers[0].is_button_pressed


def test_two_different_buttons_are_not_a_double_press():
    tester, serial_controller = _build_tester(['up:1.4'], travel_up=1.3, marker_switch_ids=['FF-11-22-33'],
                                              marker_double_press_time=1.5)

    def mark():
        time.sleep(.4)
        _press_switch(serial_controller, 'FF-11-22-33', 'AI')
        time.sleep(.2)                      # within the window, but another button
        _press_switch(serial_controller, 'FF-11-22-33', 'B0')

    threading.Thread(target=mark, daemon=True).start()
    movements = tester.start_test()

    for movement in movements:
        assert [m.button for m in movement.markers] == ['AI', 'B0']
        assert all(not m.is_manual_end_position for m in movement.markers)
        assert movement.manual_end_position_time is None

    # the same button twice in a row is still a double press
    tester, serial_controller = _build_tester(['up:1.4'], travel_up=1.3, marker_switch_ids=['FF-11-22-33'],
                                              marker_double_press_time=1.5)

    def mark_same():
        time.sleep(.4)
        _press_switch(serial_controller, 'FF-11-22-33', 'AI')
        time.sleep(.2)
        _press_switch(serial_controller, 'FF-11-22-33', 'AI')

    threading.Thread(target=mark_same, daemon=True).start()
    for movement in tester.start_test():
        assert movement.manual_end_position_time == pytest.approx(.4, abs=.15)


def test_marker_table_shows_the_pressed_button():
    tester, serial_controller = _build_tester(['up:1.2'], travel_up=1, marker_switch_ids=['FF-11-22-33'])

    def mark():
        time.sleep(.4)
        _press_switch(serial_controller, 'FF-11-22-33', 'A0')

    threading.Thread(target=mark, daemon=True).start()
    tester.start_test()

    lines = [l for l in tester.out.lines if 'FF-11-22-33 │' in l]
    assert lines, "no marker row in the report"
    assert all('│ A0' in l for l in lines)


def test_marker_switch_must_not_be_a_taught_in_switch():
    with pytest.raises(ValueError, match='marker switch'):
        _build_tester(['up:1'], marker_switch_ids=['FE-D4-E9-47'])
    with pytest.raises(ValueError, match='marker switch'):
        _build_tester(['up:1'], marker_switch_ids=['00-00-00-05'])


def test_telegram_of_an_unknown_device_disturbs_every_running_movement():
    tester, serial_controller = _build_tester(['up:2', 'pause:.4'], travel_up=5)

    def interfere():
        time.sleep(.5)
        # an address which was not declared as a switch of one of the covers
        _press_switch(serial_controller, '00-00-00-42')
        for cover in serial_controller.covers:
            cover.stop(reached_end_position=False)

    threading.Thread(target=interfere, daemon=True).start()
    movements = tester.start_test()

    for movement in movements:
        assert movement.was_interrupted
        assert not movement.first_interference.is_known_switch
        assert movement.stopped_by == 'unknown 00-00-00-42'


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


def test_status_telegram_of_an_unknown_address_is_no_reaction_of_a_cover():
    """The actuator ids must match the sender address of the received telegrams.
    Bus actuators send with their local bus address, not with their external id.
    Their status telegrams must not be counted as a reaction of the cover."""
    tester, serial_controller = _build_tester(['down:.3'], travel_down=5)
    # the configured ids are the external ids ...
    tester.covers[0].actuator_id = 'EF-00-00-05'
    tester.covers[1].actuator_id = 'EF-00-00-07'
    tester._covers_by_actuator_id = {c.actuator_id: c for c in tester.covers}
    # ... while the actuators answer with their local bus address
    for simulation, address in zip(serial_controller.covers, ['00-00-00-05', '00-00-00-07']):
        simulation.actuator_address = AddressExpression.parse(address)[0]

    movements = tester.start_test()

    for movement in movements:
        assert movement.first_reaction is None
        assert movement.measured_travel_time is None
        assert movement.stopped_by == 'no feedback'
        assert 'no reaction' in movement.problems

    report = '\n'.join(tester.out.lines)
    assert 'No telegram of a cover under test was received' in report
    # the addresses which really sent telegrams are listed as hint
    assert '00-00-00-05, 00-00-00-07' in report


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
