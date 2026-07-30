"""Travel time test for Eltako cover actuators (FSB14, FSB61, FJ62, ...).

The test drives a list of covers with a user defined sequence of movement
commands and pauses, records every telegram which is sent and received and
finally prints a detailed report which allows to verify

* whether all covers reacted on every command and in the expected direction,
* how long every cover really moved (measured and as reported by the actuator),
* which foreign telegrams (e.g. wall switches) interfered with the test and
  how much travel time was accumulated until the interference happened.

The measured travel times are the base for configuring the runtime of an FSB
actuator. The actuator only knows one runtime for the whole cover although
moving up, moving down and turning the slats of a venetian blind usually take
a different amount of time.
"""

import sys
import threading
import time

from dataclasses import dataclass, field
from enum import Enum

from termcolor import colored

from eltakobus.eep import H5_3F_7F, G5_3F_7F, F6_02_01
from eltakobus.message import EltakoPoll, EltakoTimeout, ESP2Message
from eltakobus.util import b2s, AddressExpression

from ..data.const import GatewayDeviceType, GATEWAY_DISPLAY_NAMES
from ..data.data_helper import format_rssi

from .app_bus import AppBus, AppBusEventType
from .gateway_registry import GatewayRegistry
from .serial_controller import SerialController


# Commands of the Eltako cover command EEP H5-3F-7F (DB1)
COVER_COMMAND_STOP = 0x00
COVER_COMMAND_UP = 0x01
COVER_COMMAND_DOWN = 0x02

# Travel time of a command telegram is transferred in DB2 in 100ms steps.
MAX_COMMAND_TRAVEL_TIME = 25.5

# Status values of the Eltako cover status EEP G5-3F-7F which are sent as RPS
# telegram. Values which are not listed here are shown as raw value.
COVER_END_POSITIONS = {
    0x70: 'TOP END POSITION',
    0x50: 'BOTTOM END POSITION',
}

# The actuators announce the start of a movement with the same RPS telegram.
# Verified with FSB14 on a FGW14-USB: those devices send no 4BS travel report
# at all, so this is the only source for the direction they really moved.
COVER_MOVEMENT_STARTED = {
    0x01: COVER_COMMAND_UP,
    0x02: COVER_COMMAND_DOWN,
}

# First action of a rocker switch telegram (EEP F6-02-01)
ROCKER_BUTTONS = {0: 'AI', 1: 'A0', 2: 'BI', 3: 'B0'}

# Two presses of a marker switch within this time are one double press.
DEFAULT_MARKER_DOUBLE_PRESS_TIME = 1.5

# width of the separator lines of the printed report
REPORT_WIDTH = 130

# Semantic styles of the report: (termcolor color, termcolor attributes)
STYLES = {
    'title': ('light_cyan', ['bold']),
    'header': ('light_cyan', None),
    'frame': ('dark_grey', None),
    'hint': ('dark_grey', None),
    'label': ('white', None),
    'ok': ('light_green', None),
    'warn': ('yellow', None),
    'error': ('light_red', None),
    'sent': ('light_blue', None),
    'received': (None, None),
    'foreign': ('yellow', None),
}


class ReportPrinter:
    """Writes the report directly to the console: aligned, colored and framed
    with box drawing characters if the terminal supports them. Every line is
    collected as plain text so that the whole report can be saved to a file."""

    def __init__(self, stream=None, width: int = REPORT_WIDTH, use_color: bool = None,
                 use_unicode: bool = None) -> None:
        self.stream = stream if stream is not None else sys.stdout
        self.width = width
        self.use_color = self._supports_color() if use_color is None else use_color
        self.use_unicode = self._supports_unicode() if use_unicode is None else use_unicode
        self.lines: list[str] = []

    def _supports_color(self) -> bool:
        try:
            return self.stream.isatty()
        except Exception:
            return False

    def _supports_unicode(self) -> bool:
        try:
            '─│•→…'.encode(getattr(self.stream, 'encoding', None) or 'ascii')
            return True
        except Exception:
            return False

    # characters which depend on the capabilities of the terminal
    @property
    def thin(self) -> str:
        return '─' if self.use_unicode else '-'

    @property
    def bold(self) -> str:
        return '━' if self.use_unicode else '='

    @property
    def vertical(self) -> str:
        return '│' if self.use_unicode else '|'

    @property
    def arrow(self) -> str:
        return '→' if self.use_unicode else '->'

    @property
    def ellipsis(self) -> str:
        return '…' if self.use_unicode else '~'

    def line(self, text: str = '', style: str = None) -> None:
        text = text.rstrip()
        self.lines.append(text)
        if self.use_color and style in STYLES:
            color, attrs = STYLES[style]
            if color is not None:
                text = colored(text, color, attrs=attrs)
        try:
            print(text, file=self.stream)
        except UnicodeEncodeError:
            # terminal cannot display all characters - fall back to plain ascii
            print(text.encode('ascii', 'replace').decode('ascii'), file=self.stream)

    def blank(self) -> None:
        self.line()

    def rule(self, bold: bool = False) -> None:
        self.line((self.bold if bold else self.thin) * self.width, 'frame')

    def title(self, text: str) -> None:
        self.rule(bold=True)
        self.line(f" {text}", 'title')
        self.rule(bold=True)

    def section(self, text: str, width: int = None) -> None:
        self.blank()
        self.line(f" {text}", 'title')
        self.line(self.thin * (width or self.width), 'frame')

    def label(self, key: str, value: str, key_width: int = 14) -> None:
        self.line(f" {key + ':':<{key_width}} {value}", 'label')

    def hint(self, text: str) -> None:
        self.line(f" {text}", 'hint')

    def write_to_file(self, filename: str) -> None:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.lines) + '\n')


@dataclass
class Column:
    """One column of a report table."""
    title: str
    width: int
    align: str = '<'


class Table:
    """Renders aligned rows separated by a vertical line."""

    def __init__(self, printer: ReportPrinter, columns: list) -> None:
        self.printer = printer
        self.columns = columns

    @property
    def width(self) -> int:
        return sum(c.width for c in self.columns) + 3 * (len(self.columns) - 1)

    def print_header(self) -> None:
        self.printer.line(self._join([f"{c.title:{c.align}{c.width}}" for c in self.columns]), 'header')
        self.printer.line(self.printer.thin * self.width, 'frame')

    def print_row(self, values: list, style: str = None) -> None:
        self.printer.line(self._join([self._cell(c, v) for c, v in zip(self.columns, values)]), style)

    def _cell(self, column: Column, value) -> str:
        text = '-' if value is None else str(value)
        if len(text) > column.width:
            text = text[:column.width - 1] + self.printer.ellipsis
        return f"{text:{column.align}{column.width}}"

    def _join(self, cells: list) -> str:
        return f" {self.printer.vertical} ".join(cells)


class CoverStepType(Enum):
    UP = 'up'
    DOWN = 'down'
    STOP = 'stop'
    PAUSE = 'pause'

    @property
    def command(self) -> int:
        return {CoverStepType.UP: COVER_COMMAND_UP,
                CoverStepType.DOWN: COVER_COMMAND_DOWN,
                CoverStepType.STOP: COVER_COMMAND_STOP}[self]


STEP_TYPE_ALIASES = {
    'up': CoverStepType.UP, 'auf': CoverStepType.UP, 'open': CoverStepType.UP,
    'down': CoverStepType.DOWN, 'ab': CoverStepType.DOWN, 'close': CoverStepType.DOWN,
    'stop': CoverStepType.STOP, 'halt': CoverStepType.STOP,
    'pause': CoverStepType.PAUSE, 'wait': CoverStepType.PAUSE, 'warten': CoverStepType.PAUSE,
}


@dataclass
class CoverTestStep:
    """One entry of the test sequence: a movement command or a pause."""
    type: CoverStepType
    duration: float

    @classmethod
    def parse(cls, text: str) -> 'CoverTestStep':
        """Parses entries like 'up:20', 'down:12.5', 'pause:5' or 'stop'."""
        parts = [p.strip() for p in str(text).split(':')]
        name = parts[0].lower()
        if name not in STEP_TYPE_ALIASES:
            raise ValueError(f"Unknown movement command '{parts[0]}'. "
                             f"Supported: {', '.join(sorted(set(t.value for t in CoverStepType)))}")
        if len(parts) > 2:
            raise ValueError(f"Invalid movement command '{text}'. Expected 'COMMAND:SECONDS'. "
                             f"Separate the entries of the sequence by a comma, not by a colon.")
        step_type = STEP_TYPE_ALIASES[name]

        if len(parts) > 1 and parts[1] != '':
            duration = float(parts[1].replace(',', '.'))
        elif step_type == CoverStepType.STOP:
            duration = 0.0
        else:
            raise ValueError(f"Missing duration for '{text}'. Use e.g. '{name}:20' for 20 seconds.")

        if duration < 0:
            raise ValueError(f"Duration of '{text}' must not be negative.")

        return cls(step_type, duration)

    def __str__(self) -> str:
        return f"{self.type.value.upper()} {self.duration:.1f}s"


@dataclass
class Cover:
    """A cover under test:

    * actuator_id: the address the status telegrams of the actuator come from,
    * switch_ids:  the wall switches which are taught into that actuator. They
      are optional and only needed so that a pressed switch can be assigned to
      the cover it really operates instead of disturbing all covers of the test
      run,
    * sender_id:   the address the test sends its commands from. It has to be
      taught into the actuator as well."""
    actuator_id: str
    sender_id: str
    switch_ids: tuple = ()

    COVER_ID_FORMAT = "ACTUATOR_ID[:SWITCH_ID[+SWITCH_ID...]][:SENDER_ID]"

    @classmethod
    def parse(cls, text: str) -> 'Cover':
        """Parses 'ACTUATOR_ID', 'ACTUATOR_ID:SWITCH_ID' or
        'ACTUATOR_ID:SWITCH_ID:SENDER_ID', e.g. '00-00-00-05',
        '00-00-00-05:FE-D4-E9-47' or 'FF-AA-BB-01:FE-D4-E9-47:00-00-B0-05'.
        Several switches of one cover are separated by '+'. A cover without a
        taught-in switch and with an explicit sender is given as
        '00-00-00-05::00-00-B0-05'."""
        parts = [p.strip().upper() for p in str(text).split(':')]
        if not parts[0]:
            raise ValueError(f"Invalid cover id '{text}'. No actuator id given. Use '{cls.COVER_ID_FORMAT}'.")
        if len(parts) > 3:
            raise ValueError(f"Invalid cover id '{text}'. Use '{cls.COVER_ID_FORMAT}'.")

        actuator_id = cls._normalize(parts[0])
        sender_id = cls._normalize(parts[2]) if len(parts) == 3 and parts[2] \
            else cls._default_sender_id(actuator_id)
        switch_part = parts[1] if len(parts) > 1 else ''
        switch_ids = tuple(cls._normalize(s) for s in switch_part.split('+') if s.strip())

        # 'ACTUATOR_ID:SENDER_ID': the sender in the switch position describes a
        # cover which is operated without a taught-in wall switch
        if switch_ids == (sender_id,):
            switch_ids = ()
        elif sender_id in switch_ids:
            raise ValueError(f"Invalid cover id '{text}'. '{sender_id}' is the sender id of this cover, it "
                             f"cannot be a switch which is taught into the actuator. The second entry is the "
                             f"switch: '{cls.COVER_ID_FORMAT}'.")
        if actuator_id in switch_ids:
            raise ValueError(f"Invalid cover id '{text}'. '{actuator_id}' is the actuator itself, it cannot be "
                             f"its own switch. Use '{cls.COVER_ID_FORMAT}'.")
        return cls(actuator_id, sender_id, switch_ids)

    @classmethod
    def _normalize(cls, id: str) -> str:
        try:
            return b2s(AddressExpression.parse(id.strip())[0])
        except Exception:
            raise ValueError(f"'{id}' is not a valid EnOcean address. Expected format: 'FF-AA-BB-01'.")

    @classmethod
    def _default_sender_id(cls, actuator_id: str) -> str:
        """Bus actuators (00-00-00-XX) are addressed via the sender ids
        00-00-B0-XX which this application also uses for Home Assistant."""
        if actuator_id.startswith('00-00-00-'):
            return '00-00-B0-' + actuator_id[-2:]
        return actuator_id

    @property
    def sender_address(self) -> bytes:
        return AddressExpression.parse(self.sender_id)[0]

    def __str__(self) -> str:
        details = []
        if self.switch_ids:
            details.append(f"switch {'+'.join(self.switch_ids)}")
        if self.actuator_id != self.sender_id:
            details.append(f"sender {self.sender_id}")
        return f"{self.actuator_id} ({', '.join(details)})" if details else self.actuator_id


@dataclass
class TelegramEvent:
    """A single sent or received telegram with the time it happened."""
    time: float                     # seconds since test start
    outgoing: bool
    address: str
    telegram_type: str
    description: str = ''
    cover: Cover = None             # set when the telegram belongs to a cover under test
    switch_of: tuple = ()           # covers whose taught-in switch sent this telegram
    is_marker: bool = False         # press of a marker switch which is not taught into any actuator
    is_manual_end_position: bool = False   # first press of a double press of the marker switch
    is_marker_repetition: bool = False     # follow-up press which belongs to that double press
    rssi: int = None
    is_travel_report: bool = False  # actuator reported direction and travel time
    is_end_position: bool = False   # actuator reached its top/bottom end position
    is_movement_start: bool = False # actuator announced that it starts to move
    is_button_pressed: bool = False # a rocker switch was pressed
    button: str = ''                # which button of the rocker switch (AI, A0, BI, B0)
    is_echo: bool = False           # telegram sent by this test and echoed by the gateway
    reported_direction: int = None
    reported_travel_time: float = None
    esp2: str = ''                  # raw ESP2 telegram, only filled for verbose >= 2

    @property
    def source(self) -> str:
        return 'SENT' if self.outgoing else 'RCVD'

    @property
    def is_known_switch(self) -> bool:
        """True when the telegram comes from a switch which was declared as
        taught into one of the covers under test."""
        return len(self.switch_of) > 0

    @property
    def device_kind(self) -> str:
        if self.is_echo:
            return 'echo'
        if self.is_marker:
            return 'marker'
        if self.is_known_switch:
            return 'switch'
        return 'cover' if self.cover is not None else 'unknown'


@dataclass
class Movement:
    """One movement command sent to one cover and everything which followed."""
    run: int
    step_index: int
    step: CoverTestStep
    cover: Cover
    start_time: float
    end_time: float = None                  # end of the observation window
    stop_command_time: float = None         # time when the test sent a STOP command
    events: list = field(default_factory=list)

    @property
    def expected_direction(self) -> int:
        return self.step.type.command

    @property
    def cover_events(self) -> list:
        """Telegrams which were sent by the cover under test."""
        return [e for e in self.events if e.cover is not None and not e.outgoing]

    @property
    def first_reaction(self) -> TelegramEvent:
        """First telegram of the cover under test after the command was sent.
        Foreign telegrams are recorded in the same list (see interferences) but
        must not be counted as a reaction of the cover."""
        return next(iter(self.cover_events), None)

    @property
    def travel_report(self) -> TelegramEvent:
        return next((e for e in reversed(self.events) if e.is_travel_report), None)

    @property
    def end_position(self) -> TelegramEvent:
        return next((e for e in reversed(self.events) if e.is_end_position), None)

    @property
    def movement_end_time(self) -> float:
        """First point in time at which the movement is known to have ended:
        either the test sent a STOP or the actuator signalled the end."""
        candidates = [e.time for e in self.events if e.is_travel_report or e.is_end_position]
        if self.stop_command_time is not None:
            candidates.append(self.stop_command_time)
        return min(candidates) if candidates else None

    @property
    def interferences(self) -> list:
        """Telegrams of other devices which were received while the cover was
        moving. Marker switches are not taught into any actuator, so they
        cannot have influenced the movement and are not counted."""
        end = self.movement_end_time
        return [e for e in self.events
                if e.cover is None and not e.outgoing and not e.is_marker
                and (end is None or e.time <= end)]

    @property
    def markers(self) -> list:
        """Presses of a marker switch which happened during this movement. Every
        press is followed by a release telegram which is not a marker of its own."""
        end = self.movement_end_time
        return [e for e in self.events
                if e.is_marker and e.is_button_pressed and (end is None or e.time <= end)]

    @property
    def manual_end_position(self) -> TelegramEvent:
        """First double press of a marker switch: the moment somebody signalled
        that the cover has reached its end position."""
        return next((e for e in self.markers if e.is_manual_end_position), None)

    @property
    def manual_end_position_time(self) -> float:
        """Travel time until the end position was signalled manually. This is the
        time the cover really needed, even if the actuator kept on running."""
        marker = self.manual_end_position
        return None if marker is None else marker.time - self.start_time

    @property
    def first_interference(self) -> TelegramEvent:
        return next((e for e in self.interferences if e.is_button_pressed), None)

    @property
    def measured_travel_time(self) -> float:
        """Time from the movement command until the actuator signalled the end
        of the movement. None if the actuator did not report anything."""
        last = self.travel_report or self.end_position
        if last is None:
            return None
        return last.time - self.start_time

    @property
    def reported_travel_time(self) -> float:
        report = self.travel_report
        return None if report is None else report.reported_travel_time

    @property
    def effective_travel_time(self) -> float:
        """Travel time used for the statistics. The value reported by the
        actuator is more precise than our measurement and preferred."""
        reported = self.reported_travel_time
        return reported if reported is not None else self.measured_travel_time

    @property
    def travel_time_until_interference(self) -> float:
        interference = self.first_interference
        return None if interference is None else interference.time - self.start_time

    @property
    def movement_start(self) -> TelegramEvent:
        return next((e for e in self.events if e.is_movement_start), None)

    @property
    def reported_direction(self) -> int:
        """Direction the actuator really moved. Taken from the travel report if
        the actuator sends one, otherwise from its movement start telegram."""
        report = self.travel_report
        if report is not None:
            return report.reported_direction
        start = self.movement_start
        return None if start is None else start.reported_direction

    @property
    def reached_end_position(self) -> bool:
        return self.end_position is not None

    @property
    def was_interrupted(self) -> bool:
        return self.first_interference is not None

    @property
    def stopped_by(self) -> str:
        if self.was_interrupted:
            interference = self.first_interference
            kind = 'switch' if interference.is_known_switch else 'unknown'
            return f"{kind} {interference.address}"
        if self.first_reaction is None:
            return "no feedback"
        if self.stop_command_time is not None:
            return "STOP of test"
        if self.reached_end_position:
            return COVER_END_POSITIONS.get(self.end_position_state, 'end position').lower()
        if self.travel_report is not None:
            return "actuator runtime"
        return "no feedback"

    @property
    def end_position_state(self) -> int:
        event = self.end_position
        return None if event is None else event.reported_direction

    @property
    def direction_ok(self) -> bool:
        """True when the actuator reported the direction which was requested."""
        reported = self.reported_direction
        return reported is None or reported == self.expected_direction

    @property
    def problems(self) -> list:
        """Everything which did not happen as requested."""
        problems = []
        if self.first_reaction is None:
            problems.append('no reaction')
        if not self.direction_ok:
            problems.append('wrong direction')
        if self.was_interrupted:
            problems.append('interrupted')
        return problems

    @property
    def is_ok(self) -> bool:
        return not self.problems


class CoverTravelTester:
    """Drives covers with a configurable sequence and reports their behaviour."""

    def __init__(self, app_bus: AppBus, serial_port: str, device_type: str,
                 cover_ids: list, sequence: list,
                 message_delay: float = .1, command_mode: str = 'stop',
                 marker_switch_ids: list = None,
                 marker_double_press_time: float = DEFAULT_MARKER_DOUBLE_PRESS_TIME,
                 verbose: int = 0, serial_controller: SerialController = None,
                 printer: ReportPrinter = None) -> None:
        self._stop_flag = threading.Event()
        self._lock = threading.Lock()
        self._is_running = False

        self.app_bus = app_bus
        self.serial_port = serial_port
        self.device_type = self._resolve_device_type(device_type)
        self.message_delay = message_delay
        self.command_mode = command_mode
        # 0 = only the result, 1 = live telegram log, 2 = additionally the raw ESP2 data
        self.verbose = verbose
        self.out = printer if printer is not None else ReportPrinter()
        # time the gateway needs to become ready before the first command is sent
        self.gateway_init_delay = 1.0
        # time to wait at the end of the test for late telegrams. Bus actuators
        # behind an FAM14/FGW14 need up to ~2.5s until their travel time report
        # has passed the bus.
        self.settle_time = 3.0

        self.covers: list[Cover] = [Cover.parse(c) for c in cover_ids]
        self.sequence: list[CoverTestStep] = [CoverTestStep.parse(s) for s in sequence]

        if len(self.covers) == 0:
            raise ValueError("No cover ids given. Provide at least one cover id.")
        if len(self.sequence) == 0:
            raise ValueError("No movement sequence given. Provide e.g. 'up:30,pause:5,down:30,pause:5'.")

        self._covers_by_actuator_id = {c.actuator_id: c for c in self.covers}
        # telegrams which are sent by this test can be echoed back by the gateway.
        # They must not be counted as interference.
        self._covers_by_sender_id = {c.sender_id: c for c in self.covers
                                     if c.sender_id not in self._covers_by_actuator_id}
        # switches which are taught into the actuators. One switch can operate
        # several covers, so every switch id maps to a list of covers.
        self._covers_by_switch_id = {}
        for cover in self.covers:
            for switch_id in cover.switch_ids:
                self._covers_by_switch_id.setdefault(switch_id, []).append(cover)

        # switches which are NOT taught into an actuator. They do not move anything,
        # they are only used to mark a point in time during the test.
        self.marker_switch_ids = [Cover._normalize(s) for s in (marker_switch_ids or [])]
        self.marker_double_press_time = marker_double_press_time
        for marker_id in self.marker_switch_ids:
            if marker_id in self._covers_by_switch_id:
                raise ValueError(f"'{marker_id}' is given as marker switch and as taught-in switch of a cover. "
                                 f"A marker switch must not be taught into one of the actuators.")
            if marker_id in self._covers_by_actuator_id or marker_id in self._covers_by_sender_id:
                raise ValueError(f"'{marker_id}' is given as marker switch but it is the address of a cover "
                                 f"under test.")
        self._start_timestamp: float = None
        self._events: list[TelegramEvent] = []
        self._movements: list[Movement] = []
        # currently open movement per cover, used to assign incoming telegrams
        self._open_movements: dict = {}

        if serial_controller is None:
            self.gw_reg = GatewayRegistry(app_bus)
            serial_controller = SerialController(app_bus, self.gw_reg)
        self.serial_controller = serial_controller
        self._serial_callback_id = app_bus.add_event_handler(AppBusEventType.SERIAL_CALLBACK, self._serial_callback)

    @classmethod
    def _resolve_device_type(cls, device_type: str) -> str:
        """The serial controller expects the display name of a gateway
        ('FGW14(-USB) (ESP2)') while the command line accepts the short type
        name ('fgw14usb'). Unknown values are passed through unchanged."""
        if device_type in GATEWAY_DISPLAY_NAMES.values():
            return device_type
        try:
            return GATEWAY_DISPLAY_NAMES[GatewayDeviceType(device_type)]
        except (ValueError, KeyError):
            return device_type

    # =========================================================================
    # MARK: - test execution
    # =========================================================================

    def start_test(self, run_count: int = 1) -> list:
        """Runs the configured sequence run_count times and prints the report."""
        self.serial_controller.establish_serial_connection(self.serial_port, self.device_type)

        # wait for the gateway to be initialized
        time.sleep(self.gateway_init_delay)

        if not self.serial_controller.is_serial_connection_active():
            self._log(f"No connection to gateway {self.device_type} on {self.serial_port}. Test aborted.",
                      'red', 'ERROR')
            self.app_bus.remove_event_handler_by_id(self._serial_callback_id)
            return []

        self._stop_flag.clear()
        self._is_running = True
        self._start_timestamp = time.time()

        self._print_test_configuration(run_count)

        for run in range(1, run_count + 1):
            if self._stop_flag.is_set():
                break

            self.out.blank()
            self.out.line(f" RUN {run} of {run_count}", 'title')
            self.out.rule()

            for step_index, step in enumerate(self.sequence, start=1):
                if self._stop_flag.is_set():
                    break
                self._execute_step(run, step_index, step)

        # give late telegrams (e.g. travel time reports) a chance to arrive
        self._stop_flag.wait(self.settle_time)
        self._close_open_movements()
        self._classify_marker_presses()
        self._is_running = False
        self.app_bus.remove_event_handler_by_id(self._serial_callback_id)

        self.serial_controller.stop_serial_connection()

        self._print_report(run_count)

        return self._movements

    def stop_test(self) -> None:
        self._stop_flag.set()

    def _execute_step(self, run: int, step_index: int, step: CoverTestStep) -> None:
        self.out.blank()
        self.out.line(f" [{self._now():7.2f}s] Step {step_index}/{len(self.sequence)}: {step}", 'header')

        if step.type == CoverStepType.PAUSE:
            self._stop_flag.wait(step.duration)
            return

        # STOP terminates the running movements, UP/DOWN starts new ones
        if step.type == CoverStepType.STOP:
            self._send_stop()
            self._stop_flag.wait(step.duration)
            return

        movements = []
        travel_time = self._command_travel_time(step)
        for cover in self.covers:
            self._delay_between_commands(is_first=not movements)

            # register the movement before sending so that a fast reply of the
            # actuator is not assigned to the previous movement
            with self._lock:
                movement = Movement(run=run, step_index=step_index, step=step, cover=cover,
                                    start_time=self._now())
                # a new command ends the observation window of the previous movement
                self._close_movement(cover, movement.start_time)
                self._open_movements[cover.actuator_id] = movement
                self._movements.append(movement)
                movements.append(movement)

            self._send_cover_command(cover, step.type.command, travel_time)

        self._stop_flag.wait(step.duration)

        # when the command telegram did not carry a travel time the actuator moves
        # for its whole runtime and the test has to terminate the movement itself.
        # An explicitly configured STOP step does that already.
        next_step = self.sequence[step_index] if step_index < len(self.sequence) else None
        if travel_time == 0 and (next_step is None or next_step.type != CoverStepType.STOP):
            self._send_stop(only_still_moving=True)

        self._print_step_summary(movements)

    def _command_travel_time(self, step: CoverTestStep) -> float:
        """Travel time which is put into the command telegram. 0 means that the
        actuator uses its own configured runtime."""
        if self.command_mode != 'timed':
            return 0.0
        if step.duration > MAX_COMMAND_TRAVEL_TIME:
            self.out.line(f"           {step.duration:.1f}s cannot be sent within a command telegram "
                          f"(max. {MAX_COMMAND_TRAVEL_TIME}s). Sending full runtime and STOP instead.", 'warn')
            return 0.0
        return step.duration

    def _send_cover_command(self, cover: Cover, command: int, travel_time: float) -> None:
        eep = H5_3F_7F(time=int(round(travel_time * 10)), command=command, learn_button=1)
        msg = eep.encode_message(cover.sender_address)
        self.serial_controller.send_message(msg)

        command_name = {COVER_COMMAND_UP: 'UP', COVER_COMMAND_DOWN: 'DOWN', COVER_COMMAND_STOP: 'STOP'}[command]
        time_info = 'runtime of actuator' if travel_time == 0 else f"{travel_time:.1f}s"
        self._add_event(TelegramEvent(time=self._now(), outgoing=True, address=cover.sender_id,
                                      telegram_type=type(msg).__name__, cover=cover,
                                      esp2=self._serialized(msg),
                                      description=f"command {command_name} to cover {cover.actuator_id}, travel time: {time_info}"))

    def _send_stop(self, only_still_moving: bool = False) -> None:
        sent_commands = 0
        for cover in self.covers:
            with self._lock:
                movement = self._open_movements.get(cover.actuator_id, None)
                already_stopped = movement is None or movement.travel_report is not None \
                    or movement.end_position is not None

            if only_still_moving and already_stopped:
                if self.verbose > 0:
                    self.out.hint(f"          Cover {cover.actuator_id} already signalled the end of the "
                                  f"movement. No STOP command needed.")
                continue

            self._delay_between_commands(is_first=sent_commands == 0)

            with self._lock:
                if movement is not None and movement.stop_command_time is None:
                    movement.stop_command_time = self._now()

            self._send_cover_command(cover, COVER_COMMAND_STOP, 0)
            sent_commands += 1

    def _delay_between_commands(self, is_first: bool) -> None:
        """Waits self.message_delay before the next command telegram is sent.
        Nothing is waited before the first command of a step so that the delay
        really only happens between two telegrams."""
        if not is_first and self.message_delay > 0:
            self._stop_flag.wait(self.message_delay)

    def _close_movement(self, cover: Cover, end_time: float) -> None:
        movement = self._open_movements.pop(cover.actuator_id, None)
        if movement is not None and movement.end_time is None:
            movement.end_time = end_time

    def _classify_marker_presses(self) -> None:
        """Groups the presses of every marker switch. Presses which follow each
        other within marker_double_press_time belong together: a single press is
        a time marker, two (or more) presses signal that the cover has reached
        its end position. The first press of such a group is the moment which
        counts - that is when the observer reacted."""
        # grouped per button: pressing 'up' and then 'down' are two actions,
        # only the same button twice in a row is a double press
        presses_by_button = {}
        for event in self._events:
            if event.is_marker and event.is_button_pressed:
                presses_by_button.setdefault((event.address, event.button), []).append(event)

        for presses in presses_by_button.values():
            group = []
            for press in presses:
                if group and press.time - group[-1].time > self.marker_double_press_time:
                    self._mark_press_group(group)
                    group = []
                group.append(press)
            self._mark_press_group(group)

    def _mark_press_group(self, group: list) -> None:
        if len(group) < 2:
            return
        # the first press of the group is when the observer reacted
        group[0].is_manual_end_position = True
        group[0].description += f" - pressed {len(group)}x: END POSITION REACHED"
        for press in group[1:]:
            press.is_marker_repetition = True
            press.description += " - repetition of the double press"

    def _close_open_movements(self) -> None:
        with self._lock:
            for cover in list(self.covers):
                self._close_movement(cover, self._now())

    def _now(self) -> float:
        return 0.0 if self._start_timestamp is None else time.time() - self._start_timestamp

    # =========================================================================
    # MARK: - telegram recording
    # =========================================================================

    def _serial_callback(self, data: dict) -> None:
        if not self._is_running or 'msg' not in data:
            return

        telegram = data['msg']
        if not self._is_relevant(telegram):
            return

        try:
            event = self._create_event(telegram, data.get('rssi', None))
        except Exception as e:
            self._log(f"Could not interpret telegram {telegram}: {e}", 'red', 'ERROR')
            return

        self._add_event(event)

    def _is_relevant(self, telegram: ESP2Message) -> bool:
        if type(telegram) in [EltakoPoll, EltakoTimeout]:
            return False
        if not hasattr(telegram, 'address') or isinstance(telegram.address, int):
            return False
        # empty telegrams are generated when sending telegrams with a FAM-USB
        if int.from_bytes(telegram.address, 'big') == 0:
            return False
        return True

    def _create_event(self, telegram: ESP2Message, rssi) -> TelegramEvent:
        address = b2s(telegram.address)
        cover = self._covers_by_actuator_id.get(address, None)
        echoed_cover = self._covers_by_sender_id.get(address, None) if cover is None else None
        is_other_device = cover is None and echoed_cover is None
        switch_of = tuple(self._covers_by_switch_id.get(address, ())) if is_other_device else ()
        is_marker = is_other_device and address in self.marker_switch_ids
        event = TelegramEvent(time=self._now(), outgoing=False, address=address,
                              telegram_type=type(telegram).__name__,
                              cover=cover or echoed_cover, switch_of=switch_of, is_marker=is_marker, rssi=rssi,
                              is_echo=echoed_cover is not None,
                              esp2=self._serialized(telegram))

        if event.is_echo:
            event.description = f"echo of own command for cover {echoed_cover.actuator_id}"
        elif cover is not None:
            self._describe_cover_telegram(telegram, event)
        else:
            self._describe_switch_telegram(telegram, event)

        return event

    def _describe_cover_telegram(self, telegram: ESP2Message, event: TelegramEvent) -> None:
        """Interprets a status telegram of a cover actuator (EEP G5-3F-7F)."""
        try:
            status = G5_3F_7F.decode_message(telegram)
        except Exception:
            event.description = f"status of cover, data: {b2s(telegram.data)}"
            return

        if status.time is not None:
            # 4BS telegram: the actuator reports how long it moved in which direction
            event.is_travel_report = True
            event.reported_travel_time = status.time / 10.0
            event.reported_direction = status.direction
            event.description = (f"cover reports movement {self._direction_name(status.direction)} "
                                 f"for {event.reported_travel_time:.1f}s")
        else:
            # RPS telegram: start of a movement or end position of the cover
            event.reported_direction = status.state
            if status.state in COVER_END_POSITIONS:
                event.is_end_position = True
                event.description = f"cover reached {COVER_END_POSITIONS[status.state]}"
            elif status.state in COVER_MOVEMENT_STARTED:
                event.is_movement_start = True
                event.reported_direction = COVER_MOVEMENT_STARTED[status.state]
                event.description = (f"cover started to move "
                                     f"{self._direction_name(event.reported_direction)}")
            else:
                event.description = f"cover status 0x{status.state:02X}"

    def _describe_switch_telegram(self, telegram: ESP2Message, event: TelegramEvent) -> None:
        """Interprets a telegram which does not come from a cover under test.
        Rocker switch telegrams are the typical interference of such a test."""
        if telegram.org == 0x05:
            try:
                switch = F6_02_01.decode_message(telegram)
                button = ROCKER_BUTTONS.get(switch.rocker_first_action, f"0x{switch.rocker_first_action:02X}")
                event.is_button_pressed = switch.energy_bow == 1
                if event.is_button_pressed:
                    event.button = button
                action = 'pressed' if event.is_button_pressed else 'released'
                if event.is_marker:
                    event.description = (f"marker switch {action}"
                                         f"{f' (button {button})' if event.is_button_pressed else ''}")
                elif event.is_known_switch:
                    covers = ', '.join(c.actuator_id for c in event.switch_of)
                    event.description = (f"switch of cover {covers} {action}"
                                         f"{f' (button {button})' if event.is_button_pressed else ''}")
                else:
                    event.description = (f"unknown switch {action}"
                                         f"{f' (button {button})' if event.is_button_pressed else ''}")
                return
            except Exception:
                pass

        data = telegram.data if hasattr(telegram, 'data') else b''
        event.description = f"telegram of an unknown device, data: {b2s(data)}"

    def _add_event(self, event: TelegramEvent) -> None:
        with self._lock:
            self._events.append(event)
            # assign the telegram to the open movements it belongs to
            if event.outgoing or event.is_echo:
                pass
            elif event.cover is not None:
                movement = self._open_movements.get(event.cover.actuator_id, None)
                if movement is not None:
                    movement.events.append(event)
            elif event.is_known_switch:
                # a taught-in switch only disturbs the covers it operates
                for cover in event.switch_of:
                    movement = self._open_movements.get(cover.actuator_id, None)
                    if movement is not None:
                        movement.events.append(event)
            elif event.is_marker:
                # a marker refers to whatever is moving at that moment
                for movement in self._open_movements.values():
                    movement.events.append(event)
            else:
                # the telegram cannot be assigned, so every running movement may be affected
                for movement in self._open_movements.values():
                    movement.events.append(event)

        if self.verbose > 0:
            self.out.line('  ' + self._format_event(event), self._event_style(event))

    def _signal_info(self, event: TelegramEvent) -> str:
        return f", signal: {format_rssi(event.rssi)}" if event.rssi is not None else ''

    def _serialized(self, telegram) -> str:
        """Raw ESP2 telegram as hex, only collected for verbose >= 2."""
        if self.verbose < 2:
            return ''
        try:
            return telegram.serialize().hex()
        except Exception:
            return ''

    def _direction_name(self, direction: int) -> str:
        return {COVER_COMMAND_UP: 'UP', COVER_COMMAND_DOWN: 'DOWN',
                COVER_COMMAND_STOP: 'STOP'}.get(direction, f"0x{direction:02X}")

    # =========================================================================
    # MARK: - report
    # =========================================================================

    def _log(self, msg: str, color: str = 'grey', log_level: str = 'INFO') -> None:
        """Errors and warnings go to the application log (and the log file).
        Everything else is printed as report, see self.out."""
        self.app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': msg, 'log-level': log_level, 'color': color})

    def _print_test_configuration(self, run_count: int) -> None:
        self.out.title("COVER TRAVEL TIME TEST")
        self.out.label("Gateway", f"{self.device_type} on {self.serial_port}")
        self.out.label("Covers", ', '.join(str(c) for c in self.covers))
        self.out.label("Sequence", f" {self.out.arrow} ".join(str(s) for s in self.sequence))
        self.out.label("Runs", str(run_count))
        self.out.label("Command mode", f"{self.command_mode} - "
                       + ('travel time is part of the command telegram' if self.command_mode == 'timed'
                          else 'movement is terminated by a STOP command'))
        if self.marker_switch_ids:
            self.out.label("Marker switch", f"{', '.join(self.marker_switch_ids)} - press it twice within "
                                            f"{self.marker_double_press_time}s to signal an end position")
        self.out.label("Message delay", f"{self.message_delay}s between two command telegrams"
                       + (' (no delay)' if self.message_delay == 0 else ''))
        self.out.label("Duration", f"about {self._estimated_duration(run_count):.0f}s")
        self.out.blank()
        self.out.hint("You can operate the covers with their wall switch during the test. Such interferences are "
                      "logged and the travel time until the intervention is reported.")
        if self.verbose == 0:
            self.out.hint("Use -v to see every telegram, -vv to additionally see the raw ESP2 data.")

    def _estimated_duration(self, run_count: int) -> float:
        # every step sends one command per cover, the delay happens in between
        delay_per_step = max(len(self.covers) - 1, 0) * self.message_delay
        per_run = sum(s.duration for s in self.sequence) + len(self.sequence) * delay_per_step
        return per_run * run_count + self.gateway_init_delay + self.settle_time

    def _print_step_summary(self, movements: list) -> None:
        """Compact result of one movement step which is printed while the test runs."""
        if not movements:
            return
        reacted = [m for m in movements if m.first_reaction is not None]
        times = [m.effective_travel_time for m in movements if m.effective_travel_time is not None]
        problems = sorted({p for m in movements for p in m.problems})

        info = f"{len(reacted)}/{len(movements)} covers reacted"
        if times:
            info += f", travel time: {', '.join(f'{t:.1f}s' for t in times)}"
        if problems:
            info += f" - {', '.join(problems)}"
        self.out.line(f"           {self.out.arrow} {info}", 'warn' if problems else 'ok')

    # =========================================================================
    # MARK: - report
    # =========================================================================

    def _print_report(self, run_count: int) -> None:
        self.out.blank()
        self.out.title("TEST RESULT")

        self._print_movement_table()
        self._print_manual_end_positions()
        recommendations = self._print_travel_time_statistics()
        self._print_configuration_hints(recommendations)
        self._print_interference_report()
        if self.verbose > 0:
            self._print_telegram_log()
        self._print_verdict()

    def _print_movement_table(self) -> None:
        table = Table(self.out, [
            Column('run', 3, '>'), Column('step', 4, '>'), Column('cover', 11), Column('command', 10),
            Column('react', 6, '>'), Column('measured', 8, '>'), Column('reported', 8, '>'),
            Column('dir', 4), Column('end', 3), Column('stopped by', 20), Column('result', 24),
        ])
        self.out.section("COMMANDS AND REACTION OF THE COVERS", table.width)
        table.print_header()

        for movement in self._movements:
            reaction = movement.first_reaction
            measured = movement.measured_travel_time
            reported = movement.reported_travel_time
            direction = movement.reported_direction
            problems = movement.problems

            table.print_row([
                movement.run,
                movement.step_index,
                movement.cover.actuator_id,
                f"{movement.step.type.value.upper()} {movement.step.duration:g}s",
                f"{reaction.time - movement.start_time:.2f}s" if reaction else None,
                f"{measured:.2f}s" if measured is not None else None,
                f"{reported:.1f}s" if reported is not None else None,
                self._direction_name(direction) if direction is not None else None,
                self._end_position_short(movement),
                movement.stopped_by,
                'OK' if not problems else ', '.join(problems),
            ], 'ok' if not problems else 'warn')

        self.out.blank()
        self.out.hint("react    = time between the sent command and the first telegram of the cover")
        self.out.hint("measured = time between the sent command and the telegram which ended the movement")
        self.out.hint("reported = travel time the actuator reported itself - not every actuator sends it,\n            then 'measured' is the relevant value")
        self.out.hint("end      = TOP / BOT if the cover ran into its top or bottom end position")

    def _print_manual_end_positions(self) -> None:
        """Everything which was marked with the marker switch during the test."""
        if not self.marker_switch_ids:
            return

        marked = [m for m in self._movements if m.markers]
        table = Table(self.out, [
            Column('run', 3, '>'), Column('step', 4, '>'), Column('cover', 11), Column('command', 9),
            Column('no', 3, '>'), Column('marker', 11), Column('button', 6), Column('at', 8, '>'),
            Column('travelled', 9, '>'), Column('travel', 7, '>'), Column('difference', 9, '>'),
            Column('kind', 20),
        ])
        self.out.section("MARKER SWITCH - MANUALLY MARKED POINTS IN TIME", table.width)

        if not marked:
            self.out.line(f" The marker switch ({', '.join(self.marker_switch_ids)}) was not pressed while a "
                          f"cover was moving.", 'hint')
            return

        table.print_header()
        for movement in marked:
            # not every actuator sends a travel report, then the measured time is used
            total = movement.effective_travel_time
            # the markers are numbered per movement so that they can be referred to
            for number, marker in enumerate(movement.markers, start=1):
                travelled = marker.time - movement.start_time
                difference = None if total is None else total - travelled
                table.print_row([
                    movement.run,
                    movement.step_index,
                    movement.cover.actuator_id,
                    f"{movement.step.type.value.upper()} {movement.step.duration:g}s",
                    number,
                    marker.address,
                    marker.button or None,
                    f"{marker.time:.2f}s",
                    f"{travelled:.2f}s",
                    f"{total:.1f}s" if total is not None else None,
                    f"{difference:+.2f}s" if difference is not None else None,
                    self._marker_kind(marker),
                ], 'ok' if marker.is_manual_end_position else 'received')

        self.out.blank()
        self.out.hint("no         = number of the marker within its movement, counted from the movement command")
        self.out.hint("button     = button of the rocker switch which was pressed (AI, A0, BI, B0). Two presses "
                      "are only\n            a double press when it is the same button")
        self.out.hint("travelled  = how long the cover had been moving when the marker switch was pressed")
        self.out.hint("travel     = whole travel time of that movement (reported by the actuator, otherwise measured)")
        self.out.hint("difference = how much longer the actuator kept on running after the marker")
        self.out.hint("Press the marker switch twice in a row to signal that the cover has reached its end "
                      "position. A single press only records the point in time.")

    def _marker_kind(self, marker: TelegramEvent) -> str:
        if marker.is_manual_end_position:
            return 'END POSITION REACHED'
        return 'repetition' if marker.is_marker_repetition else 'time marker'

    def _end_position_short(self, movement: Movement) -> str:
        if not movement.reached_end_position:
            return None
        return {0x70: 'TOP', 0x50: 'BOT'}.get(movement.end_position_state, 'yes')

    def _print_travel_time_statistics(self) -> dict:
        columns = [
            Column('cover', 11), Column('direction', 9), Column('moves', 5, '>'),
            Column('min', 8, '>'), Column('avg', 8, '>'), Column('max', 8, '>'),
            Column('complete travel', 15, '>'), Column('interrupted', 11, '>'),
        ]
        if self.marker_switch_ids:
            columns.append(Column('manual end', 10, '>'))
        table = Table(self.out, columns)
        self.out.section("TRAVEL TIMES PER COVER AND DIRECTION", table.width)
        table.print_header()

        recommendations = {}
        for cover in self.covers:
            for step_type in [CoverStepType.UP, CoverStepType.DOWN]:
                movements = [m for m in self._movements
                             if m.cover.actuator_id == cover.actuator_id and m.step.type == step_type]
                if not movements:
                    continue

                times = [m.effective_travel_time for m in movements if m.effective_travel_time is not None]
                complete = [m.effective_travel_time for m in movements
                            if m.reached_end_position and not m.was_interrupted
                            and m.effective_travel_time is not None]
                manual = [m.manual_end_position_time for m in movements
                          if m.manual_end_position_time is not None]
                interrupted = len([m for m in movements if m.was_interrupted])

                if complete or manual:
                    entry = recommendations.setdefault(cover.actuator_id, {}).setdefault(step_type, {})
                    if complete:
                        entry['reported'] = max(complete)
                    if manual:
                        entry['manual'] = max(manual)

                row = [
                    cover.actuator_id,
                    step_type.value.upper(),
                    len(movements),
                    f"{min(times):.2f}s" if times else None,
                    f"{sum(times) / len(times):.2f}s" if times else None,
                    f"{max(times):.2f}s" if times else None,
                    f"{max(complete):.1f}s" if complete else None,
                    interrupted if interrupted else '-',
                ]
                if self.marker_switch_ids:
                    row.append(f"{max(manual):.2f}s" if manual else None)
                table.print_row(row, 'warn' if interrupted else 'received')

        self.out.blank()
        self.out.hint("complete travel = longest travel time of a movement which reached an end position "
                      "without interference")
        if self.marker_switch_ids:
            self.out.hint("manual end      = longest travel time until the end position was signalled with the "
                          "marker switch")
        return recommendations

    def _print_configuration_hints(self, recommendations: dict) -> None:
        self.out.section("HINTS FOR CONFIGURING THE RUNTIME OF THE ACTUATOR (FSB)")

        if not recommendations:
            if self._movements and not any(m.first_reaction is not None for m in self._movements):
                self._print_unknown_cover_hint()
            else:
                self.out.line(" No cover reached an end position without interference, so the complete travel time is "
                              "unknown.", 'warn')
                self.out.hint("Increase the duration of the movement steps and repeat the test.")
            return

        for actuator_id, values in recommendations.items():
            # a manually signalled end position is the time the cover really needed
            best = {step_type: entry.get('manual', entry.get('reported'))
                    for step_type, entry in values.items()}
            up = best.get(CoverStepType.UP, None)
            down = best.get(CoverStepType.DOWN, None)
            known = [v for v in [up, down] if v is not None]
            self.out.line(f" Cover {actuator_id}: up {f'{up:.1f}s' if up else 'unknown'}, "
                          f"down {f'{down:.1f}s' if down else 'unknown'} "
                          f"{self.out.arrow} configure a runtime of at least {max(known):.1f}s", 'ok')

            manual = {t: e['manual'] for t, e in values.items() if 'manual' in e}
            if manual:
                without_marker = ', '.join(f"{t.value} {e['reported']:.1f}s"
                                           for t, e in values.items() if 'reported' in e)
                self.out.hint(f"  based on the end position which was signalled with the marker switch "
                              f"({', '.join(f'{t.value} {v:.1f}s' for t, v in manual.items())})"
                              f"{f'. Without the marker the test would use: {without_marker}' if without_marker else ''}")
            if up is not None and down is not None:
                difference = abs(up - down)
                self.out.hint(f"  difference between up and down: {difference:.1f}s. The actuator only knows one "
                              f"runtime, so the faster direction stands still for {difference:.1f}s before the "
                              f"configured runtime has elapsed.")

        self.out.hint("For venetian blinds measure the turning of the slats separately with short movement steps "
                      "(e.g. 'down:2').")

    def _print_unknown_cover_hint(self) -> None:
        """No cover answered at all. Most of the time the given actuator ids do
        not match the addresses of the telegrams which the actuators send."""
        self.out.line(" No telegram of a cover under test was received, so no travel time could be measured.",
                      'error')
        self.out.hint("The actuator id is compared with the sender address of the received telegrams. Bus actuators "
                      "behind an FAM14/FGW14 send with their local bus address (e.g. 00-00-00-1F) and not with "
                      "their external id (base id of the gateway + bus address).")

        addresses = sorted({e.address for e in self._events if e.cover is None and not e.outgoing})
        if addresses:
            self.out.hint(f"Addresses which sent telegrams during the test: {', '.join(addresses)}")
        self.out.hint("Use 'ACTUATOR_ID:SENDER_ID' when the sender id which is taught into the actuator differs from "
                      "the address of the actuator, e.g. '00-00-00-1F:EF-00-00-1F'.")

    def _print_interference_report(self) -> None:
        foreign_events = [e for e in self._events if e.cover is None and not e.outgoing and not e.is_marker]
        interfered = [m for m in self._movements if m.first_interference is not None]

        self.out.section(f"INTERFERENCES - SWITCHES AND UNKNOWN TELEGRAMS ({len(foreign_events)})")

        if not foreign_events:
            self.out.line(" Neither a switch nor an unknown telegram was received. The test was not disturbed.",
                          'ok')
            return

        for event in foreign_events:
            during = ' (during a movement)' if any(event is m.first_interference for m in interfered) else ''
            self.out.line(f" {event.time:8.2f}s  {event.address}  {event.device_kind:<8} {event.description}"
                          f"{self._signal_info(event)}{during}", self._event_style(event))

        if not interfered:
            self.out.blank()
            self.out.line(" None of them happened while a cover under test was moving.", 'ok')
        else:
            self.out.blank()
            self.out.line(" Movements which were disturbed:", 'warn')
            for movement in interfered:
                travel = movement.travel_time_until_interference
                reported = movement.reported_travel_time
                interference = movement.first_interference
                source = 'switch' if interference.is_known_switch else 'unknown device'
                self.out.line(f"   run {movement.run} step {movement.step_index} cover "
                              f"{movement.cover.actuator_id} ({movement.step}): {source} "
                              f"{interference.address} intervened after {travel:.2f}s {self.out.arrow} travel "
                              f"time until the intervention: {travel:.2f}s"
                              f"{f', actuator reported {reported:.1f}s' if reported is not None else ''}", 'warn')

            self.out.blank()
            self.out.hint("'interrupted' means that a switch telegram arrived while the cover was still moving. "
                          "The travel time up to that moment is valid, but such a movement is not used for the "
                          "runtime recommendation.")

        unknown = [e for e in foreign_events if not e.is_known_switch and e.is_button_pressed]
        if unknown:
            self.out.hint(f"{len(unknown)} telegram(s) came from a device which is not part of the test "
                          f"({', '.join(sorted({e.address for e in unknown}))}). They are treated as a possible "
                          f"interference of every running movement. If it is a switch of one of the covers, add "
                          f"it to its cover id. If it is another cover, add that cover to the cover ids - its "
                          f"status telegrams look like a switch press as well.")

    def _print_telegram_log(self) -> None:
        self.out.section(f"TELEGRAM LOG ({len(self._events)} telegrams)")
        self.out.line(f" {'time':>9}  {'':<4} {'telegram':<18} {'address':<12} {'device':<8} description", 'header')
        self.out.rule()
        for event in self._events:
            self.out.line(' ' + self._format_event(event), self._event_style(event))

    def _print_verdict(self) -> None:
        self.out.blank()
        self.out.rule(bold=True)
        total = len(self._movements)
        ok = len([m for m in self._movements if m.is_ok])
        if total == 0:
            self.out.line(" RESULT: no movement command was executed.", 'warn')
        elif ok == total:
            self.out.line(f" RESULT: all {total} movements behaved as requested.", 'ok')
        else:
            counts = {}
            for movement in self._movements:
                for problem in movement.problems:
                    counts[problem] = counts.get(problem, 0) + 1
            details = ', '.join(f"{count}x {problem}" for problem, count in counts.items())
            style = 'error' if any(m.first_reaction is None for m in self._movements) else 'warn'
            self.out.line(f" RESULT: {ok} of {total} movements behaved as requested ({details}).", style)
        self.out.rule(bold=True)

    # =========================================================================
    # MARK: - telegram formatting
    # =========================================================================

    def _format_event(self, event: TelegramEvent) -> str:
        esp2 = f", ESP2: {event.esp2}" if event.esp2 else ''
        return (f"{event.time:>8.2f}s  {event.source:<4} {event.telegram_type:<18} {event.address:<12} "
                f"{event.device_kind:<8} {event.description}{self._signal_info(event)}{esp2}")

    def _event_style(self, event: TelegramEvent) -> str:
        if event.outgoing:
            return 'sent'
        if event.is_marker:
            return 'ok' if event.is_manual_end_position else 'received'
        if event.cover is None:
            return 'warn' if event.is_known_switch else 'foreign'
        return 'received'

    # =========================================================================
    # MARK: - report files
    # =========================================================================

    def write_report_to_file(self, filename: str) -> None:
        """Writes the printed report as plain text."""
        self.out.write_to_file(filename)
        self._log(f"Report was written to {filename}.", 'green')

    def write_telegrams_to_csv(self, filename: str) -> None:
        """Writes the recorded telegrams as CSV so that they can be analysed
        with a spreadsheet application."""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("time [s];source;telegram;address;device;description;signal [dBm];ESP2\n")
            for e in self._events:
                f.write(f"{e.time:.3f};{e.source};{e.telegram_type};{e.address};{e.device_kind};"
                        f"{e.description};{e.rssi if e.rssi is not None else ''};{e.esp2}\n")
        self._log(f"Telegram log was written to {filename}.", 'green')
