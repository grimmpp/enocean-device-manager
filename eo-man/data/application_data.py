from typing import Final
from .device import Device
from .filter import DataFilter

import pickle

class ApplicationData():

    class_version:Final = '1.0.0'

    def __init__(self):
        self.application_version:str = 'unknown'
        self.selected_data_filter_name:str=None
        self.data_filters:dict[str:DataFilter] = {}
        self.devices:dict[str:Device] = {}

    @classmethod
    def read_from_file(cls, filename:str):
        result = ApplicationData()

        file_content = None
        with open(filename, 'rb') as file:
            file_content = pickle.load(file) 

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
    def write_to_file(cls, filename:str, application_data):
        with open(filename, 'wb') as file:
            pickle.dump(application_data, file)