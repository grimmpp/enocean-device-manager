# Cover Travel Time Test

This is a small command-line tool that drives Eltako cover actuators (FSB14, FSB61, FJ62, FSUD, ...) with a
configurable sequence of movement commands and pauses and reports in detail what happened.

It answers the questions:

* Did **all** covers react on **every** command and did they move into the requested direction?
* **How long** did every cover really move? The measured time and the travel time which the actuator itself
  reports are shown next to each other.
* Which **foreign telegrams** (e.g. a wall switch someone pressed) disturbed the test, and how much travel
  time was accumulated **until** the interference happened?

The measured travel times are the base for configuring the runtime of an FSB actuator. The actuator only knows
**one** runtime for the whole cover, although moving up, moving down and turning the slats of a venetian blind
usually take a different amount of time. With this test you get all those times and can pick the right value.

## Command

```shell
python.exe -m eo_man --command cover_test --serial_port COM7 --device_type fgw14usb \
                     --cover_ids 00-00-00-05,00-00-00-07 \
                     --cover_sequence up:60,pause:5,down:60,pause:5 \
                     --test_run_count 2 \
                     --test_report cover_test.txt
```

| Argument | Short | Description |
|---|---|---|
| `--serial_port` | `-sp` | Serial port of the gateway, e.g. `COM7` or `/dev/ttyUSB0`. For a LAN gateway: `IP:PORT`. |
| `--device_type` | `-dt` | Gateway type, e.g. `fgw14usb`, `fam14`, `fam-usb`, `esp3-gateway`, `lan`. |
| `--cover_ids` | `-cid` | Comma-separated list of the covers to be tested. **All covers get exactly the same commands.** |
| `--cover_sequence` | `-cseq` | Comma-separated list of movement commands and pauses which are executed one after the other. |
| `--cover_command_mode` | `-cm` | `stop` (default) or `timed`, see below. |
| `--test_run_count` | `-trc` | How often the whole sequence is repeated. Default: `1`. |
| `--cover_message_delay` | `-cmd` | Delay between two command telegrams in seconds. Default: `0.1` (100ms). See below. |
| `--verbose` | `-v` | `-v` additionally logs every relevant telegram while the test runs and appends the complete telegram log to the report. `-vv` also shows the raw ESP2 data of every telegram and enables the debug log of the serial communication. |
| `--test_report` | `-tr` | Optional file the whole printed report is written to as plain text. |
| `--test_report_csv` | `-tcsv` | Optional CSV file all recorded telegrams are written to (for a spreadsheet application). |

Without `-v` only the result is printed: one line per test step while it runs and the tables of the report
afterwards. That keeps the output readable even for a long test. Use `-v` when you want to see what really
happened on the bus.

### Cover ids

Every entry of `--cover_ids` addresses one cover and consists of the id of the **actuator** and optionally the
**sender id** which is taught into that actuator:

| Entry | Meaning |
|---|---|
| `00-00-00-05` | Bus actuator with address 5. Commands are sent from `00-00-B0-05` (the sender id this application also uses for Home Assistant). |
| `FF-AA-BB-01:00-00-B0-07` | Actuator `FF-AA-BB-01`, commands are sent from `00-00-B0-07`. |

The **actuator id** is the address the status telegrams come from, the **sender id** is the address the commands
are sent from. The sender id has to be taught into the actuator beforehand - otherwise the cover will not move.
Use *Write HA senders to devices* of the GUI or PCT14 to do so.

### Movement sequence

Every entry of `--cover_sequence` is `COMMAND:SECONDS`:

| Command | Aliases | Description |
|---|---|---|
| `up:20` | `auf`, `open` | Move up and let the cover move for 20 seconds. |
| `down:20` | `ab`, `close` | Move down and let the cover move for 20 seconds. |
| `stop` | `halt` | Stop the movement immediately. `stop:3` additionally waits 3 seconds afterwards. |
| `pause:5` | `wait`, `warten` | Send nothing for 5 seconds. |

Example: `up:60,pause:5,down:20,stop,pause:3,down:60,pause:5`

### Delay between the commands

Every step of the sequence sends one command telegram per cover. `--cover_message_delay` defines how long the
test waits **between** two of those telegrams:

```text
 [   0.00s] Step 1/2: UP 60.0s
      0.00s  SENT ... 00-00-B0-05  command UP to cover 00-00-00-05     <- first command, no delay before it
      0.10s  SENT ... 00-00-B0-07  command UP to cover 00-00-00-07     <- 100ms later
```

* Default is `0.1` (100ms). This is the same order of magnitude the bus gateways need to process a telegram and
  keeps the covers from starting at exactly the same moment.
* `--cover_message_delay 0` sends all commands without any delay. Use it if all covers have to start as
  simultaneously as possible. On a wired bus a value which is too small can cause a buffer overflow in the
  gateway, so telegrams may get lost.
* A larger value (e.g. `0.5`) is useful if you want to see the covers react one after the other.

The delay is never applied before the first telegram of a step, so it does not shift the measured travel times.
It also applies to the `STOP` telegrams which terminate a movement.

### Command mode

| Mode | Description |
|---|---|
| `stop` (default) | The movement is started without a time limit and terminated by a `STOP` command after the configured number of seconds. Works with any duration. If the cover already reported the end of the movement (end position reached), no `STOP` is sent. Use this mode to measure the **complete** travel time. |
| `timed` | The travel time is sent within the command telegram and the actuator stops on its own. This is the most precise mode but the telegram can only carry up to **25.5 seconds**. Longer durations automatically fall back to `stop`. |

## Determining the travel times

1. Drive the covers into their end position first, e.g. `--cover_sequence up:90,pause:5`. Choose a duration
   which is clearly longer than the cover needs.
2. Then measure both directions: `--cover_sequence down:90,pause:5,up:90,pause:5`. Every movement which reaches
   an end position appears as *complete travel* in the report.
3. For venetian blinds measure the turning of the slats separately with short steps, e.g.
   `--cover_sequence down:2,pause:2,down:2,pause:2`.
4. Set the runtime of the actuator to the **longer** of the two directions. The report prints this value as a hint.

## Using a wall switch during the test

Wall switches are not ignored - they are part of the result:

* Every telegram of a device which is not under test is logged with its timestamp and shown in the
  *INTERFERENCES* section.
* If such a telegram arrives **while a cover is moving**, the movement is marked as `interrupted` and the travel
  time **until the intervention** is reported. So you can also use a switch to stop the cover on purpose (e.g.
  exactly when the cover is closed) and read the travel time up to that moment.
* Telegrams which arrive when no cover is moving (e.g. during a pause) are logged but do not count as
  interference.

### What does `interrupted` mean?

A movement is marked as `interrupted` when **all** of the following applies to a received telegram:

1. it comes from an address which is neither an actuator id nor a sender id given in `--cover_ids`
   (the report calls those telegrams `foreign`),
2. it is an RPS telegram which decodes as a **pressed** rocker switch (EEP F6-02-01, energy bow set) - the
   release telegram of a switch is logged but does not count,
3. it arrived **after** the movement command was sent and **before or at** the moment the movement ended
   (the actuator reported its travel time / an end position, or the test sent `STOP`).

The report then shows:

```text
run | step | cover       | command    |  react | measured | reported | dir  | end | stopped by           | result
  1 |    5 | 00-00-00-05 | DOWN 60s   | 10.77s |   10.77s |    10.8s | DOWN | -   | switch 00-00-00-42   | interrupted

 Movements which were disturbed:
   run 1 step 5 cover 00-00-00-05 (DOWN 60.0s): 00-00-00-42 intervened after 10.77s -> travel time until the
   intervention: 10.77s, actuator reported 10.8s
```

**It means: someone or something else sent a switch telegram while this cover was still moving.** That is a
correlation in time - the test cannot know whether that switch is really taught into the actuator and therefore
whether it really stopped the cover. `stopped by: switch 00-00-00-42` is the most likely explanation, not a proof.

How to read such a row:

* `reported` is still the travel time which the actuator itself reported, i.e. how long the cover really moved
  before it stopped. **This is exactly the value you want when you use a switch on purpose to stop the cover**
  (e.g. at the moment the slats are closed) - the movement is flagged, but the measurement is valid.
* The `end` column tells you whether the cover ran into its end position anyway. If it shows `TOP` or `BOT`, the
  switch was pressed shortly before the end was reached and probably did not change the result.
* An interrupted movement is **not** used for *complete travel* and therefore never falsifies the runtime
  recommendation. If you did not want the interruption, simply repeat that movement.

Two situations lead to `interrupted`:

* **Intended**: you press a wall switch yourself to stop the cover and read the travel time up to that point.
  This is what the flag is made for.
* **Unintended**: somebody else operated a switch, or an automation did. Repeat the affected movement.

> **Pitfall - covers which are not under test look like a switch.** The status telegrams of an Eltako cover are
> RPS telegrams as well, and their end position values decode exactly like a pressed rocker switch
> (`0x70` -> button `B0`, `0x50` -> button `BI`). If a cover of your installation is moved but is **not** listed
> in `--cover_ids`, its end position telegrams therefore show up as `switch pressed` and can mark a movement as
> `interrupted`. Put all covers which move during the test into `--cover_ids` - then their telegrams are
> recognized as `cover` instead of `foreign`. The complete telegram log (`-v`) shows which address sent what, so
> such a case is easy to identify.

## Example Output

Default output (without `-v`) of a test with two covers where a wall switch interfered with the
third movement:

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 COVER TRAVEL TIME TEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Gateway:       FGW14(-USB) (ESP2) on COM7
 Covers:        00-00-00-05 (sender 00-00-B0-05), 00-00-00-07 (sender 00-00-B0-07)
 Sequence:      UP 30.0s → PAUSE 3.0s → DOWN 30.0s → PAUSE 3.0s → DOWN 30.0s → PAUSE 3.0s
 Runs:          1
 Command mode:  stop - movement is terminated by a STOP command
 Message delay: 0.1s between two command telegrams
 Duration:      about 103s

 You can move the covers with a wall switch during the test. Such interferences are logged and the travel time until the intervention is reported.
 Use -v to see every telegram, -vv to additionally see the raw ESP2 data.

 RUN 1 of 1
──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

 [   0.00s] Step 1/6: UP 30.0s
           → 2/2 covers reacted, travel time: 19.4s, 19.4s

 [  30.11s] Step 2/6: PAUSE 3.0s

 [  33.12s] Step 3/6: DOWN 30.0s
           → 2/2 covers reacted, travel time: 21.2s, 21.2s

 [  63.23s] Step 4/6: PAUSE 3.0s

 [  66.23s] Step 5/6: DOWN 30.0s
           → 2/2 covers reacted, travel time: 10.8s, 10.7s - interrupted

 [  96.34s] Step 6/6: PAUSE 3.0s

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 TEST RESULT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

 COMMANDS AND REACTION OF THE COVERS
───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
run │ step │ cover       │ command    │  react │ measured │ reported │ dir  │ end │ stopped by           │ result
───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  1 │    1 │ 00-00-00-05 │ UP 30s     │ 19.40s │   19.40s │    19.4s │ UP   │ TOP │ top end position     │ OK
  1 │    1 │ 00-00-00-07 │ UP 30s     │ 19.40s │   19.40s │    19.4s │ UP   │ TOP │ top end position     │ OK
  1 │    3 │ 00-00-00-05 │ DOWN 30s   │ 21.21s │   21.21s │    21.2s │ DOWN │ BOT │ bottom end position  │ OK
  1 │    3 │ 00-00-00-07 │ DOWN 30s   │ 21.21s │   21.21s │    21.2s │ DOWN │ BOT │ bottom end position  │ OK
  1 │    5 │ 00-00-00-05 │ DOWN 30s   │ 10.77s │   10.77s │    10.8s │ DOWN │ -   │ switch 00-00-00-42   │ interrupted
  1 │    5 │ 00-00-00-07 │ DOWN 30s   │ 10.72s │   10.72s │    10.7s │ DOWN │ -   │ switch 00-00-00-42   │ interrupted

 react    = time between the sent command and the first telegram of the cover
 measured = time between the sent command and the telegram which ended the movement
 reported = travel time which the actuator itself reported (most precise value)
 end      = TOP / BOT if the cover ran into its top or bottom end position

 TRAVEL TIMES PER COVER AND DIRECTION
────────────────────────────────────────────────────────────────────────────────────────────────
cover       │ direction │ moves │      min │      avg │      max │ complete travel │ interrupted
────────────────────────────────────────────────────────────────────────────────────────────────
00-00-00-05 │ UP        │     1 │   19.40s │   19.40s │   19.40s │           19.4s │           -
00-00-00-05 │ DOWN      │     2 │   10.80s │   16.00s │   21.20s │           21.2s │           1
00-00-00-07 │ UP        │     1 │   19.40s │   19.40s │   19.40s │           19.4s │           -
00-00-00-07 │ DOWN      │     2 │   10.70s │   15.95s │   21.20s │           21.2s │           1

 complete travel = longest travel time of a movement which reached an end position without interference

 HINTS FOR CONFIGURING THE RUNTIME OF THE ACTUATOR (FSB)
──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
 Cover 00-00-00-05: up 19.4s, down 21.2s → configure a runtime of at least 21.2s
   difference between up and down: 1.8s. The actuator only knows one runtime, so the faster direction stands still for 1.8s before the configured runtime has elapsed.
 Cover 00-00-00-07: up 19.4s, down 21.2s → configure a runtime of at least 21.2s
   difference between up and down: 1.8s. The actuator only knows one runtime, so the faster direction stands still for 1.8s before the configured runtime has elapsed.
 For venetian blinds measure the turning of the slats separately with short movement steps (e.g. 'down:2').

 INTERFERENCES - FOREIGN TELEGRAMS DURING THE TEST (1)
──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
    77.00s  00-00-00-42  RPSMessage: switch pressed (button BI) (during a movement)

 Movements which were disturbed:
   run 1 step 5 cover 00-00-00-05 (DOWN 30.0s): 00-00-00-42 intervened after 10.77s → travel time until the intervention: 10.77s, actuator reported 10.8s
   run 1 step 5 cover 00-00-00-07 (DOWN 30.0s): 00-00-00-42 intervened after 10.72s → travel time until the intervention: 10.72s, actuator reported 10.7s

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 RESULT: 4 of 6 movements behaved as requested (2x interrupted).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### With `-v`: every telegram of one step

```text
 [  33.12s] Step 3/6: DOWN 30.0s
     33.12s  SENT Regular4BSMessage  00-00-B0-05  cover    command DOWN to cover 00-00-00-05, travel time: runtime of actuator
     33.17s  SENT Regular4BSMessage  00-00-B0-07  cover    command DOWN to cover 00-00-00-07, travel time: runtime of actuator
     54.33s  RCVD Regular4BSMessage  00-00-00-05  cover    cover reports movement DOWN for 21.2s
     54.33s  RCVD RPSMessage         00-00-00-05  cover    cover reached BOTTOM END POSITION
     54.38s  RCVD Regular4BSMessage  00-00-00-07  cover    cover reports movement DOWN for 21.2s
     54.38s  RCVD RPSMessage         00-00-00-07  cover    cover reached BOTTOM END POSITION
           Cover 00-00-00-05 already signalled the end of the movement. No STOP command needed.
           Cover 00-00-00-07 already signalled the end of the movement. No STOP command needed.
           → 2/2 covers reacted, travel time: 21.2s, 21.2s
```

With `-vv` every line additionally carries the raw telegram, e.g.
`..., ESP2: a55a6b070006020a000000050089`.

## Protocol details

* Commands are sent as **EEP H5-3F-7F** (Eltako cover command, 4BS): `DB2` = travel time in 100ms steps
  (`0` = configured runtime of the actuator), `DB1` = `0x01` up / `0x02` down / `0x00` stop.
* Status telegrams of the actuator are decoded as **EEP G5-3F-7F**: the 4BS variant reports the direction and
  the travel time in 100ms steps, the RPS variant reports the end positions (`0x70` top, `0x50` bottom).
