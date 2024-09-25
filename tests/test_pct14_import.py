import unittest

from eo_man import load_dep_homeassistant
load_dep_homeassistant()

from eo_man.data.pct14_data_manager import PCT14DataManager

class TestPCT14Import(unittest.IsolatedAsyncioTestCase):

    async def test_import(self):
        devices = await PCT14DataManager.get_devices_from_pct14('./tests/resources/20240925_PCT14_export_test.xml') 

        self.assertEqual(len(devices), 64)
        self.assertEqual(len([d for d in devices.values() if d.bus_device]), 15)


    async def test_write_sender_ids_into_existing_pct_export(self):
        devices = await PCT14DataManager.get_devices_from_pct14('./tests/resources/20240925_PCT14_export_test.xml') 

        await PCT14DataManager.write_sender_ids_into_existing_pct14_export(
            source_filename='./tests/resources/20240925_PCT14_export_test.xml',
            target_filename='./tests/resources/20240925_PCT14_export_test_GENERATED.xml',
            devices=devices,
            base_id='00-00-B0-00')