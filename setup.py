import os
from setuptools import setup, find_packages
from distutils.core import setup



base_dir = os.path.dirname(__file__)

# with open(os.path.join(base_dir, 'README.md'), encoding="utf-8") as f:
with open('README.md', encoding="utf-8") as f:
    long_description = f.read()

# with open(os.path.join(base_dir, 'LICENSE'), encoding="utf-8") as f:
with open('LICENSE', encoding="utf-8") as f:
    license = f.read()

required = ['eltako14bus==0.0.46', 'requests==2.31.0', 'enocean==0.60.1', 'pyserial', 'pyserial-asyncio', 'aiocoap', 
            # 'homeassistant', 
            'pyyaml', 
            'termcolor', 'strenum', 'pillow', 'numpy',
            # 'tzlocal', 
            'tkinterhtml']



setup(
    name='eo_man',
    version='0.1.10',
    package_dir={'eo_man':"eo_man"},
    # packages=find_packages("./eo-man"),
    #package_data={'': ['*.png']},
    package_data={'': ['icons/*']},
    package=["eo_man"],
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

#python setup.py bdist_wheel
