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

# with open(os.path.join(base_dir, 'requirements.txt'), encoding="utf-16") as f:
with open('requirements.txt', encoding="utf-16") as f:
    required = f.read().splitlines()


setup(
    name='eo-man',
    version='0.0',
    package_dir={'':"eo-man"},
    packages=find_packages("./eo-man"),
    install_requires=required,
    author="Philipp Grimm",
    description="Tool to managed EnOcean Devices and to generate Home Assistant Configuration.",
    long_description=long_description,
    long_description_content_type='text/markdown',
    license=license,
    url="https://github.com/grimmpp/enocean-device-manager",
    python_requires='>=3.7',
)
