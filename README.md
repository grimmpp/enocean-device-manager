[![Generic badge](https://img.shields.io/github/commit-activity/y/grimmpp/home-assistant-eltako.svg?style=flat&color=3498db)](https://github.com/grimmpp/home-assistant-eltako/commits/main)
[![Generic badge](https://img.shields.io/badge/Community-Forum-3498db.svg)](https://community.home-assistant.io/)
[![Generic badge](https://img.shields.io/badge/Community_Forum-Eltako_Integration_Debugging-3498db.svg)](https://community.home-assistant.io/t/eltako-baureihe-14-rs485-enocean-debugging/49712)
[![Generic badge](https://img.shields.io/badge/License-MIT-3498db.svg)](/LICENSE)

# Enocean Device Manager and Home Assistant Configuration Exporter

A desktop application to **inventory, analyse and document an EnOcean installation** - and to **generate the
Home Assistant configuration** out of it.

What it does:

* **Detects the devices automatically.** The memory of the bus devices (Eltako series 14) is read out via
  FAM14, and every telegram which is received on the bus or in the wireless network adds the sensors and
  decentralized devices which are not on the bus.
* **Shows how the installation is wired.** For every actuator you see which sensors are taught into its
  memory, with key, key function, channel and function group - and for every sensor in which actuators it is
  entered. Related devices are highlighted in the table, an incoming telegram makes its device blink.
* **Lets you enrich the data**: name, comment and the parameters of a device (timeframes, thresholds, units,
  ...), and the settings which Home Assistant needs. Sensible defaults are suggested automatically.
* **Exports the configuration for Home Assistant**, intended for the
  [Eltako Home Assistant Integration](https://github.com/grimmpp/home-assistant-eltako/). The inventory itself
  is stored in an application configuration (`.eodm`), and an existing PCT14 export can be imported.
* **Brings command line tools** to analyse and test an installation without the user interface (see below):
  a live telegram monitor, a cover travel time test, a bus burst test and the configuration export.

It runs independently of Home Assistant and connects to the installation via an Eltako FAM14, FGW14(-USB) or
FAM-USB, via an ESP3 transceiver (EnOcean USB300/USB500) or via a LAN gateway.

This project grows with the installations it is used on. Not every EnOcean device is supported yet - if one of
yours is missing or something does not work, please open an [issue](/issues).

## Not only a user interface: command line tools included

Beside the desktop application the same package provides a few command line tools which work without the user
interface. They are selected with `--command` (`-C`) and are useful to analyse and test an installation:

```shell
# live telegram monitor: show every telegram on the bus / in the wireless network
python -m eo_man -C enocean_logger -sp COM7 -dt fgw14usb

# ... only the telegrams of two devices and additionally written into a file
python -m eo_man -C enocean_logger -sp COM7 -dt fgw14usb -idf FE-D4-E9-47,FE-D4-E9-48 -lf telegrams.log

# measure the travel times of covers and get the runtime to configure in the actuator
python -m eo_man -C cover_test -sp COM7 -dt fgw14usb -cid 00-00-00-05 -cseq up:60,pause:5,down:60

# check if all telegrams which are sent to the bus really arrive (needs two gateways)
python -m eo_man -C burst_test -sp COM7 -dt fam14 -sp2 COM8 -dt2 fgw14usb

# generate the Home Assistant configuration out of a stored inventory
python -m eo_man -C generate_ha_config -c my_config.eodm -ha ha_config.yaml
```

Every tool prints its result directly on the command line, `-h` shows all arguments with further examples.
More about them in [Use Command Line](#use-command-line) at the end of this page.

## Preview
<img src="https://github.com/grimmpp/enocean-device-manager/blob/main/screenshot2.png" /> 
Everything you see here is detected automatically by reading the memory of the bus devices via FAM14. Telegrams
of sensors and decentralized devices are received and added on top of that, and the information Home Assistant
needs is filled in with sensible defaults. All of it can be edited afterwards and exported as a Home Assistant
configuration.

## System Requirements / Where to install and how to use it?
This tool is a desktop application (not browser based) and it runs independent of Home Assistant. Install it directly on Windows, Linux or macOS. Your PC requires Python (>= 3.12) pre-installed and you should be able to connect it to your EnOcean devices, either via USB cable (Eltako FAM14, FGW14-USB, ...), via a wireless transceiver (Eltako FAM-USB, EnOcean USB300/USB500) or via a LAN gateway.

Most of the work is done at your desk. Only the device scan needs a connection to the FAM14, so a laptop which you can bring close to the bus for a moment is the most comfortable setup. Afterwards you keep working on the stored inventory (`.eodm`) without any hardware.

## Install python package in virtual environment (Recommended)
1. Create virtual python environment: `python.exe -m venv .\.venv`
2. Install application: `.\.venv\Scripts\pip.exe install eo_man  --force-reinstall` (Package available under pypi: [eo_man](https://pypi.org/project/eo-man/))
3. Run application: `.\.venv\Scripts\python.exe -m eo_man`

## Install python package in gloabl environment
1. Install application: `pip.exe install eo_man` (Package available under pypi: [eo_man](https://pypi.org/project/eo-man/))
2. Run application: `python.exe -m eo_man`

## Run directly from this repository (alternative, recommended for testing)

The package does not need to be installed - the code can be executed straight out of the repo.

1. Clone the repo and change into its directory:

   ```shell
   git clone https://github.com/grimmpp/enocean-device-manager.git
   cd enocean-device-manager
   ```

2. Create a virtual environment for python:
   * Windows: `python.exe -m venv .venv`
   * Linux/Mac: `python3 -m venv .venv`
3. Install the dependencies:
   * Windows: `.\.venv\Scripts\pip.exe install -r requirements.txt`
   * Linux/Mac: `./.venv/bin/pip install -r requirements.txt`
4. Start it **from the repo directory** so that the local `eo_man` package is used:
   * Windows: `.\.venv\Scripts\python.exe -m eo_man`
   * Linux/Mac: `./.venv/bin/python -m eo_man`

For an update you only need `git pull` (and `git checkout BRANCH_NAME` to change the branch). Repeat step 3 if
the dependencies in `requirements.txt` have changed.

All examples below are written as `python -m eo_man`. Replace `python` by the interpreter of your virtual
environment (`.\.venv\Scripts\python.exe` or `./.venv/bin/python`) and stay in the repo directory.

### Start the user interface

```shell
# start with an empty inventory
python -m eo_man

# start and directly load an application configuration (e.g. the included demo data)
python -m eo_man -c demo.eodm

# start and directly import a configuration which was exported by PCT14
python -m eo_man -pct14 my_pct14_export.xml
```

The application configuration must end with `.eodm`, the PCT14 export with `.xml`. Everything else is done in
the user interface: connect the gateway, scan the bus, enrich the devices and export the Home Assistant
configuration.

### Example: measure the travel times of covers (`cover_test`)

Drives all given covers with the same sequence of movement commands and pauses and reports how long each of
them really moved. This is what you need to configure the runtime of an FSB actuator properly.

Every cover is given as `ACTUATOR_ID` or, together with the wall switch which is taught into it, as
`ACTUATOR_ID:SWITCH_ID`. Giving the switch lets the test assign a press during the run to the right cover
instead of counting it as interference of all covers.

```shell
# covers 5 and 7 on a FGW14-USB: drive up for 60s, pause, drive down for 60s, pause
python -m eo_man -C cover_test -sp COM7 -dt fgw14usb \
                 -cid 00-00-00-05,00-00-00-07 \
                 -cseq up:60,pause:5,down:60,pause:5

# the same test with the taught-in wall switches of the two covers
python -m eo_man -C cover_test -sp COM7 -dt fgw14usb \
                 -cid 00-00-00-05:FE-D4-E9-47,00-00-00-07:FE-D4-E9-48 \
                 -cseq up:60,pause:5,down:60,pause:5

# same test on Linux, repeated 3 times, with every telegram and saved to files
python -m eo_man -C cover_test -sp /dev/ttyUSB0 -dt fgw14usb \
                 -cid 00-00-00-05:FE-D4-E9-47,00-00-00-07:FE-D4-E9-48 \
                 -cseq up:60,pause:5,down:60,pause:5 -trc 3 -v -tr cover_test.txt -tcsv cover_test.csv

# a cover with two taught-in switches and a custom sender id, without delay between the commands
python -m eo_man -C cover_test -sp COM7 -dt fgw14usb \
                 -cid FF-AA-BB-01:FE-D4-E9-47+FE-D4-E9-48:00-00-B0-07 -cseq up:60,pause:5 -cmd 0

# with a marker switch (not taught into the actuator) to measure the real end position by hand
python -m eo_man -C cover_test -sp COM7 -dt fgw14usb -cid 00-00-00-05:FE-D4-E9-47 \
                 -cseq up:90,pause:5,down:90,pause:5 -cms FF-11-22-33
```

An FSB actuator does not notice when the cover physically reaches its end position - it simply runs its
configured runtime. Watch the cover and press the **marker switch** twice in a row at the moment it really
stops: that time is reported as the travel time the cover needed and is used for the runtime recommendation.
A single press just records a point in time, e.g. when the slats of a venetian blind are closed.

The result is printed as tables on the command line:

```text
run | step | cover       | command    |  react | measured | reported | dir  | end | stopped by           | result
-----------------------------------------------------------------------------------------------------------------
  1 |    1 | 00-00-00-05 | UP 60s     | 19.40s |   19.40s |    19.4s | UP   | TOP | top end position     | OK
  1 |    3 | 00-00-00-05 | DOWN 60s   | 21.21s |   21.21s |    21.2s | DOWN | BOT | bottom end position  | OK

 Cover 00-00-00-05: up 19.4s, down 21.2s -> configure a runtime of at least 21.2s
   difference between up and down: 1.8s. ...

 RESULT: all 6 movements behaved as requested.
```

You can operate the covers with their wall switch while the test runs: such interferences are logged and the
travel time until the intervention is reported. That movement is marked as `interrupted`, which means that a
switch telegram arrived while the cover was still moving - the measured travel time up to that moment stays
valid, but the movement is not used for the runtime recommendation. Because the switches are declared per cover,
only the cover which that switch operates is marked; the other covers keep their clean measurement. Details, all
options and how to read the report:
[Cover Travel Time Test](https://github.com/grimmpp/enocean-device-manager/blob/main/docs/cover_travel_test).

### Example: live telegram monitor (`enocean_logger`)

Prints every telegram which appears on the bus or in the wireless network until the process is stopped
(`Enter` or `Ctrl+C`).

```shell
python -m eo_man -C enocean_logger -sp COM7 -dt fgw14usb

# show only the telegrams of the given ids
python -m eo_man -C enocean_logger -sp COM7 -dt fgw14usb -idf FE-D4-E9-47,FE-D4-E9-48

# additionally write everything into a file
python -m eo_man -C enocean_logger -sp COM7 -dt fgw14usb -lf telegrams.log
```

How to run it as a background process or service, how to follow the file live and troubleshooting:
[EnOcean Logger for Commandline](https://github.com/grimmpp/enocean-device-manager/blob/main/docs/commandline-enocean-logger).

### Example: generate the Home Assistant configuration without the user interface

```shell
python -m eo_man -C generate_ha_config -c my_config.eodm -ha ha_config.yaml
```

## Bugs and Features 
Please open [issues](/issues) if you encounter bugs or if you have ideas for new features. Also quite a lot of devices are not yet supported.

## Run unittests
`pytest tests`

## Install pre-commit hook to ensure unittests are executed before each commit
1. Install package `pip install pre-commit`
2. Config git: `pre-commit install`

## Build wheel package
1. Install the build tool: `pip install build`
2. Build the package: `python -m build --wheel` (result is put into `dist/`)

## Install built wheel pacage
`pip install dist/eo_man-VERSION-py3-none-any.whl` use `--force-reinstall` if you want to overwrite an existing version.

# Use Command Line
Beside the user interface the application provides command line tools which are selected with `--command`.
Ready to use examples are shown above in [Run directly from this repository](#run-directly-from-this-repository-alternative-recommended-for-testing).
All arguments are listed by `python -m eo_man -h`.

Command line tools:

* [EnOcean Logger](https://github.com/grimmpp/enocean-device-manager/blob/main/docs/commandline-enocean-logger) (`--command enocean_logger`): Live telegram monitor. Displays all telegrams which appear on the bus or in the wireless network, optionally filtered by device id and written into a file (`--log_file`). Can be run as a background process or service.
* [Bus Burst Tester](https://github.com/grimmpp/enocean-device-manager/blob/main/docs/burst_test) (`--command burst_test`): Checks if all telegrams sent to the bus are delivered.
* [Cover Travel Time Test](https://github.com/grimmpp/enocean-device-manager/blob/main/docs/cover_travel_test) (`--command cover_test`): Drives covers (FSB14, FSB61, ...) with a configurable sequence of movement commands and pauses and reports the travel times per direction so that the runtime of the actuator can be configured properly.
* Home Assistant configuration export (`--command generate_ha_config`): Generates the Home Assistant configuration out of a stored application configuration without starting the user interface.

Every command prints its result on the command line. `-v` adds the telegrams and the debug log of the serial
communication, `-vv` additionally the raw ESP2 data.

# [Changelog](https://github.com/grimmpp/enocean-device-manager/blob/main/changes.md)

# Contribution and Support to this Project
I'm really happy to provide a more and more growing Home Assistant Eltako Integration and tools like this which extend this automation corner even more. The size of this integration is getting much bigger than the use cases I've realized at home, the variety of supported devices is increasing and the stability of the integraiton is getting to a professional level. On the other side it is getting hard to keep this level of development speed and operational quality. I'm about to build up a professional development and testing environment so that the quality can even improved and futher features can still be delivered in a short time frame. 

In general, you can contribute to this project by:
* Support users in the Home Assistant Community ([Eltako “Baureihe 14 – RS485” (Enocean) Debugging](https://community.home-assistant.io/t/eltako-baureihe-14-rs485-enocean-debugging))
* Reporting [Issues]([/issue](https://github.com/grimmpp/home-assistant-eltako/issues))
* Creating [Pull Requests](https://github.com/grimmpp/home-assistant-eltako/pulls)
* Providing [Documentation](https://github.com/grimmpp/home-assistant-eltako/tree/main/docs)
