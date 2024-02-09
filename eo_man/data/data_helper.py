
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
    {'hw-type': 'FTS14EM', CONF_EEP: 'F6-02-01', CONF_TYPE: Platform.BINARY_SENSOR, 'description': 'Rocker switch', 'address_count': 1},
    {'hw-type': 'FTS14EM', CONF_EEP: 'F6-02-02', CONF_TYPE: Platform.BINARY_SENSOR, 'description': 'Rocker switch', 'address_count': 1},
    {'hw-type': 'FTS14EM', CONF_EEP: 'F6-10-00', CONF_TYPE: Platform.BINARY_SENSOR, 'description': 'Window handle', 'address_count': 1},
    {'hw-type': 'FTS14EM', CONF_EEP: 'D5-00-01', CONF_TYPE: Platform.BINARY_SENSOR, 'description': 'Contact sensor', 'address_count': 1},
    {'hw-type': 'FTS14EM', CONF_EEP: 'A5-08-01', CONF_TYPE: Platform.BINARY_SENSOR, 'description': 'Occupancy sensor', 'address_count': 1},

    # {'hw-type': 'FWG14', CONF_EEP: 'A5-13-01', CONF_TYPE: Platform.SENSOR, 'description': 'Weather station', 'address_count': 1},
    {'hw-type': 'FTS14EM', CONF_EEP: 'A5-12-01', CONF_TYPE: Platform.SENSOR, 'description': 'Window handle', 'address_count': 1},
    {'hw-type': 'FSDG14', CONF_EEP: 'A5-12-02', CONF_TYPE: Platform.SENSOR, 'description': 'Automated meter reading - electricity', 'address_count': 1},
    {'hw-type': 'F3Z14D', CONF_EEP: 'A5-13-01', CONF_TYPE: Platform.SENSOR, 'description': 'Automated meter reading - gas', 'address_count': 1},
    {'hw-type': 'F3Z14D', CONF_EEP: 'A5-12-03', CONF_TYPE: Platform.SENSOR, 'description': 'Automated meter reading - water', 'address_count': 1},

    {'hw-type': 'FUD14', CONF_EEP: 'A5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'PCT14-function-group': 3, 'PCT14-key-function': 32, 'description': 'Central command - gateway', 'address_count': 1},
    {'hw-type': 'FUD14_800W', CONF_EEP: 'A5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'PCT14-function-group': 3, 'PCT14-key-function': 32, 'description': 'Central command - gateway', 'address_count': 1},

    {'hw-type': 'FMZ14', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'PCT14-function-group': 1, 'description': 'Eltako relay', 'address_count': 1},
    {'hw-type': 'FSR14', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'PCT14-function-group': 2, 'PCT14-key-function': 51, 'description': 'Eltako relay', 'address_count': 1},
    {'hw-type': 'FSR14_1x', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'PCT14-function-group': 2, 'PCT14-key-function': 51, 'description': 'Eltako relay', 'address_count': 1},
    {'hw-type': 'FSR14_x2', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'PCT14-function-group': 2, 'PCT14-key-function': 51, 'description': 'Eltako relay', 'address_count': 2},
    {'hw-type': 'FSR14_4x', CONF_EEP: 'M5-38-08', 'sender_eep': 'A5-38-08', CONF_TYPE: Platform.LIGHT, 'PCT14-function-group': 2, 'PCT14-key-function': 51, 'description': 'Eltako relay', 'address_count': 4},

    {'hw-type': 'FSB14', CONF_EEP: 'G5-3F-7F', 'sender_eep': 'H5-3F-7F', CONF_TYPE: Platform.COVER, 'PCT14-function-group': 2, 'PCT14-key-function': 31, 'description': 'Eltako cover', 'address_count': 2},

    {'hw-type': 'FAE14SSR', CONF_EEP: 'A5-10-06', 'sender_eep': 'A5-10-06', CONF_TYPE: Platform.CLIMATE, 'PCT14-function-group': 3, 'PCT14-key-function': 65, 'description': 'Eltako heating/cooling', 'address_count': 2},
]

ORG_MAPPING = {
    5: {'Telegram': 'RPS', 'RORG': 'F6', CONF_NAME: 'Switch', CONF_TYPE: Platform.BINARY_SENSOR, CONF_EEP: 'F6-02-01' },
    6: {'Telegram': '1BS', 'RORG': 'D5', CONF_NAME: '1 Byte Communication', CONF_TYPE: Platform.SENSOR, CONF_EEP: 'D5-??-??' },
    7: {'Telegram': '4BS', 'RORG': 'A5', CONF_NAME: '4 Byte Communication', CONF_TYPE: Platform.SENSOR, CONF_EEP: 'A5-??-??' },
}

SENSOR_MESSAGE_TYPES = [EltakoWrappedRPS, EltakoWrapped4BS, RPSMessage, Regular4BSMessage, Regular1BSMessage, EltakoMessage]

def get_subclasses(cls):
    for subclass in cls.__subclasses__():
        yield from get_subclasses(subclass)
        yield subclass


def get_eep_names():
    eep_list = []
    eep_classes = get_subclasses(EEP)
    for c in eep_classes:
        if len(c.__name__) == 8 and c.__name__.count('_') == 2:
            eep_list.append(c.__name__.replace('_','-').upper())
    return sorted(set(eep_list))

def a2s(address:int, length:int=4):
    """address to string"""
    if address is None:
        return ""
    
    return b2s( address.to_bytes(length, byteorder = 'big') )

def find_device_info_by_device_type(device_type:str) -> dict:
    for i in EEP_MAPPING:
        if i['hw-type'] == device_type:
            return i
    return None

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
        

def get_application_version() -> str:
    filename = os.path.join(os.path.dirname(__file__), '..', '..', 'eo_man.egg-info', 'PKG-INFO')
    if os.path.isfile(filename):
        with open(filename, 'r', encoding="utf8") as f:
            lines = f.read().splitlines()
        for l in lines:
            if l.startswith('Version: '):
                return l[len('Version: '):]
    return 'unknown'