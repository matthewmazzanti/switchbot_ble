# SwitchBot BLE Protocol - Reverse Engineering Notes

Based on APK version 9.11.15.13

## General Protocol Structure

### BLE Characteristics
- Service UUID: `cba20d00-224d-11e6-9fb8-0002a5d5c51b`
- Write Characteristic: `cba20002-224d-11e6-9fb8-0002a5d5c51b`
- Notify Characteristic: `cba20003-224d-11e6-9fb8-0002a5d5c51b`

### Packet Structure

All commands start with magic byte `0x57` (87 decimal, 'W' for WonderLabs).

```
[0x57] [CMD_TYPE | FLAGS] [PASSWORD_CRC32 (4 bytes, if encrypted)] [PAYLOAD...]
```

**CMD_TYPE values:**
- `0x00` - Common command
- `0x01` - Action command
- `0x02` - Version/Info request
- `0x03` - Set mode
- `0x07` - Set password
- `0x0F` - Extended command

**Flags (OR'd with CMD_TYPE):**
- `0x00` - No password
- `0x04` - Password required (CRC32 of password in bytes 2-5)

### Extended Commands (0x0F)

Extended commands have additional sub-command bytes:
```
[0x57] [0x0F] [EXT_CMD] [SUB_CMD] [PAYLOAD...]
```

**EXT_CMD values:**
- `0x45` (69) - SET command
- `0x46` (70) - GET command

---

## Device Type Bytes

Known device type bytes:

| Device | Type Byte | Hex |
|--------|-----------|-----|
| Bot | 0x48 | H |
| Curtain | 0x63 | c |
| Curtain 3 | 0x7B | { |
| Blind Tilt | 0x64 | d |
| Meter | 0x54 | T |
| Meter Plus | 0x69 | i |
| Contact Sensor | 0x64 | d |
| Motion Sensor | 0x73 | s |
| Water Detector | 0x26 | & |
| Lock | 0x6F | o |
| Hub Mini | 0x76 | v |
| Plug Mini | 0x67 | g |
| Strip Light | 0x72 | r |

---

## Blind Tilt Protocol

Device Type: `0x64`

Disambiguated from Contact Sensor (also `0x64`) via advertisement byte:
`broadcast_data[0] & 0x7F` equals `0x78` or `0x58` for Blind Tilt.

### Commands

Commands use EXT_SET (0x45) for writes and EXT_GET (0x46) for reads.
All payloads below follow the `[0x57, CMD_TYPE|FLAGS]` packet header.
Sizes listed are payload only (add 2 bytes for header, 4 more if password).

#### Movement & Control

```
set_position (6 bytes)
  [0x0F, 0x45, 0x01, mode:1, target:1, position:1]

  mode/target varies by firmware version:
    fw >= 20: mode=0x05, target=0xFF
    fw <  20: mode=0x01, target=0x01
  position: uint8, 0-100 (tilt percentage)

stop (5 bytes)
  [0x0F, 0x45, 0x01, 0x00, 0x01]

enable_notify (8+ bytes)
  [0x0E, 0x01, time_unit:1, interval:1, 0xFF, 0xFF, read_info_cmd:3]

  read_info_cmd: specifies what to report; [0xF2, 0x01, 0x00] = get_position
  Device pushes 7-byte notifications on cba20003:
    [status:1, run_status:1, reserved:4, position:1]
    run_status: 0=stopped, 1=opening, 2=closing

disable_notify (2 bytes)
  [0x0E, 0x00]
```

#### Direction & Mode

```
set_direction (6 bytes)
  [0x0F, 0x45, 0x04, 0x06, 0x01, direction:1]

  direction: (value | 0x02)
    0x02 = horizontal (input 0)
    0x03 = vertical   (input 1)

set_action_mode (6 bytes)
  [0x0F, 0x45, 0x04, 0x01, 0x01, mode:1]

  mode: uint8
```

#### Calibration

```
start_calibration (4 bytes)
  [0x0F, 0x45, 0x05, 0x01]

stop_calibration (4 bytes)
  [0x0F, 0x45, 0x05, 0x02]

save_calibration (5 bytes)
  [0x0F, 0x45, 0x05, 0x09, preset:1]

  preset: uint8
    1 = zero position
    2 = mid position
    3 = full position
```

#### Delay

```
set_delay (15-16 bytes)
  [0x0F, 0x45, 0x06, 0x01, timestamp:8, [0xFF], 0x01, mode:1, target:1, position:1]

  timestamp: uint64 big-endian, Unix epoch seconds (current time + delay)
  0xFF byte: only present on fw < 20
  mode/target/position: same as set_position

clear_delay (4 bytes)
  [0x0F, 0x45, 0x06, 0x00]
```

#### Light Sensitivity

```
set_light_action (7+ bytes)
  [0x0F, 0x45, 0x03, 0x01, index:1, 0x01, mode:1, target:1, position:1]

  index: uint8, low nibble only (& 0x0F), 0-15
  mode/target/position: same as set_position

set_light_rule (12 bytes)
  [0x0F, 0x45, 0x03, 0x01, rule_payload:8]

  rule_payload byte layout:
    [0] (index | 0x10):      bits 0-3 = index (0-15), bit 4 = rule flag
    [1] threshold_flags:     bit 6 = enable, bits 4-5 = threshold_type (1=higher, 2=lower)
    [2] threshold:           bits 0-3 = threshold value (0-15)
    [3] repeat_days:         bits 0-6 = weekday bitmap (bit 6=Sun .. bit 0=Sat), & 0x7F
    [4] start_hour:          uint8, 0-23
    [5] start_minute:        uint8, 0-59
    [6] duration_hi:         duration in minutes, high byte
    [7] duration_lo:         duration in minutes, low byte
                             duration = ((time_length_secs + 86400) % 86400) / 60

set_light_source (6 bytes)
  [0x0F, 0x45, 0x03, 0x02, index:1, type:1]

  index: uint8
  type:  0 = built-in sensor, 1 = external sensor

clear_light_actions (4 bytes)
  [0x0F, 0x45, 0x03, 0x03]

set_ai_light (4+ bytes)
  [0x0F, 0x45, 0x03, 0x04, ...]

clear_ai_light (4 bytes)
  [0x0F, 0x45, 0x03, 0x05]
```

#### Timers

Timer commands use a different prefix (0x08/0x09) instead of extended commands.

```
get_timer_count (2 bytes)
  [0x08, 0x02]

get_timer (2 bytes)
  [0x08, index_byte:1]

  index_byte: ((index << 4) & 0xF0) | 0x06
    index in bits 4-7, fixed 0x06 in bits 0-3

set_timer_count (3 bytes)
  [0x09, 0x02, count:1]

  count: uint8

set_timer (7-9 bytes)
  [0x09, index_byte:1, header:4, 0x01, mode:1, target:1, position:1]

  index_byte: ((index << 4) & 0xF0) | 0x06  (same encoding as get_timer)
  header:
    [0] enable:        bit 7 = enabled flag
    [1] repeat_days:   bits 0-6 = weekday bitmap (& 0x7F), or 0x80 if no repeat
    [2] hour:          uint8, 0-23
    [3] minute:        uint8, 0-59
  mode/target/position: same as set_position
```

#### Read Commands (GET)

```
get_position               (4 bytes)  [0x0F, 0x46, 0x01, 0x00]
get_light_info             (4 bytes)  [0x0F, 0x46, 0x03, 0x00]
get_light_action           (5 bytes)  [0x0F, 0x46, 0x03, 0x01, index:1]
get_light_source           (4 bytes)  [0x0F, 0x46, 0x03, 0x02]
get_light_data             (6 bytes)  [0x0F, 0x46, 0x03, 0x04, time_range:1, src_idx:1]
                                        src_idx: (source << 1) | index
get_ai_light_count         (4 bytes)  [0x0F, 0x46, 0x03, 0x06]
get_ai_light_action        (4 bytes)  [0x0F, 0x46, 0x03, 0x07]
get_advanced_info          (4 bytes)  [0x0F, 0x46, 0x04, 0x02]
get_action_mode            (4 bytes)  [0x0F, 0x46, 0x04, 0x03]
get_calibration            (3 bytes)  [0x0F, 0x46, 0x05]
get_delay                  (3 bytes)  [0x0F, 0x46, 0x06]
get_calibration_step       (3 bytes)  [0x0F, 0x46, 0x09]
get_work_mode              (4 bytes)  [0x0F, 0x46, 0x82, 0x03]
get_group_firmware_battery (4 bytes)  [0x0F, 0x46, 0x46, 0x06]
get_group_charge_info      (4 bytes)  [0x0F, 0x46, 0x46, 0x07]
get_group_links            (5 bytes)  [0x0F, 0x46, 0x02, 0xFF, 0x03]
get_device_link            (5 bytes)  [0x0F, 0x46, 0x02, 0xFF, 0x04]
```

---

## Curtain Protocol

Device Type: `0x63` (Curtain), `0x7B` (Curtain 3)

### Commands

**Movement:**
```
curtainPercentage:     [0x57, 0x0F, 0x45, 0x01, 0x05, <index>, <percent>]
curtainStop:           [0x57, 0x0F, 0x45, 0x00, 0xFF, <index>]
curtainMove:           [0x57, 0x0F, 0x45, 0x01, <direction>, <index>]
                       direction: 0x01=open, 0x02=close
```

**Calibration:**
```
curtainCalibration:    [0x57, 0x0F, 0x45, 0x01, <action>]
curtainCalibrationMode:[0x57, 0x0F, 0x45, 0x01, 0x00, <mode>, 0x00, <index>]
curtainCalibrationPause:[0x57, 0x0F, 0x45, 0x01, 0x00, 0x03, <index>]
curtainCalibrationTest:[0x57, 0x0F, 0x45, 0x01, <action>]
```

**Settings:**
```
setCurtainOpenDirection: [0x57, 0x0F, 0x45, 0x01, <dir1>, <dir2>, <index>]
curtainOpenInverse:      [0x57, 0x0F, 0x45, 0x05, <index>, <inverse...>]
curtainTouchGo:          [0x57, 0x0F, 0x45, 0x01, 0x07, <enable>, <index>]
curtainMotionMode:       [0x57, 0x0F, 0x45, 0x01, <mode>, <index>]
curtainShake:            [0x57, 0x0F, 0x45, 0x01, 0x08]
```

**Grouping:**
```
curtainLinkage:        [0x57, 0x0F, 0x45, 0x05, <secondaryMac_bytes>]
curtainUngroup:        [0x57, 0x0F, 0x45, 0x08]
curtainChainInfo:      [0x57, 0x0F, 0x46, 0x02, 0xFF, 0x01]
curtainChainStatus:    [0x57, 0x0F, 0x46, 0x02, 0xFF, 0x02]
```

**Light Sensitive:**
```
curtainLightInfo:      [0x57, 0x0F, 0x46, 0x03, 0x00]
curtainLightData:      [0x57, 0x0F, 0x46, 0x03, <timeRange>, <source>, <index>]
curtainLightActionList:[0x57, 0x0F, 0x46, 0x03, 0x01, <index>]
curtainLightSource:    [0x57, 0x0F, 0x46, 0x03, 0x02, <index>, <source>]
curtainLight:          [0x57, 0x0F, 0x45, 0x03, 0x01, <enable>, <index>]
curtainClearAction:    [0x57, 0x0F, 0x45, 0x03, 0x03]
```

**Delay:**
```
curtainDelayInfo:      [0x57, 0x0F, 0x46, 0x06]
curtainClearDelay:     [0x57, 0x0F, 0x45, 0x06, 0x00]
curtainSetDelay:       [0x57, 0x0F, 0x45, 0x06, 0x01, <delayData...>]
```

**Info/Status:**
```
readCurtainInfo:       [0x57, 0x02]
readCurtainMoveInfo:   [0x57, 0x0F, 0x46, 0x01, 0x01, <index>]
curtainSettingInfo:    [0x57, 0x0F, 0x46, 0x04, 0x02]
curtainAdvancedInfo:   [0x57, 0x0F, 0x46, 0x04, 0x02]
curtainWorkMode:       [0x57, 0x0F, 0x46, 0x82, 0x03]
curtainReadCaliMode:   [0x57, 0x0F, 0x46, 0x04, 0x03]
getCurtainCaliDistance:[0x57, 0x0F, 0x46, 0x04, 0x04]
getCurtainDirection:   [0x57, 0x0F, 0x46, 0x04, 0x05]
curtainReadLightSource:[0x57, 0x0F, 0x46, 0x03, 0x02, 0x00]
```

**Misc:**
```
curtainReboot:         [0x57, 0x0F, 0x45, 0x04, 0x08]
curtainResetPwm:       [0x57, 0x0F, 0x45, 0x04, 0x09]
setCurtainTinyAdjust:  [0x57, 0x0F, 0x45, 0x04, 0x0A]
```

---

## Water Detector (Leak Sensor) Protocol

Device Type: `0x26` (normal), `0x06` (pairing/add mode)
Manufacturer ID: `2409` (0x0969)

### BLE Advertisement Data Parsing

Manufacturer data (19 bytes):

| Byte | Description |
|------|-------------|
| 0-5 | Header/MAC info |
| 6 | Sequence number |
| 7 | Battery level (bits 0-6, bit 7 unused) |
| 8 | Status byte (see below) |
| 9-12 | Last state change time (UTC, big-endian) |
| 13 | Alarm duration (seconds) |
| 14 | Alarm interval time |
| 15-18 | Test press time (UTC, big-endian) |

**Status byte (byte 8) breakdown:**
- Bit 7 (0x80): Alarm mode (0=dehydrate/dry, 1=inundate/wet alert)
- Bit 6 (0x40): Current state (0=dry, 1=wet)
- Bit 5 (0x20): Is currently alarming
- Bits 3-4 (0x18): Alarm volume (0-3)
- Bit 2 (0x04): Beat/heartbeat state
- Bits 0-1 (0x03): Alarm count

### MQTT Status Fields

| Field | Description |
|-------|-------------|
| battery | Battery percentage |
| alertMode | Alert trigger mode |
| status | Current water detection status |
| isTest | Test mode active |
| alarmVolume | Volume level |
| isAlerting | Currently sounding alarm |
| wifiConnectionFailed | WiFi connection status |
| changeTime | Last state change timestamp |
| alarmtDuration | Alarm sound duration |
| alarmInterval | Interval between alarms |
| online | Device online status |

---

## WiFi Setup Commands (Hub/WiFi-enabled devices)

These commands are used for devices with WiFi capability (Hub Mini, Water Detector with Hub, etc.)

### Constants
```
WOCODE_REQ_SET_NET_SSID = 0x01
WOCODE_REQ_SET_NET_PW   = 0x02
WOCODE_REQ_SET_NET_OVER = 0x03
```

### Command Implementations

**Scan for WiFi Networks:**
```
scanSsidCmd:           [0x57, 0x0F, 0x10, <payloadCmd>]
```

**Get WiFi Info:**
```
getSsidCmd:            [0x57, 0x0F, 0x11, <index>, <section>]
getWifiStatusCmd:      [0x57, 0x0F, 0x04]
getWifiDeviceInfo:     [0x57, 0x00, 0x03]
getWifiIp:             [0x57, 0x0F, 0x13, 0x02]
getAwsKeyCmd:          [0x57, 0x0F, 0x09]
```

**Set SSID (chunked for long names):**
```
Packets chunked at 11 bytes each:
  for each chunk:
    [0x57, 0x0F, 0x01, totalLen:1, chunkIndex:1, ssidBytes:1-11]
```

**Set Password (chunked):**
```
if empty:
  [0x57, 0x0F, 0x02, 0x01, 0x00, 0x00]
else for each chunk:
  [0x57, 0x0F, 0x02, totalLen:1, chunkIndex:1, pwBytes:1-11]
```

**Complete Network Setup:**
```
netSetupOver:          [0x57, 0x0F, 0x03]
```

**Set Region:**
```
setRegionCmd:          [0x57, 0x0F, 0x0C, <region>]
```

**WiFi OTA:**
```
startWifiOTA:          [0x57, 0x0F, 0x05, <version>]
wifiOTAStatus:         [0x57, 0x0F, 0x06]
```

---

## Password/Encryption

When password is set on device:

1. Password is converted to CRC32
2. CRC32 (4 bytes, little-endian) placed in packet bytes 2-5
3. Packet CMD_TYPE has bit 0x04 set

```
if password is set:
    crc = CRC32(password_bytes)
    packet[2] = crc & 0xFF
    packet[3] = (crc >> 8) & 0xFF
    packet[4] = (crc >> 16) & 0xFF
    packet[5] = (crc >> 24) & 0xFF
```

---

## Notes

- All multi-byte integers are big-endian unless noted
- MTU is 20 bytes - commands may need chunking
- The app uses Tuya/ThingClips SDK (`libBleLib.so`) for some BLE operations
- Devices may support both encrypted and unencrypted modes
- Position values typically 0-100 (percentage)
- Timer commands use different format (0x08/0x09 prefix) vs extended commands (0x0F prefix)
