import time
import unittest
import os
import pickle

from eo_man import load_dep_homeassistant
load_dep_homeassistant()


from eo_man.controller.app_bus import AppBus

from eo_man.data.data_manager import DataManager
from eo_man.data.application_data import ApplicationData


class TestLoadAndStoreAppConfig(unittest.TestCase):

    def test_load(self):
        app_bus = AppBus()
        dm = DataManager(app_bus)

        filename = os.path.join( os.path.dirname(__file__), 'resources', 'test_app_config_1.eodm')
        self.assertTrue(os.path.isfile(filename), f"{filename} is no valid filename.")
        dm.load_application_data_from_file(filename)

        self.assertEqual(22, len(dm.devices), "Loaded device count does not match!")
        

    def test_load_save_load(self):
        app_bus = AppBus()
        dm = DataManager(app_bus)

        filename = os.path.join( os.path.dirname(__file__), 'resources', 'test_app_config_1.eodm')
        self.assertTrue(os.path.isfile(filename), f"{filename} is no valid filename.")
        app_data:ApplicationData = dm.load_application_data_from_file(filename)

        filename2 = os.path.join( os.path.dirname(__file__), 'resources', 'test_app_config_1_temp.eodm')
        dm.write_application_data_to_file(filename2)

        self.assertTrue(os.path.isfile(filename2), f"{filename2} is no valid filename.")
        app_data2:ApplicationData = dm.load_application_data_from_file(filename2)
        
        filename3 = os.path.join( os.path.dirname(__file__), 'resources', 'test_app_config_1_temp2.eodm')
        dm.write_application_data_to_file(filename3)

        self.assertTrue(os.path.isfile(filename3), f"{filename3} is no valid filename.")
        app_data3:ApplicationData = dm.load_application_data_from_file(filename3)

        # compare app_data
        self.assertEqual(len(app_data.devices),                     len(app_data2.devices))
        self.assertEqual(len(app_data.data_filters),                len(app_data2.data_filters))
        self.assertEqual(len(app_data.selected_data_filter_name),   len(app_data2.selected_data_filter_name))
        # self.assertEqual(len(app_data.application_version),       len(app_data2.application_version))   # will not match after version change

        self.assertEqual(len(app_data2.devices),                    len(app_data3.devices))
        self.assertEqual(len(app_data2.data_filters),               len(app_data3.data_filters))
        self.assertEqual(len(app_data2.selected_data_filter_name),  len(app_data3.selected_data_filter_name))
        self.assertEqual(len(app_data2.application_version),        len(app_data3.application_version))
        
        # "binary" check
        self.assertEqual(pickle.dumps(app_data2), pickle.dumps(app_data3))
        