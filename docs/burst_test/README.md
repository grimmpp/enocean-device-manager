# Bus Burst Tester

This is a small command-line tool that allows you to test the performance of the bus. The test procedure sends a series of telegrams to the bus via an FGW14 or FGW14-USB and verifies their successful delivery by reading them back from the bus using a FAM14, FGW14, or FGW14-USB.

## Command

`python.exe -m eo_man --command burst_test --serial_port SERIAL_PORT_WRITE --device_type fgw14 --serial_port2 SERIAL_PORT_READ -device_type2 fam14 --test_run_count 10 --message_delay 0.05`

Device specified with `serial_port` and `device_type` will write the telegrams to the bus.
Device specified with `serial_port2` and `device_type2` will read the telegrams to the bus. 
Valid values for `serial_port` and `serial_port2`: e.g. /dev/ttyUSB0 or COM7
Valid values for `device_type` and `device_type2`: fgw14, fgw14-usb, fam14
`test_run_count`: Amount of test runs which will be executed in a row. 
`message_delay`: Delay between to telegrams in seconds (float). Default value is 0.05 => 50ms. If delay is too small buffer overflow in gateway will happen. 

## Example Output

```
2026-01-16 17:38:31,382 INFO eo_man Start Application eo_man 
2026-01-16 17:38:32,317 INFO eo_man Version: 0.1.43
Name: eo_man
Author: Philipp Grimm
Home-Page: https://github.com/grimmpp/enocean-device-manager
License: MIT
Summary: Tool to managed EnOcean Devices and to generate Home Assistant Configuration.
Requires-Python: >=3.12
Lastest_Available_Version: 0.1.50

2026-01-16 17:38:32,331 INFO eltakobus.serial Serial communication started 
2026-01-16 17:38:32,350 INFO eltakobus.serial Established serial connection to COM12 - baud rate: 57600 
2026-01-16 17:38:32,976 INFO eo_man Serial connection established. serial port: COM12, baudrate: 57600, device type: fgw14 
2026-01-16 17:38:32,977 INFO eltakobus.serial Serial communication started 
2026-01-16 17:38:32,995 INFO eltakobus.serial Established serial connection to COM7 - baud rate: 57600 
2026-01-16 17:38:33,010 INFO eo_man Serial connection established. serial port: COM7, baudrate: 57600, device type: fam14 
2026-01-16 17:38:34,011 INFO eo_man  
2026-01-16 17:38:34,011 INFO eo_man Start BURST TEST RUN No. 1 - 44 Messages, delayed by 0.025s 
2026-01-16 17:38:39,204 INFO eo_man => Test run No. 1 was SUCCESSFUL. 
2026-01-16 17:38:39,205 INFO eo_man  
2026-01-16 17:38:39,205 INFO eo_man Start BURST TEST RUN No. 2 - 44 Messages, delayed by 0.025s
2026-01-16 17:38:44,428 INFO eo_man => Test run No. 2 was SUCCESSFUL. 
2026-01-16 17:38:44,429 INFO eo_man  
2026-01-16 17:38:44,429 INFO eo_man Start BURST TEST RUN No. 3 - 44 Messages, delayed by 0.025s
2026-01-16 17:38:49,638 INFO eo_man => Test run No. 3 was SUCCESSFUL. 
2026-01-16 17:38:49,639 INFO eo_man  
2026-01-16 17:38:49,639 INFO eo_man Start BURST TEST RUN No. 4 - 44 Messages, delayed by 0.025s
2026-01-16 17:38:54,831 INFO eo_man => Test run No. 4 was SUCCESSFUL. 
2026-01-16 17:38:54,831 INFO eo_man  
2026-01-16 17:38:54,831 INFO eo_man Start BURST TEST RUN No. 5 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:00,031 INFO eo_man => Test run No. 5 was SUCCESSFUL. 
2026-01-16 17:39:00,031 INFO eo_man  
2026-01-16 17:39:00,032 INFO eo_man Start BURST TEST RUN No. 6 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:05,220 INFO eo_man => Test run No. 6 was SUCCESSFUL. 
2026-01-16 17:39:05,220 INFO eo_man  
2026-01-16 17:39:05,220 INFO eo_man Start BURST TEST RUN No. 7 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:10,432 INFO eo_man => Test run No. 7 was SUCCESSFUL. 
2026-01-16 17:39:10,432 INFO eo_man  
2026-01-16 17:39:10,433 INFO eo_man Start BURST TEST RUN No. 8 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:15,639 INFO eo_man => Test run No. 8 was SUCCESSFUL. 
2026-01-16 17:38:39,205 INFO eo_man
2026-01-16 17:38:39,205 INFO eo_man Start BURST TEST RUN No. 2 - 44 Messages, delayed by 0.025s
2026-01-16 17:38:44,428 INFO eo_man => Test run No. 2 was SUCCESSFUL.
2026-01-16 17:38:44,429 INFO eo_man
2026-01-16 17:38:44,429 INFO eo_man Start BURST TEST RUN No. 3 - 44 Messages, delayed by 0.025s
2026-01-16 17:38:49,638 INFO eo_man => Test run No. 3 was SUCCESSFUL.
2026-01-16 17:38:49,639 INFO eo_man
2026-01-16 17:38:49,639 INFO eo_man Start BURST TEST RUN No. 4 - 44 Messages, delayed by 0.025s
2026-01-16 17:38:54,831 INFO eo_man => Test run No. 4 was SUCCESSFUL.
2026-01-16 17:38:54,831 INFO eo_man
2026-01-16 17:38:54,831 INFO eo_man Start BURST TEST RUN No. 5 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:00,031 INFO eo_man => Test run No. 5 was SUCCESSFUL.
2026-01-16 17:39:00,031 INFO eo_man
2026-01-16 17:39:00,032 INFO eo_man Start BURST TEST RUN No. 6 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:05,220 INFO eo_man => Test run No. 6 was SUCCESSFUL.
2026-01-16 17:39:05,220 INFO eo_man
2026-01-16 17:39:05,220 INFO eo_man Start BURST TEST RUN No. 7 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:10,432 INFO eo_man => Test run No. 7 was SUCCESSFUL.
2026-01-16 17:39:10,432 INFO eo_man
2026-01-16 17:39:10,433 INFO eo_man Start BURST TEST RUN No. 8 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:15,639 INFO eo_man => Test run No. 8 was SUCCESSFUL.
2026-01-16 17:38:44,428 INFO eo_man => Test run No. 2 was SUCCESSFUL.
2026-01-16 17:38:44,429 INFO eo_man
2026-01-16 17:38:44,429 INFO eo_man Start BURST TEST RUN No. 3 - 44 Messages, delayed by 0.025s
2026-01-16 17:38:49,638 INFO eo_man => Test run No. 3 was SUCCESSFUL.
2026-01-16 17:38:49,639 INFO eo_man
2026-01-16 17:38:49,639 INFO eo_man Start BURST TEST RUN No. 4 - 44 Messages, delayed by 0.025s
2026-01-16 17:38:54,831 INFO eo_man => Test run No. 4 was SUCCESSFUL.
2026-01-16 17:38:54,831 INFO eo_man
2026-01-16 17:38:54,831 INFO eo_man Start BURST TEST RUN No. 5 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:00,031 INFO eo_man => Test run No. 5 was SUCCESSFUL.
2026-01-16 17:39:00,031 INFO eo_man
2026-01-16 17:39:00,032 INFO eo_man Start BURST TEST RUN No. 6 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:05,220 INFO eo_man => Test run No. 6 was SUCCESSFUL.
2026-01-16 17:39:05,220 INFO eo_man
2026-01-16 17:39:05,220 INFO eo_man Start BURST TEST RUN No. 7 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:10,432 INFO eo_man => Test run No. 7 was SUCCESSFUL.
2026-01-16 17:39:10,432 INFO eo_man
2026-01-16 17:39:10,433 INFO eo_man Start BURST TEST RUN No. 8 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:15,639 INFO eo_man => Test run No. 8 was SUCCESSFUL.
2026-01-16 17:38:44,429 INFO eo_man Start BURST TEST RUN No. 3 - 44 Messages, delayed by 0.025s
2026-01-16 17:38:49,638 INFO eo_man => Test run No. 3 was SUCCESSFUL.
2026-01-16 17:38:49,639 INFO eo_man
2026-01-16 17:38:49,639 INFO eo_man Start BURST TEST RUN No. 4 - 44 Messages, delayed by 0.025s
2026-01-16 17:38:54,831 INFO eo_man => Test run No. 4 was SUCCESSFUL.
2026-01-16 17:38:54,831 INFO eo_man
2026-01-16 17:38:54,831 INFO eo_man Start BURST TEST RUN No. 5 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:00,031 INFO eo_man => Test run No. 5 was SUCCESSFUL.
2026-01-16 17:39:00,031 INFO eo_man
2026-01-16 17:39:00,032 INFO eo_man Start BURST TEST RUN No. 6 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:05,220 INFO eo_man => Test run No. 6 was SUCCESSFUL.
2026-01-16 17:39:05,220 INFO eo_man
2026-01-16 17:39:05,220 INFO eo_man Start BURST TEST RUN No. 7 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:10,432 INFO eo_man => Test run No. 7 was SUCCESSFUL.
2026-01-16 17:39:10,432 INFO eo_man
2026-01-16 17:39:10,433 INFO eo_man Start BURST TEST RUN No. 8 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:15,639 INFO eo_man => Test run No. 8 was SUCCESSFUL.
2026-01-16 17:38:49,639 INFO eo_man Start BURST TEST RUN No. 4 - 44 Messages, delayed by 0.025s
2026-01-16 17:38:54,831 INFO eo_man => Test run No. 4 was SUCCESSFUL.
2026-01-16 17:38:54,831 INFO eo_man
2026-01-16 17:38:54,831 INFO eo_man Start BURST TEST RUN No. 5 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:00,031 INFO eo_man => Test run No. 5 was SUCCESSFUL.
2026-01-16 17:39:00,031 INFO eo_man
2026-01-16 17:39:00,032 INFO eo_man Start BURST TEST RUN No. 6 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:05,220 INFO eo_man => Test run No. 6 was SUCCESSFUL.
2026-01-16 17:39:05,220 INFO eo_man
2026-01-16 17:39:05,220 INFO eo_man Start BURST TEST RUN No. 7 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:10,432 INFO eo_man => Test run No. 7 was SUCCESSFUL.
2026-01-16 17:39:10,432 INFO eo_man
2026-01-16 17:39:10,433 INFO eo_man Start BURST TEST RUN No. 8 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:15,639 INFO eo_man => Test run No. 8 was SUCCESSFUL.
2026-01-16 17:38:54,831 INFO eo_man Start BURST TEST RUN No. 5 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:00,031 INFO eo_man => Test run No. 5 was SUCCESSFUL.
2026-01-16 17:39:00,031 INFO eo_man
2026-01-16 17:39:00,032 INFO eo_man Start BURST TEST RUN No. 6 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:05,220 INFO eo_man => Test run No. 6 was SUCCESSFUL.
2026-01-16 17:39:05,220 INFO eo_man
2026-01-16 17:39:05,220 INFO eo_man Start BURST TEST RUN No. 7 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:10,432 INFO eo_man => Test run No. 7 was SUCCESSFUL.
2026-01-16 17:39:10,432 INFO eo_man
2026-01-16 17:39:10,433 INFO eo_man Start BURST TEST RUN No. 8 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:15,639 INFO eo_man => Test run No. 8 was SUCCESSFUL.
2026-01-16 17:39:00,032 INFO eo_man Start BURST TEST RUN No. 6 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:05,220 INFO eo_man => Test run No. 6 was SUCCESSFUL.
2026-01-16 17:39:05,220 INFO eo_man
2026-01-16 17:39:05,220 INFO eo_man Start BURST TEST RUN No. 7 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:10,432 INFO eo_man => Test run No. 7 was SUCCESSFUL.
2026-01-16 17:39:10,432 INFO eo_man
2026-01-16 17:39:10,433 INFO eo_man Start BURST TEST RUN No. 8 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:15,639 INFO eo_man => Test run No. 8 was SUCCESSFUL.
2026-01-16 17:39:10,432 INFO eo_man => Test run No. 7 was SUCCESSFUL.
2026-01-16 17:39:10,432 INFO eo_man
2026-01-16 17:39:10,433 INFO eo_man Start BURST TEST RUN No. 8 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:15,639 INFO eo_man => Test run No. 8 was SUCCESSFUL.
2026-01-16 17:39:15,639 INFO eo_man => Test run No. 8 was SUCCESSFUL.
2026-01-16 17:39:15,640 INFO eo_man
2026-01-16 17:39:15,641 INFO eo_man Start BURST TEST RUN No. 9 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:20,834 INFO eo_man => Test run No. 9 was SUCCESSFUL.
2026-01-16 17:39:20,834 INFO eo_man
2026-01-16 17:39:20,835 INFO eo_man Start BURST TEST RUN No. 10 - 44 Messages, delayed by 0.025s
2026-01-16 17:39:26,047 INFO eo_man => Test run No. 10 was SUCCESSFUL.
2026-01-16 17:39:26,048 INFO eo_man ===================================================================================
2026-01-16 17:39:26,049 INFO eo_man      =>      10 of 10 RUNS WERE SUCESSFULL. 44 Message per run delayed by 0.025s.
2026-01-16 17:39:26,049 INFO eo_man ===================================================================================
2026-01-16 17:39:26,049 INFO eo_man      run: 1, msg sent: 44, msg not received: 0, received other msgs: 102
2026-01-16 17:39:26,049 INFO eo_man      run: 2, msg sent: 44, msg not received: 0, received other msgs: 100
2026-01-16 17:39:26,050 INFO eo_man      run: 3, msg sent: 44, msg not received: 0, received other msgs: 99
2026-01-16 17:39:26,050 INFO eo_man      run: 4, msg sent: 44, msg not received: 0, received other msgs: 99
2026-01-16 17:39:26,050 INFO eo_man      run: 5, msg sent: 44, msg not received: 0, received other msgs: 99
2026-01-16 17:39:26,051 INFO eo_man      run: 6, msg sent: 44, msg not received: 0, received other msgs: 99
2026-01-16 17:39:26,051 INFO eo_man      run: 7, msg sent: 44, msg not received: 0, received other msgs: 98
2026-01-16 17:39:26,051 INFO eo_man      run: 8, msg sent: 44, msg not received: 0, received other msgs: 101
2026-01-16 17:39:26,052 INFO eo_man      run: 9, msg sent: 44, msg not received: 0, received other msgs: 99
2026-01-16 17:39:26,052 INFO eo_man      run: 10, msg sent: 44, msg not received: 0, received other msgs: 99
2026-01-16 17:39:26,162 INFO eltakobus.serial Serial communication stopped
2026-01-16 17:39:26,552 INFO eo_man Serial connection stopped.
2026-01-16 17:39:26,653 INFO eltakobus.serial Serial communication stopped
2026-01-16 17:39:27,053 INFO eo_man Serial connection stopped.
```