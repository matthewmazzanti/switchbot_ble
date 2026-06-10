# SwitchBot Blind Tilt BLE Protocol

Based on APK version 9.11.15.13

## Device Identification

| Property              | Value             |
| --------------------- | ----------------- |
| Device Type (normal)  | `0x78` (120, 'x') |
| Device Type (pairing) | `0x58` (88, 'X')  |
| Manufacturer ID       | `0x0969` (2409)   |

## BLE Advertisement Data

The advertisement is split across two BLE fields. The app's `WoBlindTiltParser`
reads `device_type` + `battery` from the **service data**, and the remaining
fields from **manufacturer data bytes 7-10** (bytes 0-6 are the MAC and are
not read).

### Service data (UUID `0xFD3D`)

| Byte | Bits | Mask   | Field       | Type |
|------|------|--------|-------------|------|
| 0    | 6:0  | `0x7F` | device_type | u7   |
| 2    | 6:0  | `0x7F` | battery     | u7   |

- **device_type** — `0x58` or `0x78` for Blind Tilt (`isForThisType` accepts
  both). The app reports `pair_mode = (device_type == 0x58)`.

### Manufacturer data (ID `0x0969`), minimum 11 bytes

| Byte | Bits  | Mask   | Field         | Type |
|------|-------|--------|---------------|------|
| 0-6  | —     |        | MAC (not read)| —    |
| 7    | 7     | `0x80` | direction_set | bool |
|      | 6     | `0x40` | direction     | bool |
|      | 3     | `0x08` | stuck flag    | bool |
|      | 0     | `0x01` | calibrated    | bool |
| 8    | 7     | `0x80` | moving        | bool |
|      | 6:0   | `0x7F` | position      | u7   |
| 9    | 2:0   | `0x07` | link_length   | u3   |
| 10   | 7     | `0x80` | connect_allow | bool |

**Fields:**

- **battery** — battery percentage (0-100), from service data byte 2
- **direction_set** — 1 if open direction has been configured
- **direction** — 0 = default, 1 = reversed
- **calibrated** — 1 if calibration is complete
- **moving** — bit **SET** = motor running (NOT inverted)
- **position** — tilt position (0-100)
- **stuck** — reported only when the byte-7 stuck flag is set **and** not moving
- **link_length** — number of devices in chain (0-7)
- **connect_allow** — 1 if BLE connections are allowed

**Parsing example:**
```c
// service data (0xFD3D)
u8   device_type   = svc[0] & 0x7F;          // 0x58 or 0x78
u8   battery       = svc[2] & 0x7F;
// manufacturer data (0x0969); bytes 0-6 are the MAC
bool direction_set = mfr[7] & 0x80;
u8   direction     = (mfr[7] & 0x40) >> 6;
bool calibrated    = mfr[7] & 0x01;
u8   position      = mfr[8] & 0x7F;
bool moving        = mfr[8] & 0x80;          // SET = moving
bool stuck         = !moving && (mfr[7] & 0x08);
u8   link_length   = mfr[9] & 0x07;
bool connect_allow = mfr[10] & 0x80;
```

## BLE Characteristics

- **Service UUID**: `cba20d00-224d-11e6-9fb8-0002a5d5c51b`
- **Write Characteristic**: `cba20002-224d-11e6-9fb8-0002a5d5c51b`
- **Notify Characteristic**: `cba20003-224d-11e6-9fb8-0002a5d5c51b`

## Command Structure

All commands are prefixed with magic byte `0x57` when sent. The Blind Tilt uses extended commands:

```
[0x57] [0x0F] [CMD_TYPE] [SUB_CMD...] [PAYLOAD...]
```

**CMD_TYPE:** `0x45` = SET (write), `0x46` = GET (read)

**Response status codes:**

| Code   | Description      |
|--------|------------------|
| `0x01` | OK / Success     |
| `0x02` | Error            |
| `0x03` | Busy             |
| `0x05` | Unsupported      |
| `0x06` | Bootloader mode  |
| `0x07` | Encrypted        |
| `0x08` | Unencrypted      |
| `0x09` | Invalid password |

Success is indicated by `0x01` or `0x06`.

## Command Reference

### Movement & Control

| Command        | Bytes                                | Size | Description      |
| -------------- | ------------------------------------ | ---- | ---------------- |
| set_position   | `0F 45 01 <mode> <target> <pos>`     | 6    | Move to position |
| stop           | `0F 45 01 00 01`                     | 5    | Stop immediately |

**set_position** — Payload varies by firmware version:

| Offset | Size | Field    | Description                            |
|--------|------|----------|----------------------------------------|
| 0-2    | 3    | header   | `0F 45 01`                             |
| 3      | 1    | mode     | fw >= 20: `0x05`, fw < 20: `0x01`      |
| 4      | 1    | target   | fw >= 20: `0xFF`, fw < 20: `0x01`      |
| 5      | 1    | position | uint8, 0-100 (tilt percentage)         |

**get_position** (`0F 46 01 00`) — Get current position.

Response (7 bytes):

| Offset | Size | Field      | Description                            |
|--------|------|------------|----------------------------------------|
| 0      | 1    | status     | Status code                            |
| 1      | 1    | run_status | 0 = stopped, 1 = opening, 2 = closing |
| 2-5    | 4    | (reserved) |                                        |
| 6      | 1    | position   | Current position (0-100)               |

### Notifications

The device pushes position updates via BLE notifications on `cba20003` during
movement. Notifications must be explicitly enabled/disabled.

| Command          | Bytes                                      | Size | Description          |
| ---------------- | ------------------------------------------ | ---- | -------------------- |
| enable_notify    | `0E 01 <time_unit> <interval> FF FF <read_info_cmd...>` | 8+   | Enable notifications |
| disable_notify   | `0E 00`                                    | 2    | Disable notifications |

**enable_notify** — Subscribes to position updates during movement:

| Offset | Size | Field         | Description                        |
|--------|------|---------------|------------------------------------|
| 0      | 1    | cmd           | `0x0E` notify control              |
| 1      | 1    | enable        | `0x01` enable                      |
| 2      | 1    | time_unit     | Time unit for interval (0 = none)  |
| 3      | 1    | interval      | Reporting interval (0 = immediate) |
| 4-5    | 2    | reserved      | `0xFF 0xFF`                        |
| 6-8    | 3    | read_info_cmd | Query to report; `0xF2 0x01 0x00` = get_position |

**Notification data** — Same 7-byte format as `get_position` response:

| Offset | Size | Field      | Description                            |
|--------|------|------------|----------------------------------------|
| 0      | 1    | status     | Status code                            |
| 1      | 1    | run_status | 0 = stopped, 1 = opening, 2 = closing |
| 2-5    | 4    | (reserved) |                                        |
| 6      | 1    | position   | Current position (0-100)               |

Movement is complete when `run_status == 0`.

**Typical move flow:**
```
# 1. Send move command
Write:    57 0F 45 01 05 FF 32       # set_position(50), fw >= 20

# 2. Enable position notifications
Write:    57 0E 01 00 00 FF FF F2 01 00

# 3. Device pushes updates as motor runs
Notify:   01 01 00 00 00 00 19       # opening, position=25
Notify:   01 01 00 00 00 00 26       # opening, position=38
Notify:   01 01 00 00 00 00 32       # opening, position=50
Notify:   01 00 00 00 00 00 32       # stopped, position=50 (done)

# 4. Disable notifications
Write:    57 0E 00
```

### Calibration

| Command              | Bytes              | Size | Description            |
|----------------------|--------------------|------|------------------------|
| start_calibration    | `0F 45 05 01`      | 4    | Begin calibration      |
| stop_calibration     | `0F 45 05 02`      | 4    | Cancel calibration     |
| save_calibration     | `0F 45 05 09 <p>`  | 5    | Save calibration       |
| get_calibration      | `0F 46 05`         | 3    | Get calibration status |
| get_calibration_step | `0F 46 09`         | 3    | Get calibration step   |

**save_calibration** — Takes a preset byte:

| Offset | Size | Field   | Description                                   |
|--------|------|---------|-----------------------------------------------|
| 0-3    | 4    | header  | `0F 45 05 09`                                 |
| 4      | 1    | preset  | 1 = zero position, 2 = mid, 3 = full         |

Wire format: `57 0F 45 05 09 XX` where XX is the preset byte.

**get_calibration** — Request calibration status flags.

Wire format: `57 0F 46 05`

Response (2 bytes):

| Offset | Size | Field  | Description      |
|--------|------|--------|------------------|
| 0      | 1    | status | Status code      |
| 1      | 1    | flags  | Calibration info |

Response flags (byte 1):

| Bit(s) | Mask   | Field         | Description                      |
|--------|--------|---------------|----------------------------------|
| 7:3    | `0xF8` | (reserved)    |                                  |
| 2      | `0x04` | calibrated    | 1 = calibration complete         |
| 1      | `0x02` | direction_set | 1 = direction has been set       |
| 0      | `0x01` | direction     | 0 = default, 1 = reversed        |

**get_calibration_step** — Request current step during calibration.

Wire format: `57 0F 46 09`

Response (2 bytes):

| Offset | Size | Field  | Description        |
|--------|------|--------|--------------------|
| 0      | 1    | status | Status code        |
| 1      | 1    | flags  | Step and state     |

Response flags (byte 1):

| Bit(s) | Mask   | Field           | Description                        |
|--------|--------|-----------------|------------------------------------|
| 7      | `0x80` | (reserved)      |                                    |
| 6      | `0x40` | direction_error | 1 = direction detection failed     |
| 5      | `0x20` | exit            | 1 = calibration complete/exited    |
| 4      | `0x10` | enable_next     | 1 = ready to proceed to next step  |
| 3:0    | `0x0F` | step            | Current calibration step (0-15)    |

**Calibration Notification** — Pushed to `cba20003` during calibration. Same 2-byte format as `get_calibration_step` response.

**Example flow:**
```
# 1. Start calibration
Write:    57 0F 45 05 01
Response: 01              # OK

# 2. Device sends notifications as calibration progresses
Notify:   01 01           # step=1, flags=0
Notify:   01 11           # step=1, enable_next=1 (ready for next)
Notify:   01 02           # step=2
...
Notify:   01 24           # step=4, exit=1 (complete)

# 3. Save calibration (preset=1, zero position)
Write:    57 0F 45 05 09 01
Response: 01              # OK

# 4. Verify
Write:    57 0F 46 05
Response: 01 04           # calibrated=1
```

### Direction & Mode

| Command           | Bytes                      | Size | Description           |
| ----------------- | -------------------------- | ---- | --------------------- |
| set_direction     | `0F 45 04 06 01 <dir>`     | 6    | Set open direction    |
| set_action_mode   | `0F 45 04 01 01 <mode>`    | 6    | Set action mode       |
| get_action_mode   | `0F 46 04 03`              | 4    | Get action mode       |
| get_advanced_info | `0F 46 04 02`              | 4    | Get advanced settings |
| get_work_mode     | `0F 46 82 03`              | 4    | Get work mode         |

**set_direction** — Direction byte is `(value | 0x02)`:

| Input | Byte | Meaning    |
|-------|------|------------|
| 0     | 0x02 | Horizontal |
| 1     | 0x03 | Vertical   |

**set_action_mode** — Full 6-byte payload:

| Offset | Size | Field  | Description             |
|--------|------|--------|-------------------------|
| 0-4    | 5    | header | `0F 45 04 01 01`        |
| 5      | 1    | mode   | uint8, mode value       |

**get_action_mode** — Response (2 bytes): `[status] [mode]`. Mode bit 0: 0 = performance, 1 = silent.

### Light Sensitivity

| Command              | Bytes                                | Size  | Description                 |
| -------------------- | ------------------------------------ | ----- | --------------------------- |
| set_light_action     | `0F 45 03 01 <idx> 01 <mode...>`     | 7+    | Set light trigger action    |
| set_light_rule       | `0F 45 03 01 <rule:8>`               | 12    | Set light trigger rule      |
| set_light_source     | `0F 45 03 02 <idx> <type>`           | 6     | Set light data source       |
| clear_light_actions  | `0F 45 03 03`                        | 4     | Clear all light actions     |
| set_ai_light         | `0F 45 03 04 ...`                    | 4+    | Set AI light settings       |
| clear_ai_light       | `0F 45 03 05`                        | 4     | Clear AI light settings     |
| get_light_info       | `0F 46 03 00`                        | 4     | Get light basic info        |
| get_light_action     | `0F 46 03 01 <idx>`                  | 5     | Get light action at index   |
| get_light_source     | `0F 46 03 02`                        | 4     | Get light source info       |
| get_light_data       | `0F 46 03 04 <range> <src_idx>`      | 6     | Get light sensor data       |
| get_ai_light_count   | `0F 46 03 06`                        | 4     | Get AI light count state    |
| get_ai_light_action  | `0F 46 03 07`                        | 4     | Get AI light action info    |

**set_light_action** — Set the position to move to when a light threshold triggers:

| Offset | Size | Field    | Description                         |
|--------|------|----------|-------------------------------------|
| 0-3    | 4    | header   | `0F 45 03 01`                       |
| 4      | 1    | index    | Action slot (low nibble, & 0x0F, 0-15) |
| 5      | 1    | fixed    | `0x01`                              |
| 6-8    | 3    | action   | Same as set_position mode/target/position |

**set_light_rule** — Set the trigger conditions for a light action:

| Offset | Size | Field    | Description                           |
|--------|------|----------|---------------------------------------|
| 0-3    | 4    | header   | `0F 45 03 01`                         |
| 4      | 1    | idx_flag | `(index & 0x0F) \| 0x10` (bit 4 = rule flag) |
| 5      | 1    | thresh_flags | bit 6: enable, bits 4-5: threshold_type (1=higher, 2=lower) |
| 6      | 1    | threshold | bits 0-3: threshold level (0-15)    |
| 7      | 1    | repeat   | bits 0-6: weekday bitmap (bit 6=Sun .. bit 0=Sat) |
| 8      | 1    | hour     | Start hour, uint8, 0-23              |
| 9      | 1    | minute   | Start minute, uint8, 0-59            |
| 10     | 1    | dur_hi   | Duration in minutes, high byte       |
| 11     | 1    | dur_lo   | Duration in minutes, low byte        |

Duration is computed as `((time_length_secs + 86400) % 86400) / 60`.

**set_light_source** — Choose built-in or external light sensor:

| Offset | Size | Field | Description                         |
|--------|------|-------|-------------------------------------|
| 0-3    | 4    | header| `0F 45 03 02`                       |
| 4      | 1    | index | uint8, source slot index            |
| 5      | 1    | type  | 0 = built-in sensor, 1 = external   |

**get_light_data** — The `src_idx` byte packs two fields: `(source << 1) | index`.

### Delay

| Command      | Bytes                                           | Size  | Description         |
| ------------ | ----------------------------------------------- | ----- | ------------------- |
| set_delay    | `0F 45 06 01 <ts:8> [FF] 01 <mode...>`          | 15-16 | Set delayed action  |
| clear_delay  | `0F 45 06 00`                                   | 4     | Clear delay         |
| get_delay    | `0F 46 06`                                      | 3     | Get delay settings  |

**set_delay** — Schedule a position change after a delay:

| Offset | Size | Field     | Description                              |
|--------|------|-----------|------------------------------------------|
| 0-3    | 4    | header    | `0F 45 06 01`                            |
| 4-11   | 8    | timestamp | uint64 big-endian, Unix epoch seconds (now + delay) |
| 12     | 1    | pad       | `0xFF` — **only present on fw < 20**     |
| 12/13  | 1    | fixed     | `0x01`                                   |
| 13-15  | 3    | action    | Same as set_position mode/target/position |

Total: 16 bytes (fw < 20) or 15 bytes (fw >= 20).

**get_delay** — Response (6 bytes):

| Offset | Size | Field     | Description                 |
|--------|------|-----------|-----------------------------|
| 0      | 1    | status    | Status code                 |
| 1-4    | 4    | timestamp | Unix timestamp (big-endian) |
| 5      | 1    | position  | Target position (0-100)     |

### Timers / Schedules

Timer commands use `0x08`/`0x09` prefixes instead of the extended command format.

| Command          | Bytes                              | Size | Description          |
| ---------------- | ---------------------------------- | ---- | -------------------- |
| get_timer_count  | `08 02`                            | 2    | Get number of timers |
| get_timer        | `08 <idx_byte>`                    | 2    | Get timer at index   |
| set_timer_count  | `09 02 <count>`                    | 3    | Set timer count      |
| set_timer        | `09 <idx_byte> <hdr:4> 01 <act:3>` | 9    | Save timer at index  |

**Index byte encoding** (shared by get_timer and set_timer):
`idx_byte = ((index << 4) & 0xF0) | 0x06` — index in bits 4-7, fixed `0x06` in bits 0-3.

**set_timer** — Full layout:

| Offset | Size | Field      | Description                                    |
|--------|------|------------|------------------------------------------------|
| 0      | 1    | prefix     | `0x09`                                         |
| 1      | 1    | idx_byte   | Index encoding (see above)                     |
| 2      | 1    | enable     | bit 7: enabled flag                            |
| 3      | 1    | repeat     | bits 0-6: weekday bitmap, or `0x80` if no repeat |
| 4      | 1    | hour       | uint8, 0-23                                    |
| 5      | 1    | minute     | uint8, 0-59                                    |
| 6      | 1    | fixed      | `0x01`                                         |
| 7-9    | 3    | action     | Same as set_position mode/target/position      |

### Group / Link Info

| Command                    | Bytes            | Size | Description                |
| -------------------------- | ---------------- | ---- | -------------------------- |
| get_group_firmware_battery | `0F 46 46 06`    | 4    | Get group firmware/battery |
| get_group_charge_info      | `0F 46 46 07`    | 4    | Get group charge info      |
| get_group_links            | `0F 46 02 FF 03` | 5    | Get group links info       |
| get_device_link            | `0F 46 02 FF 04` | 5    | Get device link info       |
