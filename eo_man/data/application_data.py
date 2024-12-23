from typing import Final
import yaml

from .device import Device
from .filter import DataFilter
from .recorded_message import RecordedMessage

import pickle

class ApplicationData():

    class_version:Final = '1.0.0'

    def __init__(self, 
                 version:str='unknown', 
                 selected_data_filter:str=None, data_filters:dict[str:DataFilter]={},
                 devices:dict[str:Device]={},
                 recoreded_messages:list[RecordedMessage]=[]):
        
        self.application_version:str = version

        self.selected_data_filter_name:str=selected_data_filter
        self.data_filters:dict[str:DataFilter] = data_filters

        self.devices:dict[str:Device] = devices

        self.recoreded_messages:list[RecordedMessage] = recoreded_messages

        self.send_message_template_list: list[str] = []


    translations:dict[str:str] ={
        'name: HA Contoller': 'name: HA Controller',
        '(Wireless Tranceiver)': '(Wireless Transceiver)'
    }

    @classmethod
    def read_from_file(cls, filename:str):
        result = ApplicationData()

        file_content = None
        with open(filename, 'rb') as file:
            file_content = pickle.loads(file) 

        if isinstance(file_content, ApplicationData):
            result = file_content
            return result
        
        # to be downwards compatible
        if isinstance(file_content, dict) and len(file_content) > 0 and isinstance(list(file_content.values())[0], Device):
            result.devices = file_content

        if hasattr(file_content, 'devices'):
            result.devices = file_content.devices

        if hasattr(file_content, 'data_filters'):
            result.data_filters = file_content.data_filters
            
        if hasattr(file_content, 'selected_data_filter_name'):
            result.selected_data_filter_name = file_content.selected_data_filter_name

        if hasattr(file_content, 'application_version'):
            result.application_version = file_content.application_version

        return result
    
    @classmethod
    def _migrate(cls, obj):
        """required to make different versions compatibel"""
        if not hasattr(obj, 'recoreded_messages'):
            setattr(obj, 'recoreded_messages', [])

        if not hasattr(obj, 'send_message_template_list'):
            setattr(obj, 'send_message_template_list', [])

        for d in obj.devices.values():
            if not hasattr(d, 'additional_fields'):
                d.additional_fields = {}
            if not hasattr(d, 'ha_platform'):
                d.ha_platform = None
            if not hasattr(d, 'eep'):
                d.eep = None
            if not hasattr(d, 'key_function'):
                d.key_function = None
            if not hasattr(d, 'comment'):
                d.comment = None
            if not hasattr(d, 'device_type'):
                d.device_type = None

            if 'sender' in d.additional_fields and 'id' in d.additional_fields['sender']:
                try:
                    sender_id = d.additional_fields['sender']['id']
                    if isinstance(sender_id, str) and '-' in sender_id:
                        id = int( sender_id.split('-')[-1], 16 )
                        if id > 128: id -= 128
                        hex_id = hex(id)[2:].upper()
                        if len(hex_id) == 1: hex_id = "0"+hex_id
                        d.additional_fields['sender']['id'] = hex_id
                except:
                    pass

    @classmethod
    def read_from_yaml_file(cls, filename:str):
        with open(filename, 'r') as file:
            file_content = file.read()
            for k,v in cls.translations.items():
                file_content.replace(k,v)
            app_data = yaml.load(file_content, Loader=yaml.Loader)
        cls._migrate(app_data)
        
        return app_data
        
    
    # @classmethod
    # def from_yaml(cls, constructor, node):
    #     return cls(version=node.version, 
    #                selected_data_filter=node.selected_data_filter,
    #                data_filters=node.data_filters,
    #                devices=node.devices
    #                )

    @classmethod
    def write_to_file(cls, filename:str, application_data):
        with open(filename, 'wb') as file:
            pickle.dump(application_data, file)

    @classmethod
    def write_to_yaml_file(cls, filename:str, application_data):
        with open(filename, 'w') as file:
            yaml.dump(application_data, file)