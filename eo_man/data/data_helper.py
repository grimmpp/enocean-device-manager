
import os
from termcolor import colored

from .const import *
from homeassistant.const import CONF_ID, CONF_DEVICE, CONF_DEVICES, CONF_NAME, CONF_PLATFORM, CONF_TYPE, CONF_DEVICE_CLASS, CONF_TEMPERATURE_UNIT, UnitOfTemperature, Platform

from eltakobus.device import BusObject, FAM14, SensorInfo, KeyFunction
from eltakobus.message import *
from eltakobus.eep import *
from eltakobus.device import SensorInfo, KeyFunction
from eltakobus.util import b2s, AddressExpression

SENDER_BASE_ID = 0x0000B000

EEP_MAPPING = [
    # gateways and bus connectors
    {'hw-type': 'BusObject', 'brand': 'unknown', CONF_EEP: 'unknown', CONF_TYPE: 'unknown', 'description': 'unknown bus device'},
    {'hw-type': 'FAM14', 'brand': 'Eltako', 'description': 'Bus Gateway', 'device_type': GatewayDeviceType.EltakoFAM14.value, 'docs': 'https://github.com/grimmpp/home-assistant-eltako/tree/main/docs/gateways'},
    {'hw-type': 'FGW14_USB', 'brand': 'Eltako', 'description': 'Bus Gateway', 'device_type': GatewayDeviceType.EltakoFGW14USB.value, 'docs': 'https://github.com/grimmpp/home-assistant-eltako/tree/main/docs/gateways'},
    {'hw-type': 'FTD14', 'brand': 'Eltako', 'description': 'Bus Gateway', 'device_type': GatewayDeviceType.EltakoFTD14.value, 'docs': 'https://github.com/grimmpp/home-assistant-eltako/tree/main/docs/gateways'},
    {'hw-type': 'FGW14', 'brand': 'Eltako', 'description': 'Bus Gateway'},
    {'hw-type': 'FAM-USB', 'brand': 'Eltako', 'description': 'USB Gateway', 'device_type': GatewayDeviceType.EltakoFAMUSB.value, 'docs': 'https://github.com/grimmpp/home-assistant-eltako/tree/main/docs/gateways'},
    {'hw-type': 'USB300', 'brand': 'unknown', 'description': 'USB Gateway', 'device_type': GatewayDeviceType.USB300.value, 'docs': 'https://github.com/grimmpp/home-assistant-eltako/tree/main/docs/gateways'},
    {'hw-type': 'MGW (LAN)', 'brand': 'PioTek', 'description': 'USB Gateway', 'device_type': GatewayDeviceType.LAN.value, 'docs': 'https://github.com/grimmpp/home-assistant-eltako/tree/main/docs/gateways'},
    {'hw-type': 'MGW (USB)', 'brand': 'PioTek', 'description': 'USB Gateway', 'device_type': GatewayDeviceType.ESP3.value, 'docs': 'https://github.com/grimmpp/home-assistant-eltako/tree/main/docs/gateways'},

    # Input module    
    {'hw-type': 'FTS14EM', 'brand': 'Eltako', CONF_EEP: 'F6-02-01', CONF_TYPE: Platform.BINARY_SENSOR, 'description': 'Wired Rocker switch', 'address_count': 1},
    {'hw-type': 'FTS14EM', 'brand': 'Eltako', CONF_EEP: 'F6-02-02', CONF_TYPE: Platform.BINARY_SENSOR, 'description': 'Wired Rocker switch', 'address_count': 1},
    {'hw-type': 'FTS14EM', 'brand': 'Eltako', CONF_EEP: 'F6-10-00', CONF_TYPE: Platform.BINARY_SENSOR, 'description': 'Window handle', 'address_count': 1},
    {'hw-type': 'FTS14EM', 'brand': 'Eltako', CONF_EEP: 'D5-00-01', CONF_TYPE: Platform.BINARY_SENSOR, 'description': 'Contact sensor', 'address_count': 1},
    {'hw-type': 'FTS14EM', 'brand': 'Eltako', CONF_EEP: 'A5-08-01', CONF_TYPE: Platform.BINARY_SENSOR, 'description': 'Occupancy sensor', 'address_count': 1},

    # Wireless 4-way pushbutton
    {'hw-type': 'FT55', 'brand': 'Eltako', CONF_EEP: 'F6-02-01', CONF_TYPE: Platform.BINARY_SENSOR, 'description': 'Wireless 4-way pushbutton', 'address_count': 1},
    {'hw-type': 'F4T55E', 'brand': 'Eltako', CONF_EEP: 'F6-02-01', CONF_TYPE: Platform.BINARY_SENSOR, 'description': 'Wireless 4-way pushbutton in E-Design55', 'address_count': 1},

    # window and door contacts
    {'hw-type': 'FFTE', 'brand': 'Eltako', CONF_EEP: 'F6-10-00', CONF_TYPE: Platform.BINARY_SENSOR, 'description': 'window and door contacts', 'address_count': 1},
    {'hw-type': 'FTKE', 'brand': 'Eltako', CONF_EEP: 'F6-10-00', CONF_TYPE: Platform.BINARY_SENSOR, 'description': 'window and door contacts', 'address_count': 1},
    {'hw-type': 'FTK', 'brand': 'Eltako', CONF_EEP: 'F6-10-00', CONF_TYPE: Platform.BINARY_SENSOR, 'description': 'window and door contacts', 'address_count': 1},

    # metering
    {'hw-type': 'FSDG14', 'brand': 'Eltako', CONF_EEP: 'A5-12-01', CONF_TYPE: Platform.SENSOR, 'description': 'Electricity Meter', 'address_count': 1},
    {'hw-type': 'F3Z14D', 'brand': 'Eltako', CONF_EEP: 'A5-12-01', CONF_TYPE: Platform.SENSOR, 'description': 'Electricity Meter', 'address_count': 3},
    {'hw-type': 'FSVA-230V-10A-Power-Meter', 'brand': 'Eltako', CONF_EEP: 'A5-12-01', CONF_TYPE: Platform.SENSOR, CONF_METER_TARIFFS: '[]', 'description': 'Power Meter', 'address_count': 1},
    {'hw-type': 'F3Z14D', 'brand': 'Eltako', CONF_EEP: 'A5-12-02', CONF_TYPE: Platform.SENSOR, 'description': 'Gas Meter', 'address_count': 3},
    {'hw-type': 'F3Z14D', 'brand': 'Eltako', CONF_EEP: 'A5-12-03', CONF_TYPE: Platform.SENSOR, 'description': 'Water Meter', 'address_count': 3},
    {'hw-type': 'FWZ14_65A', 'brand': 'Eltako', CONF_EEP: 'A5-12-01', CONF_TYPE: Platform.SENSOR, CONF_METER_TARIFFS: '[]', 'description': 'Electricity Meter', 'address_count': 1},
    
    # Weather Station
    {'hw-type': 'FWG14MS', 'brand': 'Eltako', CONF_EEP: 'A5-13-01', CONF_TYPE: Platform.SENSOR, 'description': 'Weather Station Gateway', 'address_count': 1},
    {'hw-type': 'MS', 'brand': 'Eltako', CONF_EEP: 'A5-13-01', CONF_TYPE: Platform.SENSOR, 'description': 'Weather Station', 'address_count': 1},
    {'hw-type': 'WMS', 'brand': 'Eltako', CONF_EEP: 'A5-13-01', CONF_TYPE: Platform.SENSOR, 'description': 'Weather Station', 'address_count': 1},
    {'hw-type': 'FWS61', 'brand': 'Eltako', CONF_EEP: 'A5-13-01', CONF_TYPE: Platform.SENSOR, 'description': 'Weather Station', 'address_count': 1},

    # Temp and humidity sensor
    {'hw-type': 'FLGTF', 'brand': 'Eltako', CONF_EEP: 'A5-04-02', CONF_TYPE: Platform.SENSOR, 'description': 'Temperature and Humidity Sensor', 'address_count': 1},
    {'hw-type': 'FLT58', 'brand': 'Eltako', CONF_EEP: 'A5-04-02', CONF_TYPE: Platform.SENSOR, 'description': 'Temperature and Humidity Sensor', 'address_count': 1},
    {'hw-type': 'FFT60', 'brand': 'Eltako', CONF_EEP: 'A5-04-02', CONF_TYPE: Platform.SENSOR, 'description': 'Temperature and Humidity Sensor', 'address_count': 1},
    {'hw-type': 'FTFSB', 'brand': 'Eltako', CONF_EEP: 'A5-04-02', CONF_TYPE: Platform.SENSOR, 'description': 'Temperature and Humidity Sensor', 'address_count': 1},

    # light sensor
    {'hw-type': 'FHD60SB', 'brand': 'Eltako', CONF_EEP: 'A5-06-01', CONF_TYPE: Platform.SENSOR, 'description': 'Light - Twilight and daylight Sensor', 'address_count': 1},

    # occupancy sensor
    {'hw-type': 'FABH65S', 'brand': 'Eltako', CONF_EEP: 'A5-08-01', CONF_TYPE: Platform.SENSOR, 'description': 'Light-, Temperature-, Occupancy Sensor', 'address_count': 1},
    {'hw-type': 'FBH65', 'brand': 'Eltako', CONF_EEP: 'A5-08-01', CONF_TYPE: Platform.SENSOR, 'description': 'Light-, Temperature-, Occupancy Sensor', 'address_count': 1},
    {'hw-type': 'FBH65S', 'brand': 'Eltako', CONF_EEP: 'A5-08-01', CONF_TYPE: Platform.SENSOR, 'description': 'Light-, Temperature-, Occupancy Sensor', 'address_count': 1},
    {'hw-type': 'FBH65TF', 'brand': 'Eltako', CONF_EEP: 'A5-08-01', CONF_TYPE: Platform.SENSOR, 'description': 'Light-, Temperature-, Occupancy Sensor', 'address_count': 1},

    # air quality
    {'hw-type': 'FLGTF', 'brand': 'Eltako', CONF_EEP: 'A5-09-0C', CONF_TYPE: Platform.SENSOR, 'description': 'Air Quality, Temperature and Humidity Sensor', 'address_count': 1},

    # Temp Controller
    {'hw-type': 'FUTH', 'brand': 'Eltako', CONF_EEP: 'A5-10-06', CONF_TYPE: Platform.SENSOR, 'description': 'Temperature Sensor and Controller', 'address_count': 1},
    {'hw-type': 'FUTH-feature', 'brand': 'Eltako', CONF_EEP: 'A5-10-12', CONF_TYPE: Platform.SENSOR, 'description': 'Temperature Sensor and Controller and Humidity Sensor', 'address_count': 1},

    # light dimmer
    {'hw-type': 'FUD14', 'brand': 'Eltako', CONF_EEP: 'A5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'PCT14-function-group': 3, 'PCT14-key-function': 32, 'description': 'Light dimmer', 'address_count': 1},
    {'hw-type': 'FUD14_800W', 'brand': 'Eltako', CONF_EEP: 'A5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'PCT14-function-group': 3, 'PCT14-key-function': 32, 'description': 'Light dimmer', 'address_count': 1},

    # Dali Gateway
    {'hw-type': 'FDG14', 'brand': 'Eltako', CONF_EEP: 'A5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'PCT14-function-group': 1, 'PCT14-key-function': 32, 'description': 'Dali Gateway', 'address_count': 16},
    {'hw-type': 'FD2G14', 'brand': 'Eltako', CONF_EEP: 'A5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'PCT14-function-group': 1, 'PCT14-key-function': 32, 'description': 'Dali Gateway', 'address_count': 16},

    # relays
    {'hw-type': 'FMZ14', 'brand': 'Eltako', CONF_EEP: 'M5-38-08', 'sender_eep': 'F6-02-01', CONF_TYPE: Platform.LIGHT, 'PCT14-function-group': 1, 'PCT14-key-function': 1, 'description': 'Relay', 'address_count': 1},
    {'hw-type': 'FSR14', 'brand': 'Eltako', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'PCT14-function-group': 2, 'PCT14-key-function': 51, 'description': 'Relay', 'address_count': 1},
    {'hw-type': 'FSR14_1x', 'brand': 'Eltako', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'PCT14-function-group': 2, 'PCT14-key-function': 51, 'description': 'Relay', 'address_count': 1},
    {'hw-type': 'FSR14_2x', 'brand': 'Eltako', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'PCT14-function-group': 2, 'PCT14-key-function': 51, 'description': 'Relay', 'address_count': 2},
    {'hw-type': 'FSR14_4x', 'brand': 'Eltako', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'PCT14-function-group': 2, 'PCT14-key-function': 51, 'description': 'Relay', 'address_count': 4},
    {'hw-type': 'FSR14M_2x', 'brand': 'Eltako', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'PCT14-function-group': 2, 'PCT14-key-function': 51, 'description': 'Relay', 'address_count': 2},
    {'hw-type': 'FSR14M_2x-feature', 'brand': 'Eltako', CONF_EEP: 'A5-12-01', CONF_TYPE: Platform.SENSOR, CONF_METER_TARIFFS: '[]', 'description': 'Electricity Meter', 'address_count': 2},
    {'hw-type': 'F4SR14_LED', 'brand': 'Eltako', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'PCT14-function-group': 2, 'PCT14-key-function': 51, 'description': 'Relay', 'address_count': 4},

    # covers
    {'hw-type': 'FSB14', 'brand': 'Eltako', CONF_EEP: 'G5-3F-7F', 'sender_eep': 'H5-3F-7F', CONF_TYPE: Platform.COVER, 'PCT14-function-group': 2, 'PCT14-key-function': 31, 'description': 'Cover', 'address_count': 2},

    # heating and cooling
    {'hw-type': 'FHK14', 'brand': 'Eltako', CONF_EEP: 'A5-10-06', 'sender_eep': 'A5-10-06', CONF_TYPE: Platform.CLIMATE, 'PCT14-function-group': 3, 'PCT14-key-function': 65, 'description': 'Heating/Cooling', 'address_count': 2},
    {'hw-type': 'F4HK14', 'brand': 'Eltako', CONF_EEP: 'A5-10-06', 'sender_eep': 'A5-10-06', CONF_TYPE: Platform.CLIMATE, 'PCT14-function-group': 3, 'PCT14-key-function': 65, 'description': 'Heating/Cooling', 'address_count': 4},
    {'hw-type': 'FAE14SSR', 'brand': 'Eltako', CONF_EEP: 'A5-10-06', 'sender_eep': 'A5-10-06', CONF_TYPE: Platform.CLIMATE, 'PCT14-function-group': 3, 'PCT14-key-function': 65, 'description': 'Heating/Cooling', 'address_count': 2},

    # decentralized relays
    {'hw-type': 'FMZ61', 'brand': 'Eltako', CONF_EEP: 'M5-38-08', 'sender_eep': 'F6-02-01', CONF_TYPE: Platform.LIGHT, 'description': 'Relay', 'address_count': 1},
    {'hw-type': 'FSR61-230V', 'brand': 'Eltako', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'description': 'Relay', 'address_count': 1},
    {'hw-type': 'FSR61NP-230V', 'brand': 'Eltako', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'description': 'Relay', 'address_count': 1},
    {'hw-type': 'FSR61/8-24V UC', 'brand': 'Eltako', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'description': 'Relay', 'address_count': 1},
    {'hw-type': 'FSR61-230V', 'brand': 'Eltako', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'description': 'Relay', 'address_count': 1},
    {'hw-type': 'FSR61G-230V', 'brand': 'Eltako', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'description': 'Relay', 'address_count': 1},
    {'hw-type': 'FSR61LN-230V', 'brand': 'Eltako', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'description': 'Relay', 'address_count': 2},
    {'hw-type': 'FLC61NP-230V', 'brand': 'Eltako', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'description': 'Relay', 'address_count': 1},
    {'hw-type': 'FR62-230V', 'brand': 'Eltako', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'description': 'Relay', 'address_count': 1},
    {'hw-type': 'FR62NP-230V', 'brand': 'Eltako', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'description': 'Relay', 'address_count': 1},
    {'hw-type': 'FL62-230V', 'brand': 'Eltako', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'description': 'Relay', 'address_count': 1},
    {'hw-type': 'FL62NP-230V', 'brand': 'Eltako', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'description': 'Relay', 'address_count': 1},
    {'hw-type': 'FSSA-230V', 'brand': 'Eltako', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'description': 'Socket Switch Actuator', 'address_count': 1},
    {'hw-type': 'FSVA-230V-10A', 'brand': 'Eltako', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'description': 'Socket Switch Actuator', 'address_count': 1},
    
    # decentralized dimmers
    {'hw-type': 'FUD61NP-230V', 'brand': 'Eltako', CONF_EEP: 'A5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'description': 'Light dimmer', 'address_count': 1},
    {'hw-type': 'FUD61NPN-230V', 'brand': 'Eltako', CONF_EEP: 'A5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'description': 'Light dimmer', 'address_count': 1},
    {'hw-type': 'FD62NP-230V', 'brand': 'Eltako', CONF_EEP: 'A5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'description': 'Relay', 'address_count': 1},
    {'hw-type': 'FD62NPN-230V', 'brand': 'Eltako', CONF_EEP: 'A5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'description': 'Relay', 'address_count': 1},

    # decentralized covers
    {'hw-type': 'FSB61-230V', 'brand': 'Eltako', CONF_EEP: 'G5-3F-7F', 'sender_eep': 'H5-3F-7F', CONF_TYPE: Platform.COVER, 'address_count': 1, 'description': 'Cover'},
    {'hw-type': 'FSB61NP-230V', 'brand': 'Eltako', CONF_EEP: 'G5-3F-7F', 'sender_eep': 'H5-3F-7F', CONF_TYPE: Platform.COVER, 'address_count': 1, 'description': 'Cover'},
    {'hw-type': 'FJ62/12-36V DC', 'brand': 'Eltako', CONF_EEP: 'G5-3F-7F', 'sender_eep': 'H5-3F-7F', CONF_TYPE: Platform.COVER, 'address_count': 1, 'description': 'Cover'},
    {'hw-type': 'FJ62NP-230V', 'brand': 'Eltako', CONF_EEP: 'G5-3F-7F', 'sender_eep': 'H5-3F-7F', CONF_TYPE: Platform.COVER, 'address_count': 1, 'description': 'Cover'},
    {'hw-type': 'FSUD-230V', 'brand': 'Eltako', CONF_EEP: 'G5-3F-7F', 'sender_eep': 'H5-3F-7F', CONF_TYPE: Platform.COVER, 'address_count': 1, 'description': 'Cover'},
]

ORG_MAPPING = {
    5: {'Telegram': 'RPS', 'RORG': 'F6', CONF_NAME: 'Switch', CONF_TYPE: Platform.BINARY_SENSOR, CONF_EEP: 'F6-02-01' },
    6: {'Telegram': '1BS', 'RORG': 'D5', CONF_NAME: '1 Byte Communication', CONF_TYPE: Platform.SENSOR, CONF_EEP: 'D5-??-??' },
    7: {'Telegram': '4BS', 'RORG': 'A5', CONF_NAME: '4 Byte Communication', CONF_TYPE: Platform.SENSOR, CONF_EEP: 'A5-??-??' },
}

KNOWN_MDNS_SERVICES = {
    'SmartConn': '_bsc-sc-socket._tcp.local.',
    'Virtual-Network-Gateway-Adapter': '_bsc-sc-socket._tcp.local.',
    'EUL': '_tcm515._tcp.local.'
}

MDNS_SERVICE_2_GW_TYPE_MAPPING = {
    'SmartConn': GatewayDeviceType.LAN,
    'EUL': GatewayDeviceType.LAN,
    'Virtual-Network-Gateway-Adapter': GatewayDeviceType.LAN_ESP2,
}

SENSOR_MESSAGE_TYPES = [EltakoWrappedRPS, EltakoWrapped4BS, RPSMessage, Regular4BSMessage, Regular1BSMessage, EltakoMessage]

def get_all_eep_names():
    subclasses = set()
    work = [EEP]
    while work:
        parent = work.pop()
        for child in parent.__subclasses__():
            if child not in subclasses:
                subclasses.add(child)
                work.append(child)
    return sorted(set([s.__name__.replace('_', '-').upper() for s in subclasses if len(s.__name__) == 8 and s.__name__.count('_') == 2]))

def find_eep_by_name(eep_name:str) -> EEP:
    for child in EEP.__subclasses__():
        if child.__name__.replace('_', '-').upper() == eep_name.replace('_', '-').upper():
            return child
        for sub_child in child.__subclasses__():
            if sub_child.eep_string.replace('_', '-').upper() == eep_name.replace('_', '-').upper():
                return sub_child
    return None

def get_values_for_eep(eep:EEP, message:EltakoMessage) -> list[str]:
    properties_as_str = []
    for k, v in eep.decode_message(message).__dict__.items():
        properties_as_str.append(f"{str(k)[1:] if str(k).startswith('_') else str(k)}: {str(v)}")

    return properties_as_str

def a2s(address:int, length:int=4):
    """address to string"""
    if address is None:
        return ""
    
    return b2s( address.to_bytes(length, byteorder = 'big') )

def build_unique_name_for_device_type(device_type:str)->str:
    dev_type = device_type.replace('-', '_').upper()
    #remove unimportant parts
    for c in ['/']:
        index = dev_type.find(c)
        if index != -1:
            dev_type = dev_type[:index]

    return dev_type

def find_device_info_by_device_type(device_type:str, eep:str=None) -> dict:
    for i in EEP_MAPPING:
        hw_type = str(i['hw-type']).replace('-', '_').upper()
        dev_type = build_unique_name_for_device_type(device_type)

        if hw_type == dev_type:
            if eep is None:
                return i
            elif i[CONF_EEP] == eep:
                return i
    return {}

def find_device_info_by_eep(eep:str) -> dict:
    for i in EEP_MAPPING:
        if CONF_EEP in i and i[CONF_EEP] == eep:
            return i
    return {}

def is_device_description(description:str) -> bool:
    for i in EEP_MAPPING:
        if 'description' in i and i['description'] == description:
            return True
    return False

def get_known_device_types() -> list:
    return sorted(list(set([t['hw-type'] for t in EEP_MAPPING])))

def get_eep_from_key_function_name(kf: KeyFunction) -> str:
    pos = KeyFunction(kf).name.find('EEP_')
    if pos > -1:
        substr = KeyFunction(kf).name[pos+4:pos+4+8].replace('_', '-')
        return substr
    return None

def get_name_from_key_function_name(kf: KeyFunction) -> str:
    pos = KeyFunction(kf).name.find('_ACCORDING_')
    if pos > -1:
        substr = KeyFunction(kf).name[0:pos].replace('_', ' ').lower().title()
        return substr
    return ""

def a2i(address:str) -> int:
    return int.from_bytes(AddressExpression.parse(address)[0], 'big')

class BusObjectHelper():

    @classmethod
    def find_sensors(cls, sensors:list[SensorInfo], dev_id: int, channel:int, in_func_group: int) -> list[SensorInfo]:
        result = []
        for s in sensors: 
            if s.dev_id == dev_id and s.channel == channel and s.in_func_group == in_func_group:
                result.append(s)
        return result

    @classmethod
    def find_sensor(cls, sensors:list[SensorInfo], dev_id: int, channel:int, in_func_group: int) -> SensorInfo:
        l = cls.find_sensors(sensors, dev_id, channel, in_func_group)
        if len(l) > 0:
            return l[0]
        return None
    
def add_addresses(adr1:str, adr2:str) -> str:
    _adr1 = int.from_bytes( AddressExpression.parse(adr1)[0], 'big')
    _adr2 = int.from_bytes( AddressExpression.parse(adr2)[0], 'big')
    return a2s(_adr1 + _adr2)
    
def print_memory_entires(sensors: list[SensorInfo]) -> None:
    for _s in sensors:
        s:SensorInfo = _s
        print(f"{s.memory_line}: {b2s(s.sensor_id, ' ')} {hex(s.key)} {hex(s.key_func)} {hex(s.channel)} (FG: {s.in_func_group})")
        

def get_all_device_classes(cls=BusObject):
    subclasses = cls.__subclasses__()  # Get immediate subclasses
    for subclass in subclasses:
        subclasses.extend(get_all_device_classes(subclass))  # Recursively add subclasses
    return subclasses

def find_device_class_by_name(name:str) -> BusObject:
    for dc in get_all_device_classes():
        if build_unique_name_for_device_type(dc.__name__) == build_unique_name_for_device_type(name):
            return dc
    return None
