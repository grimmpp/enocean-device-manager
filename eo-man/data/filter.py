from .device import Device

class DataFilter():

    def __init__(self, name:str, 
                 global_filter:list[str]=[], 
                 device_address_filter:list[str]=[],
                 device_external_address_filter:list[str]=[],
                 device_type_filter:list[str]=[],
                 device_eep_filter:list[str]=[]):
        self.name = name
        self.global_filter = global_filter
        self.device_address_filter = device_address_filter
        self.device_external_address_filter = device_external_address_filter
        self.device_type_filter = device_type_filter
        self.device_eep_filter = device_eep_filter

    
    def filter_device(self, device:Device):
        # check address
        for f in self.device_address_filter + self.global_filter:
            if device.address and f.upper() in device.address.upper():
                return True
        
        # check external id
        for f in self.device_external_address_filter + self.global_filter:
            if device.external_id and f.upper() in device.external_id.upper():
                return True
            
        # check device type
        for f in self.device_type_filter + self.global_filter:
            if device.device_type and f.upper() in device.device_type.upper():
                return True
        
        # check eep
        for f in self.device_eep_filter + self.global_filter:
            if device.eep and f.upper() in device.eep.upper():
                return True
            
        for f in self.global_filter:
            # key function
            if device.key_function and f.upper() in device.key_function.upper():
                return True
            
            # comment
            if device.comment and f.upper() in device.comment.upper():
                return True
            
            # version
            if device.version and f.upper() in device.version.upper():
                return True
            
            # ha platform
            if device.ha_platform and f.upper() in device.ha_platform.upper():
                return True

            if self.find_in_dict(device.additional_fields, f.upper()):
                return True

        return False
    
    
    def find_in_dict(self, additional_fields:dict, filter:str) -> bool:
        for key, value in additional_fields.items():
            if isinstance(value, dict):
                if self.find_in_dict(value, filter):
                    return True
            elif filter in str(value).upper():
                return True
        return False