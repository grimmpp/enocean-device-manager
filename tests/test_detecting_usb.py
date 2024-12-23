import unittest
import sys 
import os
import asyncio

file_dir = os.path.join( os.path.dirname(__file__), '..', 'eo_man', 'data')
sys.path.append(file_dir)
__import__('homeassistant') 


from tests.mocks import AppBusMock

from eo_man.controller.serial_port_detector import SerialPortDetector



class TestDetectingUsbDevices(unittest.TestCase):

    @unittest.skip("Not yet compatible with Linux")
    def test_print_device_info(self):
        SerialPortDetector.print_device_info()

    @unittest.skip("Not yet compatible with Linux")
    def test_port_detection(self):
        spd = SerialPortDetector(AppBusMock())
        mapping = asyncio.run( spd.async_get_gateway2serial_port_mapping() )
        pass