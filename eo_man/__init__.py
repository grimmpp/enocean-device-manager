import os
import sys
import logging

LOGGER = logging.getLogger()

def load_dep_homeassistant():
    # import fake homeassistant package
    file_dir = os.path.join( os.path.dirname(__file__), 'data')
    sys.path.append(file_dir)
    __import__('homeassistant')