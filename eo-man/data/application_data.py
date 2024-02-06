
from .device import Device
from .filter import DataFilter

import pickle

class ApplicationData():

    def __init__(self):
        self.selected_data_filter_name:str=None
        self.data_filters:dict[str:DataFilter] = {}
        self.devices:dict[str:Device] = {}

    @classmethod
    def read_from_file(cls, filename:str):
        result = ApplicationData()

        file_content = None
        with open(filename, 'rb') as file:
            file_content = pickle.load(file) 

        # to be downwards compatible
        if isinstance(file_content, dict) and len(file_content) > 0 and isinstance(list(file_content.values())[0], Device):
            result.devices = file_content
        elif isinstance(file_content, ApplicationData):
            result = file_content

        return result
    

    @classmethod
    def write_to_file(cls, filename:str, application_data):
        with open(filename, 'wb') as file:
            pickle.dump(application_data, file)