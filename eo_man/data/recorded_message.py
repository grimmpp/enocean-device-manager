from datetime import datetime
from eltakobus.message import ESP2Message

class RecordedMessage():

    def __init__(self, message:ESP2Message, external_id:str, gateway_id:str) -> None:
        self.message:ESP2Message = None
        self.external_device_id:str = external_id
        self.received_via_gateway_id: str = gateway_id
        self.received = datetime.now()