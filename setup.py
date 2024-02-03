import os
from setuptools import setup, find_packages
from distutils.core import setup
import shutil
import re


base_dir = os.path.dirname(__file__)

# with open(os.path.join(base_dir, 'README.md'), encoding="utf-8") as f:
with open('README.md', encoding="utf-8") as f:
    long_description = f.read()

# with open(os.path.join(base_dir, 'LICENSE'), encoding="utf-8") as f:
with open('LICENSE', encoding="utf-8") as f:
    license = f.read()

# req_fn = os.path.join(base_dir, 'requirements.txt')
# if not os.path.isfile(os.path.join(os.getcwd(), 'requirements.txt')):
#     shutil.copyfile(os.path.join(base_dir, 'requirements.txt'), os.path.join(os.getcwd, 'requirements.txt'))

# .\.venv\Scripts\pip.exe  freeze | Out-File -Encoding UTF8 requirements.txt
# check if file is really in utf-8
# req_fn = os.path.join(base_dir, 'requirements.txt')
# with open(req_fn, encoding='utf-8') as f:
#     required = f.read().splitlines()
    
# with open(os.path.join(os.getcwd(), 'requirements.txt'), encoding='utf-8') as f:
#     f.writelines(required)

required = ['eltako14bus==0.0.45', 'pyserial', 'pyserial-asyncio', 'aiocoap', 
            # 'homeassistant', 
            'pyyaml', 
            'termcolor', 'strenum', 'pillow', 'numpy', 'tzlocal', 'tkinterhtml']

setup(
    name='eo-man',
    version='0.1-rc1',
    package_dir={'':"eo-man"},
    # packages=find_packages("./eo-man"),
    package=['view', 'data', 'controller', 'icons'],
    package_data={'': ['*.png']},
    include_package_data=True,
    install_requires=required,
    author="Philipp Grimm",
    description="Tool to managed EnOcean Devices and to generate Home Assistant Configuration.",
    long_description=long_description,
    long_description_content_type='text/markdown',
    license=license,
    url="https://github.com/grimmpp/enocean-device-manager",
    python_requires='>=3.7',
)
