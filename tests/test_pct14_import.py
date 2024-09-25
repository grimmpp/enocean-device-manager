import unittest

from eo_man import load_dep_homeassistant
load_dep_homeassistant()

from eo_man.data.pct14_data_manager import PCT14DataManager

class TestPCT14Import(unittest.IsolatedAsyncioTestCase):

    async def test_import(self):
        devices = await PCT14DataManager.get_devices_from_pct14('./tests/resources/20240925_PCT14_export_test.xml') 

        self.assertEqual(len(devices), 58)
        self.assertEqual(len([d for d in devices.values() if d.bus_device]), 9)