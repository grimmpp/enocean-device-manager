# Cover Travel Time Test

This is a small command-line tool that drives Eltako cover actuators (FSB14, FSB61, FJ62, FSUD, ...) with a
configurable sequence of movement commands and pauses and reports in detail what happened.

It answers the questions:

* Did **all** covers react on **every** command and did they move into the requested direction?
* **How long** did every cover really move? The measured time and the travel time which the actuator itself
  reports are shown next to each other.
* Which **switch telegrams** (e.g. a wall switch someone pressed) disturbed the test, and how much travel
  time was accumulated **until** the interference happened?

The measured travel times are the base for configuring the runtime of an FSB actuator. The actuator only knows
**one** runtime for the whole cover, although moving up, moving down and turning the slats of a venetian blind
usually take a different amount of time. With this test you get all those times and can pick the right value.

## Command

```shell
python.exe -m eo_man --command cover_test --serial_port COM7 --device_type fgw14usb \
                     --cover_ids 00-00-00-05:FE-D4-E9-47,00-00-00-07:FE-D4-E9-48 \
                     --cover_sequence up:60,pause:5,down:60,pause:5 \
                     --cover_marker_switch FF-11-22-33 \
                     --test_run_count 2 \
                     --test_report cover_test.txt
```

| Argument | Short | Description |
|---|---|---|
| `--serial_port` | `-sp` | Serial port of the gateway, e.g. `COM7` or `/dev/ttyUSB0`. For a LAN gateway: `IP:PORT`. |
| `--device_type` | `-dt` | Gateway type, e.g. `fgw14usb`, `fam14`, `fam-usb`, `esp3-gateway`, `lan`. |
| `--cover_ids` | `-cid` | Comma-separated list of the covers to be tested, each with the switch which is taught into it. **All covers get exactly the same commands.** See below. |
| `--cover_sequence` | `-cseq` | Comma-separated list of movement commands and pauses which are executed one after the other. |
| `--cover_command_mode` | `-cm` | `stop` (default) or `timed`, see below. |
| `--test_run_count` | `-trc` | How often the whole sequence is repeated. Default: `1`. |
| `--cover_marker_switch` | `-cms` | Optional switch which is **not** taught into any actuator. Used to mark points in time and to signal an end position by hand. See below. |
| `--cover_marker_double_press_time` | `-cmt` | Two presses of the marker switch within this time are one double press. Default: `1.5` seconds. |
| `--cover_message_delay` | `-cmd` | Delay between two command telegrams in seconds. Default: `0.1` (100ms). See below. |
| `--verbose` | `-v` | `-v` additionally logs every relevant telegram while the test runs and appends the complete telegram log to the report. `-vv` also shows the raw ESP2 data of every telegram and enables the debug log of the serial communication. |
| `--test_report` | `-tr` | Optional file the whole printed report is written to as plain text. |
| `--test_report_csv` | `-tcsv` | Optional CSV file all recorded telegrams are written to (for a spreadsheet application). |

Without `-v` only the result is printed: one line per test step while it runs and the tables of the report
afterwards. That keeps the output readable even for a long test. Use `-v` when you want to see what really
happened on the bus.

### Cover ids

Every entry of `--cover_ids` describes one cover:

```text
ACTUATOR_ID[:SWITCH_ID[+SWITCH_ID...]][:SENDER_ID]
```

| Part | Required | Meaning |
|---|---|---|
| `ACTUATOR_ID` | yes | Address of the actuator, i.e. the address its status telegrams come from (e.g. `00-00-00-05`). |
| `SWITCH_ID` | no | The wall switch which is taught into that actuator (e.g. `FE-D4-E9-47`). Several switches of one cover are separated by `+`. Leave it out if no switch is taught in or if you do not want to operate the cover by hand during the test. |
| `SENDER_ID` | no | Address the test sends its commands from. Defaults to `00-00-B0-XX` for bus actuators (`00-00-00-XX`), which is the sender id this application also uses for Home Assistant. |

Examples:

| Entry | Meaning |
|---|---|
| `00-00-00-05` | Bus actuator with address 5, no switch declared. Commands are sent from `00-00-B0-05`. |
| `00-00-00-05:FE-D4-E9-47` | The same cover, operated by switch `FE-D4-E9-47`. |
| `00-00-00-05:FE-D4-E9-47+FE-D4-E9-48` | The same cover, but two switches are taught into it. |
| `00-00-00-05::00-00-B0-05` | No switch, but an explicitly given sender id (the empty middle entry keeps the sender in the third position). |
| `FF-AA-BB-01:FE-D4-E9-47:00-00-B0-07` | Actuator `FF-AA-BB-01`, switch `FE-D4-E9-47`, commands are sent from `00-00-B0-07`. |

Naming the sender id in the switch position (`00-00-00-05:00-00-B0-05`) is accepted as well and means the same
as `00-00-00-05`: the address the test sends from is not a switch, so it is not treated as one.

The **sender id** has to be taught into the actuator beforehand - otherwise the cover will not move. Use
*Write HA senders to devices* of the GUI or PCT14 to do so.

**Why should the switch be given?** Every telegram which does not come from a declared device has to be treated
as a possible interference of *every* running movement, because the test cannot know which cover it belongs to.
As soon as the switches are declared, a press is assigned to exactly the cover(s) that switch operates - the
other covers of the test run keep their clean measurement. It also keeps the report readable: declared switches
show up as `switch`, everything else as `unknown`.

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

### Marker switch: measuring the real end position by hand

An FSB actuator does not know when the cover physically reaches its end position - it simply runs for its
configured runtime. So the travel time it reports can be **longer** than the cover really needed. With
`--cover_marker_switch` you can measure the real value: take any EnOcean switch which is **not** taught into the
actuators, watch the cover and press it at the right moment.

```shell
python -m eo_man -C cover_test -sp COM3 -dt fgw14usb -cid 00-00-00-05:FE-D4-E9-47 \
                 -cseq up:90,pause:5,down:90,pause:5 -cms FF-11-22-33
```

| Action | Meaning |
|---|---|
| **press once** | Records the point in time. The report shows how long the cover had been moving at that moment. Use it to mark anything you want to measure, e.g. when the slats of a venetian blind are closed. |
| **press twice in a row** | *Manual end position detection*: the cover has physically reached its end position now. The report treats this time as the travel time the cover really needed. |

Two presses count as a double press when they follow each other within `--cover_marker_double_press_time`
(default 1.5 seconds) **and the same button was used**. Pressing `AI` and then `B0` are two separate actions, so
each of them stays a single time marker. The **first** press of a pair is the moment which counts - that is when
you reacted. Further presses of that button within the window are shown as `repetition`.

The report names the button of every marker, so you can use the four buttons of one rocker switch for different
things during a test, e.g. the upper one for the end position and the lower one for the closed slats.

Only the press is a marker. A rocker switch also sends a release telegram right afterwards - it appears in the
telegram log (`-v`) but does not become a marker of its own.

The marker switch is not taught into any actuator, so it cannot move anything: its telegrams are **never**
counted as an interference, and a movement which was marked is not flagged as `interrupted`. The test refuses to
start if the marker switch is also given as a taught-in switch of a cover.

The result is a separate section of the report:

```text
run | step | cover       | command   |  no | marker      | button |       at | travelled |  travel | difference | kind
  1 |    1 | 00-00-00-05 | UP 90s    |   1 | FF-11-22-33 | AI     |   12.80s |    12.80s |   21.5s |     +8.70s | time marker
  1 |    1 | 00-00-00-05 | UP 90s    |   2 | FF-11-22-33 | AI     |   19.42s |    19.42s |   21.5s |     +2.08s | END POSITION REACHED
  1 |    1 | 00-00-00-05 | UP 90s    |   3 | FF-11-22-33 | AI     |   19.68s |    19.68s |   21.5s |     +1.82s | repetition
  1 |    3 | 00-00-00-05 | DOWN 90s  |   1 | FF-11-22-33 | A0     |   45.10s |    21.30s |   23.0s |     +1.70s | END POSITION REACHED

 no         = number of the marker within its movement, counted from the movement command
 button     = button of the rocker switch which was pressed (AI, A0, BI, B0)
 travelled  = how long the cover had been moving when the marker switch was pressed
 travel     = whole travel time of that movement (reported by the actuator, otherwise measured)
 difference = how much longer the actuator kept on running after the marker
```

The markers are numbered **per movement**, so the numbering starts again with `1` for every movement command.
That makes it easy to refer to a specific marker, e.g. "marker 1 of the UP movement was the closed slats".

The manually measured times are shown as `manual end` in the travel time statistics and - because they are the
times the cover really needed - they are used for the runtime recommendation:

```text
 Cover 00-00-00-05: up 19.4s, down 21.3s -> configure a runtime of at least 21.3s
   based on the end position which was signalled with the marker switch (up 19.4s, down 21.3s).
   The actuator itself reported: up 21.5s, down 23.0s
```

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

* Every telegram which does not come from an actuator under test is logged with its timestamp and shown in the
  *INTERFERENCES* section. Telegrams of the switches declared in `--cover_ids` are marked as `switch`, all
  others as `unknown`.
* If such a telegram arrives **while a cover is moving**, that movement is marked as `interrupted` and the
  travel time **until the intervention** is reported. So you can also use a switch to stop the cover on purpose
  (e.g. exactly when the cover is closed) and read the travel time up to that moment.
* Telegrams which arrive when no cover is moving (e.g. during a pause) are logged but do not count as
  interference.

### What does `interrupted` mean?

A movement is marked as `interrupted` when a received telegram

1. is an RPS telegram which decodes as a **pressed** rocker switch (EEP F6-02-01, energy bow set) - the release
   telegram of a switch is logged but does not count,
2. arrived **after** the movement command was sent and **before or at** the moment the movement ended (the
   actuator reported its travel time / an end position, or the test sent `STOP`),
3. and belongs to this cover:

| Sender of the telegram | Which movements are marked | Shown as |
|---|---|---|
| A switch declared for this cover in `--cover_ids` | only the movements of the cover(s) that switch operates | `switch FE-D4-E9-47` |
| Any other address | **every** movement which was running at that moment, because it cannot be assigned | `unknown 00-00-00-42` |

The report then shows:

```text
run | step | cover       | command    |  react | measured | reported | dir  | end | stopped by           | result
  1 |    5 | 00-00-00-05 | DOWN 60s   | 10.77s |   10.77s |    10.8s | DOWN | -   | switch FE-D4-E9-47   | interrupted

 Movements which were disturbed:
   run 1 step 5 cover 00-00-00-05 (DOWN 60.0s): switch FE-D4-E9-47 intervened after 10.77s -> travel time
   until the intervention: 10.77s, actuator reported 10.8s
```

**It means: a switch telegram arrived while this cover was still moving.** Even for a declared switch this is a
correlation in time - the report says which switch it was and when, it does not prove that the cover stopped
because of it.

How to read such a row:

* `reported` is still the travel time which the actuator itself reported, i.e. how long the cover really moved
  before it stopped. **This is exactly the value you want when you use a switch on purpose to stop the cover**
  (e.g. at the moment the slats are closed) - the movement is flagged, but the measurement is valid.
* The `end` column tells you whether the cover ran into its end position anyway. If it shows `TOP` or `BOT`, the
  switch was pressed shortly before the end was reached and probably did not change the result.
* An interrupted movement is **not** used for *complete travel* and therefore never falsifies the runtime
  recommendation. If you did not want the interruption, simply repeat that movement.

Two situations lead to `interrupted`:

* **Intended**: you press the wall switch of a cover yourself to stop it and read the travel time up to that
  point. This is what the flag is made for.
* **Unintended**: somebody else operated a switch, or an automation did. Repeat the affected movement.

### `unknown` telegrams

Everything which is neither an actuator nor a declared switch is reported as `unknown` and - to be on the safe
side - counts as a possible interference of every movement which was running at that moment. The report lists
those addresses at the end of the *INTERFERENCES* section. Two typical causes:

* **A switch you did not declare.** Add it to the cover it operates: `00-00-00-05:FE-D4-E9-47+FE-D4-E9-48`.
* **Another cover which moves but is not part of the test.** The status telegrams of an Eltako cover are RPS
  telegrams as well, and their end position values decode exactly like a pressed rocker switch (`0x70` ->
  button `B0`, `0x50` -> button `BI`). Add that cover to `--cover_ids` - then its telegrams are recognized as
  `cover` instead of `unknown`.

The complete telegram log (`-v`) shows which address sent what, so such a case is easy to identify.

## Example Output

Default output (without `-v`) of a test with two covers. During the third movement the wall switch of
cover `00-00-00-05` was pressed - only that cover is marked, the other one keeps its clean measurement:

```text
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 COVER TRAVEL TIME TEST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 Gateway:       FGW14(-USB) (ESP2) on COM7
 Covers:        00-00-00-05 (switch FE-D4-E9-47, sender 00-00-B0-05), 00-00-00-07 (switch FE-D4-E9-48, sender 00-00-B0-07)
 Sequence:      UP 30.0s → PAUSE 3.0s → DOWN 30.0s → PAUSE 3.0s → DOWN 30.0s → PAUSE 3.0s
 Runs:          1
 Command mode:  stop - movement is terminated by a STOP command
 Message delay: 0.1s between two command telegrams
 Duration:      about 103s

 You can operate the covers with their wall switch during the test. Such interferences are logged and the travel time until the intervention is reported.
 Use -v to see every telegram, -vv to additionally see the raw ESP2 data.

 RUN 1 of 1
──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

 [   0.00s] Step 1/6: UP 30.0s
           → 2/2 covers reacted, travel time: 19.4s, 19.4s

 [  30.11s] Step 2/6: PAUSE 3.0s

 [  33.11s] Step 3/6: DOWN 30.0s
           → 2/2 covers reacted, travel time: 21.2s, 21.2s

 [  63.22s] Step 4/6: PAUSE 3.0s

 [  66.22s] Step 5/6: DOWN 30.0s
           → 2/2 covers reacted, travel time: 9.8s, 21.2s - interrupted

 [  96.33s] Step 6/6: PAUSE 3.0s

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
  1 │    5 │ 00-00-00-05 │ DOWN 30s   │  9.78s │    9.78s │     9.8s │ DOWN │ -   │ switch FE-D4-E9-47   │ interrupted
  1 │    5 │ 00-00-00-07 │ DOWN 30s   │ 21.20s │   21.20s │    21.2s │ DOWN │ BOT │ bottom end position  │ OK

 react    = time between the sent command and the first telegram of the cover
 measured = time between the sent command and the telegram which ended the movement
 reported = travel time which the actuator itself reported (most precise value)
 end      = TOP / BOT if the cover ran into its top or bottom end position

 TRAVEL TIMES PER COVER AND DIRECTION
────────────────────────────────────────────────────────────────────────────────────────────────
cover       │ direction │ moves │      min │      avg │      max │ complete travel │ interrupted
────────────────────────────────────────────────────────────────────────────────────────────────
00-00-00-05 │ UP        │     1 │   19.40s │   19.40s │   19.40s │           19.4s │           -
00-00-00-05 │ DOWN      │     2 │    9.80s │   15.50s │   21.20s │           21.2s │           1
00-00-00-07 │ UP        │     1 │   19.40s │   19.40s │   19.40s │           19.4s │           -
00-00-00-07 │ DOWN      │     2 │   21.20s │   21.20s │   21.20s │           21.2s │           -

 complete travel = longest travel time of a movement which reached an end position without interference

 HINTS FOR CONFIGURING THE RUNTIME OF THE ACTUATOR (FSB)
──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
 Cover 00-00-00-05: up 19.4s, down 21.2s → configure a runtime of at least 21.2s
   difference between up and down: 1.8s. The actuator only knows one runtime, so the faster direction stands still for 1.8s before the configured runtime has elapsed.
 Cover 00-00-00-07: up 19.4s, down 21.2s → configure a runtime of at least 21.2s
   difference between up and down: 1.8s. The actuator only knows one runtime, so the faster direction stands still for 1.8s before the configured runtime has elapsed.
 For venetian blinds measure the turning of the slats separately with short movement steps (e.g. 'down:2').

 INTERFERENCES - SWITCHES AND UNKNOWN TELEGRAMS (1)
──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
    76.00s  FE-D4-E9-47  switch   switch of cover 00-00-00-05 pressed (button BI) (during a movement)

 Movements which were disturbed:
   run 1 step 5 cover 00-00-00-05 (DOWN 30.0s): switch FE-D4-E9-47 intervened after 9.78s → travel time until the intervention: 9.78s, actuator reported 9.8s

 'interrupted' means that a switch telegram arrived while the cover was still moving. The travel time up to that moment is valid, but such a movement is not used for the runtime recommendation.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 RESULT: 5 of 6 movements behaved as requested (1x interrupted).
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
* Status telegrams of the actuator are decoded as **EEP G5-3F-7F**:
  * RPS, `0x01` / `0x02`: the actuator starts to move up / down. This is where the `dir` column comes from.
  * RPS, `0x70` / `0x50`: the top / bottom end position was reached. This ends the movement and is what the
    `measured` travel time is based on.
  * 4BS: the actuator reports the direction and the travel time in 100ms steps -> the `reported` column.

> **Not every actuator sends the 4BS travel report.** Verified with FSB14 behind a FGW14-USB: those devices
> only send the RPS telegrams listed above, so the `reported` column stays empty and `measured` is the value to
> look at. `measured` is the time between the sent command and the end position telegram, which includes the
> reaction time of the actuator (typically 0.2 - 0.8s, visible in the `react` column).
