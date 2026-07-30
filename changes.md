# Change Log

## Cover Travel Time Test: the taught-in switch is optional again
* `--cover_ids` accepts `ACTUATOR_ID[:SWITCH_ID[+SWITCH_ID...]][:SENDER_ID]` now, so a cover can be given as `00-00-00-05` when no wall switch is taught into it or when it is not needed for the test.
* `ACTUATOR_ID:SENDER_ID` (e.g. `00-00-00-06:00-00-B0-06`) is understood as a cover without a switch instead of being rejected: the address the test sends from cannot be a switch. Only a switch list which mixes real switches with the sender id is still an error.
* Without a switch and with an explicit sender id: `00-00-00-05::00-00-B0-05`.

## Marker switch: shows the pressed button, two fixes
* The marker table has a `button` column now, so you can see which button of the rocker switch was pressed (AI, A0, BI, B0) and use the four buttons of one switch for different things.
* Fixed that the release telegram of a switch was listed as an additional marker. Every press produced two entries, which doubled the number of markers.
* Two presses are only a double press when the **same** button was used. Before, pressing e.g. `AI` and then `B0` within the time window was taken as one manual end position detection.

## Colored headline on the command line
* The ASCII art headline is shaded from a bright top edge down to a dark bottom, which makes it look lit from above. Shown on the help page (`-h`) and in the startup banner.
* Color is only used when the output really goes to a terminal. Piped output, the log file and `--log_file` keep the plain headline without escape sequences.

## Fixed DeprecationWarning when started without `-m`
* Starting the application as a directory or file (`python eo_man`, `python eo_man/__main__.py`) printed `DeprecationWarning: __package__ != __spec__.parent` for every relative import. `__main__.py` set `__package__` unconditionally, which contradicted the `__spec__` of a plain script.
* The bootstrap only runs now when the module is really not part of its package, and it keeps `__package__` and `__spec__` consistent. `python -m eo_man` is unaffected.

## Cover Travel Time Test: verified against real hardware (FSB14 on FGW14-USB)
* Those actuators send **no** 4BS travel report at all, only RPS status telegrams. The `reported` column therefore stays empty and the measured time is the relevant one. Documented accordingly.
* The RPS values `0x01` / `0x02` are the start of an upward / downward movement. They are decoded now ("cover started to move UP") and used as the direction the actuator really moved, so the `dir` column and the check for a wrong direction work with those actuators as well.
* The `difference` column of the marker table stayed empty because it was calculated from the missing travel report. It falls back to the measured travel time now (column renamed from `reported` to `travel`).
* Fixed that a colon instead of a comma between two sequence entries (`down:12:pause:2`) silently dropped the following entries instead of reporting the typo.
* The actuator address in the switch position of `--cover_ids` is rejected now, a sender id there is taken as the sender of a cover without a switch - both would otherwise silently be treated as a taught-in switch.

## Cover Travel Time Test: marker switch for a manual end position detection
* New optional argument `--cover_marker_switch` (`-cms`): a switch which is **not** taught into any actuator and therefore does not move anything. Its telegrams never count as an interference.
* Pressing it **once** records a point in time and the report shows how long the cover had been moving at that moment.
* Pressing it **twice in a row** (within `--cover_marker_double_press_time`, default 1.5s) is a manual end position detection: an FSB actuator simply runs its configured runtime and does not notice when the cover physically stops, so this is the only way to measure the travel time the cover really needed. The first press of the pair counts.
* The report got a section `MARKER SWITCH` which compares the manually measured time with the time the actuator reported, a `manual end` column in the travel time statistics, and the runtime recommendation prefers the manually measured value.

## Cover Travel Time Test: the taught-in switch is required per cover
* `--cover_ids` now expects `ACTUATOR_ID:SWITCH_ID[+SWITCH_ID...][:SENDER_ID]`, e.g. `00-00-00-05:FE-D4-E9-47`. The wall switch which is taught into the actuator has to be given, several switches of one cover are separated by `+`. The optional sender id moved to the third position.
* A press of a declared switch now only marks the movements of the cover(s) that switch really operates. Before, every foreign telegram disturbed **all** covers which were moving, so one switch press invalidated the measurement of the whole test run.
* Telegrams of declared switches are reported as `switch`, everything else as `unknown` (`stopped by: switch FE-D4-E9-47` vs. `unknown 00-00-00-42`). Unknown telegrams still count as a possible interference of every running movement and the report names the addresses and explains what to do about them.

## Restructured the command line help page
* `python -m eo_man -h` groups the arguments now by topic (general, gateway connection, device data and one group per command) instead of showing one long flat list.
* Added a list of the available commands and ready to use examples for every command at the end of the help page.
* Shortened the usage line, clearer help texts and the defaults are mentioned where relevant.
* Fixed the default of `--device_type`: it was `fgw14-usb` which is not one of the valid choices, so it could not be resolved to a gateway type. It is `fgw14usb` now (same connection behaviour, but the gateway is named correctly in the log).

## Telegram Monitor (`enocean_logger`) improvements
* New argument `--log_file` (`-lf`) writes the whole log output including the received telegrams into a file of your choice. The file is appended, so a restart does not lose the previous log.
* Fixed `--log_telegram_id_filter` (`-idf`): the already parsed id list was converted to a string again, so the filter never matched and **no** telegram at all was displayed as soon as a filter was given.
* Fixed the `EOFError` traceback when the logger is started without an interactive console (background process, service, `nohup`). It now logs a hint that the process has to be terminated to stop it and keeps on logging.
* The command now reports a clear error and ends with exit code 1 if no serial port was given or the gateway cannot be reached (before it continued and ran into a `NameError`).
* The built-in log file `enocean-device-manager.log` is written with UTF-8 encoding so that special characters (e.g. the signal strength bars) cannot break the log output.
* Documentation extended: how to run the monitor as a background process, screen/tmux session, systemd service or hidden Windows process, how to follow the log file live and a troubleshooting table. See [docs/commandline-enocean-logger](https://github.com/grimmpp/enocean-device-manager/blob/main/docs/commandline-enocean-logger).

## Added Cover Travel Time Test
* New command line test `--command cover_test` which drives a list of covers (FSB14, FSB61, FJ62, ...) with a configurable sequence of movement commands and pauses.
* All given cover ids get exactly the same commands. Sent commands and received telegrams are logged with timestamps.
* The report shows per movement the reaction time, the measured and the actuator-reported travel time, the reached end position and how the movement was terminated.
* Foreign telegrams (e.g. wall switches) are logged. Interferences during a movement are marked and the travel time until the intervention is reported, so a switch can also be used on purpose to stop a cover and measure the travel time.
* Travel times are summarized per cover and direction including a hint which runtime has to be configured in the actuator.
* The result is printed as colored and aligned tables directly on the command line and ends with a one-line verdict. It can be saved with `--test_report` (text) and `--test_report_csv` (telegrams).
* The delay between two command telegrams can be set once with `--cover_message_delay` (`-cmd`). Default is 0.1s (100ms), `0` sends the commands without any delay. It is only applied between the telegrams, never before the first one of a step, so it does not shift the measured travel times.
* Without `-v` only the result is shown. `-v` logs every relevant telegram while the test runs and appends the complete telegram log, `-vv` additionally shows the raw ESP2 data.
* Fixed that `-v` never changed the log level of `esp2_gateway_adapter` and `eltakobus.serial` (the verbosity was not passed to the logger setup and the second level was unreachable).
* README: reworked how to run the application directly out of the repository and added examples for the user interface and all command line tools. The documented `setup.py install`, `setup.py bdist_wheel` and `python -m eo_man demo.eodm` did not work anymore (there is no `setup.py` and the configuration file has to be passed via `-c`).

## v0.1.57 Added Script for building exe file

## v0.1.56 Made Echo Tests for FAM14 detection optional

## v0.1.55 PCT14Export improved

## v0.1.54 Broken message handling fixed

## v0.1.53 Added new lib eltako14bus version for additional FSB14 type

## v0.1.52 Device Detection Improved

## v0.1.51 Improved Linux compatibility

## v0.1.50 Added Burst Tests for checking if all telegrams appear on the bus

## v0.1.47 Added Log exceptions for broken EnOcean Telegrams
* Little improvements for Linux added.

## v0.1.46 Prepared EnOcean Logger for Linux

## v0.1.45 Commandline EnOcean Logger with filter for specific EnOcean Telegram Ids

## v0.1.44 Fixed config generation for lan gateways

## v0.1.42 Fixed dependencies

## v0.1.41 HA Config Generation Fix for USB300
* device type of USB300 was wrong
* Getting started docs improved.

## v0.1.40 Dependency Fix
* Updated to current lib of esp2-gateway-adapter 0.2.18

## v0.1.39
* Support for EUL-2PJ3Q tcm515 added. https://busware.de/tiki-index.php?page=EUL
* Clean up of device table implemented
* Made ESP3 LAN gateway more reactive
* Improved communication of remote connection to Home Assistant
* Added binary output optionally to logout put
* Improved installation script
* Migration function/compatibility for loading older data added.

## v0.1.38 Remote detection of messages and gateways in Home Assistant

## v0.1.37 Fixed new packaging
* Fixed missing files in 0.1.36
* Green background removed from buttons in toolbar

## v0.1.36 Added Extending PCT14 Export
* Changed package build description from setup.py to toml
* Added install scripts for windows
* Added install script for ubuntu (detecting of gateway devices is still not working under linux)
* Added extending PCT14 export

## v0.1.35 Loading PCT14 Export
* Loading exported data from PCT14 introduced.
* eo_man can now take EEP from TeachIn telegram and pre-configure device.

## v0.1.34 Added more configuration templates for devices
* Added more configuration templates for devices
* Fixed configuration for FMZ
* Fixed send message for fired gateways
* Improved writing sender ids into actuators for EEP F6-02-01/02
* Added List for supported devices.
* Configuration Checks which are made before generating Home Assistant Configuration can be ignored.

## v0.1.33 Added Supported Device View
* Improved template selection in Details View. 
* Improved GUI Details View

## v0.1.30 Extended device list
* Extended device list with EEP mapping
* Fixed sender id duplication check.

## v0.1.29 Added FGD14 and FD2G14 Support
* Added FGD14 and FD2G14 Support
* Fixed missing dependency for FSR14M-2x support.
* Fixed configuration generation and sender id validation.

## v0.1.28 added EEP F6-01-01

## v0.1.27 Added Support for FSR14M-2x
* Added support for FSR14M-2x. Switch/light and power meter are represented as separate entities.
* Fixed sender ids for bus gateways
* Introduced validation for auto-generated configuration before exporting it.
* Prepared configuration option for Home Assistance base_id.

## v0.1.26 Fixed LAN Gateway Connection
* For reconnecting lan gateway you still need to wait for 10sec

## v0.1.25 Fixed Gateway Detection
* Bug-fix for gateway detection. 

## v0.1.24 Added Support for FHK14, F4HK14 and FTD14
* Added support for Eltako devices: FHK14, F4HK14 and FTD14
* Config generation for MGW Gateway (LAN) extended

## v0.1.23 Support for MGW Gateway
* Added support for [MGW Gateway](https://www.piotek.de/PioTek-MGW-POE) (ESP3 over LAN)

## v0.1.21 EEP representation bug fixes
* Ignores unknown devices
* Fixed EEP representation in dorp down
* Preparation for FDG14 detection

## v0.1.20 Bug-fix for detection of FSR14_2x

## v0.1.19 Added EEP A5-30-01 and A5-30-03
* Added EEPs for digital input

## v0.1.18 Bug-fix for USB300 detection
* Bug-fix USB300 detection
* Typos removed

## v0.1.17 Bug-Fix missing dependency in v0.1.16
* added dependency `esp2_gateway_adapter`

## v0.1.16 Improved send message and program devices (DELETED)
* Support for programming different baseId for HA sender into devices on bus.
* Enabled FMZ14 and FAE14SSR to be programmed. 
* Added template list for messages to be sent
* Added lib for ESP3 (USB300) support. (https://github.com/grimmpp/esp2_gateway_adapter)

## v0.1.15 Fixed Send Message
* Send Message Window improved and fixed.
* Added button in toolbar for send message window.

## v0.1.13 Send Message Window Improved
* Improved send messages tool.
* fixed log rotation
* Improved ESP3. Sending is working but not for gateway commands like A5-38-08 which is needed to control lights.

## v0.1.12 Send Message Window added
* Small tool to send messages added.

## v0.1.11 EEP Checker added
* Small tool added to check EEP values of a data set.

## v0.1.10 Logs are sent into file
* Logs are now written to log file in application folder.
* Added Flag to see values from incomming telegrams.

## v0.1.9 Read Support for USB300 + Multi-Gateway Support for HA Config Export
* Fixed compatibility of loading old application configs
* Icons added
* Remove Smart Home addresses as real buttons from HA export
* Serial port detection for FAM-USB and USB300 improved.
* TODO: Cleanup of ESP3 communication, move function into lib

## v0.1.8 Wireless Transceiver Support
* Reset suggested HA settings added
* Support for FAM-USB. Is now detected as gateway and contained in HA config 
* **Experimental** Support for USB300. CODE CLEANUP HEAVILY NEEDED!!!

## v0.1.7 F2SR14 Support
* Support for F4SR14 added
* Update Button added

## v0.1.6 Sensor Values are evaluated
* Sensor values are displayed in command line
* Sponsor button added
* Docs updated with system requirements
* Added links to documentation
* Improved look and feel
* About window improved
* Icons to menu added
* Unmapped devices are moved to FAM14 after connection.
* Error handling added for serial connection.

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