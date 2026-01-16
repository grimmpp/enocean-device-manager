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
from .controller.app_bus import AppBus, AppBusEventType
from .controller.enocean_logger import EnOceanLogger
from .controller.serial_controller import SerialController
from .controller.gateway_registry import GatewayRegistry
from .controller.bus_burst_tester import BusBurstTester

import logging

cli_commands = ["generate_ha_config", "enocean_logger", "burst_test"]

def cli_argument():
    p = argparse.ArgumentParser(
        description=
"""EnOcean Device Manager (https://github.com/grimmpp/enocean-device-manager) allows you to managed your EnOcean devices and to generate 
Home Assistant Configurations for the Home Assistant Eltako Integration (https://github.com/grimmpp/home-assistant-eltako).""")
    p.add_argument('-v', '--verbose', help="Logs all messages.", action='count', default=0)
    p.add_argument('-md', '--message_delay', help="Delay to send messages.", type=float, default=0.05)
    p.add_argument('-trc', '--test_run_count', help="Amount of test runs to be executed.", type=float, default=1)
    p.add_argument('-c', "--app_config", help="Filename of stored application configuration. Filename must end with '.eodm'.", default=None)
    p.add_argument('-ha', "--ha_config", help="Filename for Home Assistant Configuration for Eltako Integration. By passing the filename it will disable the GUI and only generate the Home Assistant Configuration file.")
    p.add_argument('-pct14', '--pct14_export', help="Load PCT14 exported file. Filename must end with .xml")
    p.add_argument('-sp', '--serial_port', help="Serial port")
    p.add_argument('-dt', '--device_type', help="Device Type for serial port")
    p.add_argument('-sp2', '--serial_port2', help="Serial port")
    p.add_argument('-dt2', '--device_type2', help="Device Type for serial port")
    p.add_argument('-idf', '--log_telegram_id_filter', help="List of telegram ids which will be shown for log command. E.g. 'FE-D4-E9-47, FE-D4-E9-48, FE-D4-E9-49'")
    p.add_argument('-C', '--command', help=f"Action to perform. If nothing specified GUI will appear. Commands are {str.join(", ", cli_commands)}")
    return p.parse_args()


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

    LOGGER.info("Start Application eo_man")
    LOGGER.info(ApplicationInfo.get_app_info_as_str())
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
