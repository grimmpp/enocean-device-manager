# Change Log

## v0.1.6 
* Sponsor button added
* Docs updated with system requirements
* Added links to documentation

## v0.1.5 Refactoring + Basic Features (GOAL: Stability)
* Improved imports incl. homeassistant mock
* Changed application output format to yaml. **=> Braking Change**
* Refactored Home Assistant Configuration Exporter
* Created start file for windows (eo-man.bat) which can be used to create a shortcut for e.g. the taskbar.
* Changed folder structure (renamed 'eo-man' to 'eo_man' which allows using package name.)  **=> Braking Change**
* Introduced tests
* Introduced cli commands
* Added possibility to only use command line to generate Home Assistant Configuration
* Application info added
* Application info and description added to auto-generated Home Assistant configuration.
* python pre-commits added to ensure unittests are executed successfully before every commit. 

## v0.1.4 Bug fixed in python package
* Bug in python package fixed

## v0.1.1 Bug Fix and values in log view
* 🐞 Missing function added from refactoring 🐞
* 💎 Added values for incoming messages which are displayed in log view.