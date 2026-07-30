import sys
import os
import argparse
import asyncio
from typing import Final
from logging.handlers import RotatingFileHandler
import time
import threading

import warnings
from termcolor import colored
from bs4 import XMLParsedAsHTMLWarning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

PACKAGE_NAME: Final = 'eo_man'

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# Started via 'python -m eo_man' the module already belongs to its package and
# nothing has to be done. Started as a directory or a file ('python eo_man',
# 'python eo_man/__main__.py') it does not, so the relative imports below would
# fail. In that case make the package importable and join it manually.
if not __package__:
    sys.path.append(os.path.dirname(PROJECT_DIR))
    __import__(PACKAGE_NAME)
    __package__ = PACKAGE_NAME
    # __spec__ still describes a plain script. Leaving it in place would make
    # every relative import warn 'DeprecationWarning: __package__ != __spec__.parent'.
    __spec__ = None

from eo_man import load_dep_homeassistant, LOGGER
load_dep_homeassistant()

from .data.app_info import ApplicationInfo
from .data.data_manager import DataManager
from .data.pct14_data_manager import PCT14DataManager
from .data.ha_config_generator import HomeAssistantConfigurationGenerator
from .data.const import GatewayDeviceType
from .controller.app_bus import AppBus, AppBusEventType
from .controller.enocean_logger import EnOceanLogger
from .controller.serial_controller import SerialController
from .controller.gateway_registry import GatewayRegistry
from .controller.bus_burst_tester import BusBurstTester
from .controller.cover_travel_tester import CoverTravelTester

import logging

cli_commands = ["generate_ha_config", "enocean_logger", "burst_test", "cover_test"]

ASCII_ART_HEADLINE = (
    " _____     _____                    ____          _            _____                         \n"
    "|   __|___|     |___ ___ ___ ___   |    \\ ___ _ _|_|___ ___   |     |___ ___ ___ ___ ___ ___ \n"
    "|   __|   |  |  |  _| -_| .'|   |  |  |  | -_| | | |  _| -_|  | | | | .'|   | .'| . | -_|  _|\n"
    "|_____|_|_|_____|___|___|__,|_|_|  |____/|___|\\_/|_|___|___|  |_|_|_|__,|_|_|__,|_  |___|_|\n"
    "                                                                                |___|        \n")

# Shades of the headline from its lit top edge down to the shadow at the bottom.
# A drop shadow (an offset copy behind the letters) does not work with this font
# because its glyphs are hollow - the offset copy would land inside the letters.
# Shading the rows instead makes it look lit from above.
HEADLINE_SHADES: Final = [
    ('light_cyan', ['bold']),
    ('light_cyan', None),
    ('cyan', None),
    ('blue', None),
    ('dark_grey', None),
]


def ascii_art_headline(use_color: bool = None, stream=None) -> str:
    """Returns the headline shaded from a bright top edge down to a dark bottom.
    Without color support the plain headline is returned, so that log files and
    piped output stay free of escape sequences."""
    stream = stream if stream is not None else sys.stdout
    if use_color is None:
        try:
            use_color = stream.isatty()
        except Exception:
            use_color = False
    if not use_color:
        return ASCII_ART_HEADLINE

    lines = ASCII_ART_HEADLINE.split('\n')
    shaded = []
    for index, line in enumerate(lines):
        if not line.strip():
            shaded.append(line)
            continue
        color, attrs = HEADLINE_SHADES[min(index, len(HEADLINE_SHADES) - 1)]
        shaded.append(colored(line.rstrip(), color, attrs=attrs))
    return '\n'.join(shaded)


def _description(use_color: bool = None) -> str:
    return (
        ascii_art_headline(use_color) + "\n"
        "EnOcean Device Manager manages your EnOcean devices and generates Home Assistant configurations.\n"
        "  Documentation: https://github.com/grimmpp/enocean-device-manager\n"
        "  Home Assistant Eltako Integration: https://github.com/grimmpp/home-assistant-eltako\n"
        "\n"
        "Without --command the graphical user interface is started. With --command the selected command line\n"
        "tool is executed instead. Only the arguments of the chosen command are relevant, see the groups below."
    )

EPILOG = (
    "commands:\n"
    "  (none)               Start the graphical user interface.\n"
    "  generate_ha_config   Generate the Home Assistant configuration out of a stored application config.\n"
    "  enocean_logger       Live telegram monitor: print every telegram until the process is stopped.\n"
    "  burst_test           Send a series of telegrams to the bus and check that all of them arrive.\n"
    "  cover_test           Drive covers (FSB14, FSB61, ...) and report their travel times.\n"
    "\n"
    "examples:\n"
    "  Start the user interface with the demo data:\n"
    "    python -m eo_man -c demo.eodm\n"
    "\n"
    "  Generate the Home Assistant configuration:\n"
    "    python -m eo_man -C generate_ha_config -c my_config.eodm -ha ha_config.yaml\n"
    "\n"
    "  Watch all telegrams and write them into a file:\n"
    "    python -m eo_man -C enocean_logger -sp COM3 -dt fgw14usb -lf telegrams.log\n"
    "\n"
    "  Check the bus (writes via the first, reads via the second gateway):\n"
    "    python -m eo_man -C burst_test -sp COM3 -dt fgw14usb -sp2 COM7 -dt2 fam14 -trc 10\n"
    "\n"
    "  Measure the travel times of two covers (with the switch which is taught into each of them):\n"
    "    python -m eo_man -C cover_test -sp COM3 -dt fgw14usb \\\n"
    "                     -cid 00-00-00-05:FE-D4-E9-47,00-00-00-07:FE-D4-E9-48 \\\n"
    "                     -cseq up:60,pause:5,down:60,pause:5\n"
    "\n"
    "More examples and details for every command: https://github.com/grimmpp/enocean-device-manager/tree/main/docs\n"
)


def cli_argument():
    parser = argparse.ArgumentParser(
        prog='python -m eo_man',
        description=_description(),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    device_type_choices = [str(d.value).lower() for d in GatewayDeviceType]

    general = parser.add_argument_group('general')
    general.add_argument('-C', '--command', required=False,
                         help=f"Command line tool to execute (disables the user interface). "
                              f"Choices: {', '.join(cli_commands)}. See 'commands' below.",
                         type=str.lower, default=None, choices=[c.lower() for c in cli_commands], metavar='COMMAND')
    general.add_argument('-v', '--verbose', action='count', default=0, required=False,
                         help="Increase verbosity. -v adds debug output of the gateway adapter and (for "
                              "`cover_test`) every telegram, -vv additionally the serial communication and raw data.")
    general.add_argument('-lf', '--log_file', required=False, metavar='FILE',
                         help="Additionally write the whole log output - including the received telegrams - into "
                              "this file. The file is appended, not overwritten.")

    gateway = parser.add_argument_group(
        'gateway connection',
        "Used by `enocean_logger`, `burst_test` and `cover_test`.\n"
        "A second gateway is only needed by `burst_test`.")
    gateway.add_argument('-sp', '--serial_port', required=False, metavar='PORT',
                         help="Serial port of the gateway, e.g. COM3 or /dev/ttyUSB0. "
                              "For a LAN gateway: IP:PORT.")
    gateway.add_argument('-dt', '--device_type', required=False, type=str.lower, default="fgw14usb",
                         choices=device_type_choices, metavar='TYPE',
                         help=f"Type of the gateway. Default: fgw14usb. "
                              f"Choices: {', '.join(device_type_choices)}")
    gateway.add_argument('-sp2', '--serial_port2', required=False, metavar='PORT',
                         help="Serial port of the second gateway (`burst_test` reads the telegrams through it).")
    gateway.add_argument('-dt2', '--device_type2', required=False, type=str.lower, default="fgw14usb",
                         choices=device_type_choices, metavar='TYPE',
                         help="Type of the second gateway. Default: fgw14usb. Same choices as --device_type.")

    data = parser.add_argument_group(
        'device data',
        "Devices which are loaded on startup. The user interface and `enocean_logger` use them\n"
        "to show names and decoded telegram values, `generate_ha_config` to generate the\n"
        "configuration out of them.")
    data.add_argument('-c', '--app_config', required=False, default=None, metavar='FILE',
                      help="Stored application configuration of this application (must end with '.eodm').")
    data.add_argument('-pct14', '--pct14_export', required=False, metavar='FILE',
                      help="Configuration exported by PCT14 (must end with '.xml').")

    ha_config = parser.add_argument_group('command generate_ha_config')
    ha_config.add_argument('-ha', '--ha_config', required=False, metavar='FILE',
                           help="Output filename for the generated Home Assistant configuration. "
                                "Requires --app_config.")

    logger = parser.add_argument_group('command enocean_logger')
    logger.add_argument('-idf', '--log_telegram_id_filter', required=False, metavar='IDS',
                        help="Show only the telegrams of these devices. Comma-separated list of telegram IDs "
                             "(e.g. 'FE-D4-E9-47,FE-D4-E9-48'). Without it all telegrams are shown.",
                        type=lambda s: [x.strip().upper() for x in s.split(',') if x.strip()])

    burst = parser.add_argument_group('command burst_test')
    burst.add_argument('-md', '--message_delay', type=float, default=0.05, metavar='SEC', required=False,
                       help="Delay between two outgoing telegrams in seconds. Default: 0.05 => 50ms. "
                            "If the delay is too small the gateway runs into a buffer overflow.")
    burst.add_argument('-tmc', '--test_message_count', type=int, default=44, metavar='N', required=False,
                       help="Number of telegrams which are sent per test run. Default: 44.")

    cover = parser.add_argument_group(
        'command cover_test',
        "All given covers get exactly the same commands. Details:\n"
        "https://github.com/grimmpp/enocean-device-manager/tree/main/docs/cover_travel_test")
    cover.add_argument('-cid', '--cover_ids', required=False, metavar='IDS',
                       help="Covers to be tested. Comma-separated list of "
                            "'ACTUATOR_ID[:SWITCH_ID[+SWITCH_ID...]][:SENDER_ID]' entries, e.g. "
                            "'00-00-00-05,00-00-00-07:FE-D4-E9-48'. ACTUATOR_ID is the address the "
                            "status telegrams come from. SWITCH_ID is optional and names the wall switch which is "
                            "taught into that actuator - give it so that a pressed switch can be assigned to the "
                            "right cover; several switches of one cover are separated by '+'. SENDER_ID is the "
                            "address the commands are sent from, it defaults to '00-00-B0-XX' for bus devices. "
                            "Without a switch and with an explicit sender: '00-00-00-05::00-00-B0-05'.",
                       type=lambda s: [x.strip() for x in s.split(',') if x.strip()])
    cover.add_argument('-cseq', '--cover_sequence', required=False, metavar='SEQUENCE',
                       default="up:60,pause:5,down:60,pause:5",
                       help="Movement sequence: comma-separated list of 'COMMAND:SECONDS' entries which are "
                            "executed one after the other. Commands: up, down, stop, pause. "
                            "Default: 'up:60,pause:5,down:60,pause:5'. "
                            "Example: 'up:60,pause:5,down:20,stop,pause:3,down:60'.",
                       type=lambda s: [x.strip() for x in s.split(',') if x.strip()])
    cover.add_argument('-cms', '--cover_marker_switch', required=False, metavar='IDS',
                       help="Optional switch which is NOT taught into any actuator. Pressing it once marks a "
                            "point in time in the report, pressing it twice in a row signals that the cover has "
                            "reached its end position - that gives the travel time the cover really needed even "
                            "if the actuator keeps on running. Comma-separated list of ids.",
                       type=lambda s: [x.strip() for x in s.split(',') if x.strip()])
    cover.add_argument('-cmt', '--cover_marker_double_press_time', type=float, default=1.5, metavar='SEC',
                       required=False,
                       help="Two presses of the marker switch within this time count as one double press. "
                            "Default: 1.5 seconds.")
    cover.add_argument('-cmd', '--cover_message_delay', type=float, default=0.1, metavar='SEC', required=False,
                       help="Delay between two command telegrams in seconds. It is only applied between the "
                            "telegrams, not before the first one of a step. Default: 0.1 => 100ms. "
                            "Use 0 to send the commands without any delay.")
    cover.add_argument('-cm', '--cover_command_mode', required=False, type=str.lower, default='stop',
                       choices=['stop', 'timed'], metavar='MODE',
                       help="How the movement duration is applied. 'stop' (default) starts the movement and sends "
                            "a STOP command after the given time - works for any duration. 'timed' sends the "
                            "travel time within the command telegram (only possible up to 25.5 seconds).")
    cover.add_argument('-tr', '--test_report', required=False, metavar='FILE',
                       help="Write the printed report into this file as plain text.")
    cover.add_argument('-tcsv', '--test_report_csv', required=False, metavar='FILE',
                       help="Write the recorded telegrams into this file as CSV.")

    tests = parser.add_argument_group('commands burst_test and cover_test')
    tests.add_argument('-trc', '--test_run_count', type=int, default=1, metavar='N', required=False,
                       help="How often the whole test is repeated. Default: 1.")

    return parser.parse_args()


class ColoredHeadlineFormatter(logging.Formatter):
    """Replaces the plain headline by the colored one. Only used for the console
    so that the log files stay free of escape sequences."""

    def format(self, record) -> str:
        text = super().format(record)
        if ASCII_ART_HEADLINE in text:
            text = text.replace(ASCII_ART_HEADLINE, ascii_art_headline(stream=sys.stderr))
        return text


def init_logger(app_bus:AppBus, log_level:int=logging.INFO, verbose_level:int=0, log_file:str=None):
    file_handler = RotatingFileHandler(os.path.join(PROJECT_DIR, "enocean-device-manager.log"),
                                       mode='a', maxBytes=10*1024*1024, backupCount=2, encoding='utf-8', delay=0)
    stream_handler = logging.StreamHandler()
    handlers = [ file_handler, stream_handler ]

    # optional log file which was requested on the command line
    user_file_handler = None
    if log_file:
        user_file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        handlers.append(user_file_handler)

    logging.basicConfig(format='%(asctime)s %(levelname)s %(name)s %(message)s ',
                        level=log_level,
                        handlers=handlers)

    global LOGGER
    LOGGER = logging.getLogger(PACKAGE_NAME)
    LOGGER.setLevel(log_level)
    file_handler.setLevel(logging.DEBUG)
    stream_handler.setLevel(log_level)
    stream_handler.setFormatter(ColoredHeadlineFormatter('%(asctime)s %(levelname)s %(name)s %(message)s '))
    if user_file_handler is not None:
        user_file_handler.setLevel(log_level)

    logging.getLogger('esp2_gateway_adapter').setLevel(logging.INFO)
    logging.getLogger('eltakobus.serial').setLevel(logging.INFO)
    # third-party libraries which are very chatty on DEBUG level
    logging.getLogger('PIL').setLevel(logging.INFO)
    if verbose_level > 0:
        logging.getLogger('esp2_gateway_adapter').setLevel(logging.DEBUG)
    if verbose_level > 1:
        logging.getLogger('eltakobus.serial').setLevel(logging.DEBUG)

    LOGGER.info("Start Application eo_man\n" + ASCII_ART_HEADLINE + ApplicationInfo.get_app_info_as_str())
    # add print log messages for log message view on command line as debug
    def print_log_event(e:dict):
        log_level = e.get('log-level', 'INFO')
        log_level_int = logging.getLevelName(log_level)
        if log_level_int >= LOGGER.getEffectiveLevel():
            LOGGER.log(log_level_int, str(e['msg']))
    app_bus.add_event_handler(AppBusEventType.LOG_MESSAGE, print_log_event)


def main():
    opts = cli_argument()

    if hasattr(opts, 'help') and opts.help:
        return
    
    # init application message BUS
    app_bus = AppBus()

    init_logger(app_bus, logging.DEBUG if opts.verbose > 0 else logging.INFO, opts.verbose, opts.log_file)

    # init DATA MANAGER
    data_manager = DataManager(app_bus)

    # initially load from file application data
    if opts.app_config and opts.app_config.endswith('.eodm'):
       e = {'msg': f"Initially load data from file {opts.app_config}", 'color': 'darkred'}
       app_bus.fire_event(AppBusEventType.LOG_MESSAGE, e)
       data_manager.load_application_data_from_file(opts.app_config)
    elif opts.app_config:
       e = {'msg': f"Invalid filename {opts.app_config}. It must end with '.eodm'", 'color': 'darkred'}
       app_bus.fire_event(AppBusEventType.LOG_MESSAGE, e)
    elif opts.pct14_export and opts.pct14_export.endswith('.xml'):
        e = {'msg': f"Initially load exported data from PCT14 {opts.pct14_export}", 'color': 'darkred'}
        devices = asyncio.run( PCT14DataManager.get_devices_from_pct14(opts.pct14_export) )
        data_manager.load_devices(devices)

    # generate home assistant config instead of starting GUI
    if opts.command is None or opts.command.lower() not in cli_commands:
        from .view.main_panel import MainPanel
        MainPanel(app_bus, data_manager)

    elif opts.command.lower() == "generate_ha_config":
        # generate_ha_config
        if opts.app_config is None: 
            return
        if not opts.app_config.endswith('.eodm'):
            return
        if not opts.ha_config:
            e = {'msg': f"Target configuration filename for home assistant configuration must be specified.", 'color': 'darkred'}
            app_bus.fire_event(AppBusEventType.LOG_MESSAGE, e)
            return

        HomeAssistantConfigurationGenerator(app_bus, data_manager).save_as_yaml_to_file(opts.ha_config)

    # start enocean logger for commandline
    elif opts.command.lower() == "enocean_logger":
        if opts.serial_port is None:
            e = {'msg': "Serial port of the gateway must be specified (-sp).", 'log-level': 'ERROR', 'color': 'red'}
            app_bus.fire_event(AppBusEventType.LOG_MESSAGE, e)
            sys.exit(1)

        serial_controller = SerialController(app_bus, GatewayRegistry(app_bus))
        serial_controller.establish_serial_connection(opts.serial_port, opts.device_type)
        if not serial_controller.is_serial_connection_active():
            e = {'msg': f"No connection to gateway {opts.device_type} on {opts.serial_port}.",
                 'log-level': 'ERROR', 'color': 'red'}
            app_bus.fire_event(AppBusEventType.LOG_MESSAGE, e)
            sys.exit(1)

        enocean_logger = EnOceanLogger(app_bus, data_manager)
        enocean_logger.set_show_telegram_values(True)
        if opts.log_telegram_id_filter:
            # the argument is already parsed into a list of upper case ids
            enocean_logger.set_id_filter( opts.log_telegram_id_filter )
            e = {'msg': f"EnOcean Telegram Id filter was set to: {str.join(", ",enocean_logger.id_filter)}"}
            app_bus.fire_event(AppBusEventType.LOG_MESSAGE, e)

        app_bus.add_event_handler(AppBusEventType.SERIAL_CALLBACK, enocean_logger.serial_callback)
        
        def wait_for_enter():
            try:
                input("Press Enter to stop...\n")
            except (EOFError, OSError):
                # no interactive console (e.g. started as background process or
                # service). Keep on logging until the process is terminated.
                LOGGER.info("No console available to stop the logger. "
                            "Terminate the process to stop it (e.g. Ctrl+C or kill).")
                return
            serial_controller.stop_serial_connection()

        threading.Thread(target=wait_for_enter, daemon=True).start()

    elif opts.command.lower() == "burst_test":

        bt = BusBurstTester(app_bus, opts.serial_port, opts.device_type, opts.serial_port2, opts.device_type2, message_delay=opts.message_delay, quiet=opts.verbose==0, message_count=opts.test_message_count)
        bt.start_test(opts.test_run_count)

    elif opts.command.lower() == "cover_test":

        if opts.serial_port is None:
            e = {'msg': "Serial port of the gateway must be specified (-sp).", 'log-level': 'ERROR', 'color': 'red'}
            app_bus.fire_event(AppBusEventType.LOG_MESSAGE, e)
            sys.exit(1)
        if not opts.cover_ids:
            e = {'msg': "At least one cover id must be specified (-cid).", 'log-level': 'ERROR', 'color': 'red'}
            app_bus.fire_event(AppBusEventType.LOG_MESSAGE, e)
            sys.exit(1)

        try:
            ct = CoverTravelTester(app_bus, opts.serial_port, opts.device_type,
                                   cover_ids=opts.cover_ids,
                                   sequence=opts.cover_sequence,
                                   message_delay=opts.cover_message_delay,
                                   command_mode=opts.cover_command_mode,
                                   marker_switch_ids=opts.cover_marker_switch,
                                   marker_double_press_time=opts.cover_marker_double_press_time,
                                   verbose=opts.verbose)
        except ValueError as ex:
            app_bus.fire_event(AppBusEventType.LOG_MESSAGE, {'msg': str(ex), 'log-level': 'ERROR', 'color': 'red'})
            sys.exit(1)

        movements = ct.start_test(opts.test_run_count)

        if opts.test_report:
            ct.write_report_to_file(opts.test_report)
        if opts.test_report_csv:
            ct.write_telegrams_to_csv(opts.test_report_csv)

        # no movement at all means the test could not be executed
        if not movements:
            sys.exit(1)

    sys.exit(0)

if __name__ == "__main__":
    main()
