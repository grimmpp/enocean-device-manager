import sys
import os
import argparse
import asyncio
from typing import Final
from logging.handlers import RotatingFileHandler
import time
import threading

import warnings
from bs4 import XMLParsedAsHTMLWarning
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

PACKAGE_NAME: Final = 'eo_man'

# load same path like calling the app via 'python -m eo-man'
PROJECT_DIR = os.path.dirname(__file__)
file_dir = os.path.join( PROJECT_DIR, '..')
sys.path.append(file_dir)
__import__(PACKAGE_NAME)
__package__ = PACKAGE_NAME

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

import logging

cli_commands = ["generate_ha_config", "enocean_logger", "burst_test"]

ASCII_ART_HEADLINE = (
    " _____     _____                    ____          _            _____                         \n"
    "|   __|___|     |___ ___ ___ ___   |    \\ ___ _ _|_|___ ___   |     |___ ___ ___ ___ ___ ___ \n"
    "|   __|   |  |  |  _| -_| .'|   |  |  |  | -_| | | |  _| -_|  | | | | .'|   | .'| . | -_|  _|\n"
    "|_____|_|_|_____|___|___|__,|_|_|  |____/|___|\\_/|_|___|___|  |_|_|_|__,|_|_|__,|_  |___|_|\n"
    "                                                                                |___|        \n")

def cli_argument():
    description = (
        ASCII_ART_HEADLINE + "\n\n"
        "EnOcean Device Manager (https://github.com/grimmpp/enocean-device-manager) "
        "manages your EnOcean devices and generate Home Assistant configurations for the "
        "Home Assistant Eltako Integration (https://github.com/grimmpp/home-assistant-eltako)."
    )
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument('-v', '--verbose', action='count', default=0, required=False,
                        help='Increase verbosity (repeat for more verbose).')
    parser.add_argument('-C', '--command', required=False,
                        help=f"Action to perform (disables GUI when specified). Choices: {', '.join(cli_commands)}",
                        type=str.lower, default=None, choices=[c.lower() for c in cli_commands])
    parser.add_argument('-sp', '--serial_port', required=False, help='Serial port for gateway', metavar='PORT')
    device_type_choices = [str(d.value).lower() for d in GatewayDeviceType]
    parser.add_argument('-dt', '--device_type', required=False, type=str.lower, default="fgw14-usb", choices=device_type_choices,
                        help=f"Device type for serial port. Choices: {', '.join(device_type_choices)}", metavar='TYPE')
    parser.add_argument('-sp2', '--serial_port2', required=False, help='Second serial port (optional)', metavar='PORT')
    parser.add_argument('-dt2', '--device_type2', required=False, type=str.lower, default="fgw14-usb", choices=device_type_choices,
                        help=f"Device type for second serial port. Choices: {', '.join(device_type_choices)}", metavar='TYPE')
    parser.add_argument('-c', '--app_config', required=False, default=None, metavar='FILE',
                        help="Stored application configuration filename (must end with '.eodm').")
    parser.add_argument('-ha', '--ha_config', required=False, metavar='FILE',
                        help='Output filename for generated Home Assistant configuration (disables GUI) for command `generate_ha_config`.')
    parser.add_argument('-pct14', '--pct14_export', required=False, metavar='FILE',
                        help="PCT14 exported file (must end with '.xml').")
    parser.add_argument('-md', '--message_delay', type=float, default=0.05, metavar='SEC', required=False, 
                        help='Delay between outgoing messages in seconds.')
    parser.add_argument('-trc', '--test_run_count', type=int, default=1, metavar='N', required=False, 
                        help='Number of test runs to execute.')
    parser.add_argument('-idf', '--log_telegram_id_filter', required=False, 
                        help="Filter for command `enocean_logger`. Comma-separated list of telegram IDs to show (e.g. 'FE-D4-E9-47,FE-D4-E9-48').",
                        type=lambda s: [x.strip().upper() for x in s.split(',') if x.strip()])

    return parser.parse_args()


def init_logger(app_bus:AppBus, log_level:int=logging.INFO, verbose_level:int=0):
    file_handler = RotatingFileHandler(os.path.join(PROJECT_DIR, "enocean-device-manager.log"), 
                                       mode='a', maxBytes=10*1024*1024, backupCount=2, encoding=None, delay=0)
    stream_handler = logging.StreamHandler()

    logging.basicConfig(format='%(asctime)s %(levelname)s %(name)s %(message)s ',
                        level=log_level,
                        handlers=[ file_handler, stream_handler ])
    
    global LOGGER
    LOGGER = logging.getLogger(PACKAGE_NAME)
    LOGGER.setLevel(log_level)
    file_handler.setLevel(logging.DEBUG)
    stream_handler.setLevel(log_level)
    
    logging.getLogger('esp2_gateway_adapter').setLevel(logging.INFO)
    logging.getLogger('eltakobus.serial').setLevel(logging.INFO)
    if verbose_level > 0:
        logging.getLogger('esp2_gateway_adapter').setLevel(logging.DEBUG)
    elif verbose_level > 1:
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

    init_logger(app_bus, logging.DEBUG if opts.verbose > 0 else logging.INFO)

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
        if opts.serial_port is not None and opts.device_type is not None:
            serial_controller = SerialController(app_bus, GatewayRegistry(app_bus))
            serial_controller.establish_serial_connection(opts.serial_port, opts.device_type)

        enocean_logger = EnOceanLogger(app_bus, data_manager)
        enocean_logger.set_show_telegram_values(True)
        if opts.log_telegram_id_filter is not None:
            enocean_logger.set_id_filter( str(opts.log_telegram_id_filter).replace(' ', '').upper().split(',') )
            e = {'msg': f"EnOcean Telegram Id filter was set to: {str.join(", ",enocean_logger.id_filter)}"}
            app_bus.fire_event(AppBusEventType.LOG_MESSAGE, e)

        app_bus.add_event_handler(AppBusEventType.SERIAL_CALLBACK, enocean_logger.serial_callback)
        
        def wait_for_enter():
            input("Press Enter to stop...\n")
            serial_controller.stop_serial_connection()

        threading.Thread(target=wait_for_enter, daemon=True).start()

    elif opts.command.lower() == "burst_test":

        bt = BusBurstTester(app_bus, opts.serial_port, opts.device_type, opts.serial_port2, opts.device_type2, message_delay=opts.message_delay, quiet=opts.verbose==0)
        bt.start_test(opts.test_run_count)

    sys.exit(0)

if __name__ == "__main__":
    main()
