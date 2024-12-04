import inspect
import asyncio

from enum import Enum
from .. import LOGGER

class AppBusEventType(Enum):
    LOG_MESSAGE = 0                     # dict with keys: msg:str, color:str
    SERIAL_CALLBACK = 1                 # dict: msg:EltakoMessage base_id:str
    CONNECTION_STATUS_CHANGE = 2        # dict with keys: serial_port:str, baudrate:int, connected:bool
    DEVICE_ITERATION_PROGRESS = 3            # percentage 0..100 in float
    DEVICE_SCAN_STATUS = 4              # str: STARTED, FINISHED, DEVICE_DETECTED
    ASYNC_DEVICE_DETECTED = 5           # BusObject
    UPDATE_DEVICE_REPRESENTATION = 6    # busdevice
    UPDATE_SENSOR_REPRESENTATION = 7    # esp2  eltakomessage
    WINDOW_CLOSED = 8
    WINDOW_LOADED = 9
    SELECTED_DEVICE = 10                # device
    LOAD_FILE = 11
    WRITE_SENDER_IDS_TO_DEVICES_STATUS = 12
    SET_DATA_TABLE_FILTER = 13          # applies data filter to data table
    ADDED_DATA_TABLE_FILTER = 14        # adds data filter to application data
    REMOVED_DATA_TABLE_FILTER = 15      # remove data filter from application data
    ASYNC_TRANSCEIVER_DETECTED = 17     # type:str (FAM-USB), base_id:str 00-00-00-00
    SEND_MESSAGE_TEMPLATE_LIST_UPDATED = 18
    REQUEST_SERVICE_ENDPOINT_DETECTION = 19
    SERVICE_ENDPOINTS_UPDATES = 20     # fired when new services are detected

class AppBus():

    

    def __init__(self) -> None:
        self.handler_count = 0

        for event_type in AppBusEventType:
            if event_type not in self._controller_event_handlers.keys():
                self._controller_event_handlers[event_type] = {}


    _controller_event_handlers={}
    def add_event_handler(self, event:AppBusEventType, handler) -> int:
        self.handler_count += 1
        self._controller_event_handlers[event][self.handler_count] = handler
        return self.handler_count
    
    def remove_event_handler_by_id(self, handler_id:int) -> None:
        for et in AppBusEventType:
            if handler_id in self._controller_event_handlers[et]:
                del self._controller_event_handlers[et][handler_id]
                break

    def fire_event(self, event:AppBusEventType, data) -> None:
        # print(f"[Controller] Fire event {event}")
        for h in self._controller_event_handlers[event].values(): 
            try:
                if inspect.iscoroutinefunction(h):
                    asyncio.run(h(data))
                else:
                    h(data)
            except:
                LOGGER.exception(f"Error handling event {event}")
                

    async def async_fire_event(self, event:AppBusEventType, data) -> None:
        # print(f"[Controller] Fire async event {event}")
        for h in self._controller_event_handlers[event].values(): 
            try:
                if inspect.iscoroutinefunction(h):
                    await h(data)
                else:
                    h(data)
            except:
                LOGGER.exception(f"Error handling event {event}")