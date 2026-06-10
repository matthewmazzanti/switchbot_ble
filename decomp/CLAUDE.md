# Decompiled SwitchBot app — investigation map

This directory holds the decompiled SwitchBot Android app, the **authoritative
reference** for the BLE protocol. It is gitignored except this file; run
`just decomp` to (re)populate it. Mapped against app **v9.11.15.13** (check
`decomp/VERSION`). Java line numbers drift across versions — rely on the
package/naming patterns below, not specific lines.

## Layout

```
decomp/
  download/   raw .xapk / .apk
  apks/ dex/ lib/   intermediate extraction
  src/        decompiled Java (pruned to protocol-relevant packages)
  VERSION     app version string
```

Source lives under `src/com/theswitchbot/`. The decompile prunes to:
`device/protocol`, `device/impl`, `device/consts`, `device/abs`,
`device/control`, `connector`, and `thingclips/ble`.

## Where things live (by pattern)

- **Advertisement parsing** → `device/protocol/scan/delegate/Wo<Device>Parser.java`
  (e.g. `WoBlindTiltParser.java`). `getRunData(...)` reads the service data
  (arg `broadcastData`, byte 0 = device type) and `scanRecord`'s
  manufacturer-specific data (`keyAt == 2409`). `isForThisType` shows the
  accepted device-type bytes. Extra/complex fields: `scan/kn/*Parser.java`.
- **Command header map** → `device/protocol/<Device>Cmd.java` (e.g.
  `BlindTiltCmd.java`): a `cmdMap` of name → bytes. **These omit the leading
  `0x57`** — `device/protocol/CmdMapper.java` (`mapCmd`/`mapGeneralCmd`)
  prepends it (`MAGIC_NUM = 87`).
- **Command argument builders** → `device/impl/<device>/dto/Wo<Device>Device.java`.
  This is where the bytes appended after the header are assembled (e.g.
  `actionPayload`, `saveActionMode`, `setDirectionCmd`). Prefer this over the
  generic `device/protocol/CmdGenerator.java` when they differ — the per-device
  builder is what actually runs.
- **Shared/generic commands** → `device/protocol/CmdGenerator.java` is the flat
  catalog of *every* command the app can send — much of it cross-device and
  named after the *function*, not the device: Wi-Fi onboarding, OTA, time/UTC,
  region, base/device-info, password/key, groups (its `WOCODE_REQ_*` constants
  enumerate the sub-command space). These are driven by orchestrators in
  `device/impl/common/...` (e.g. `setting/WifiDeviceTools.java`), not a
  per-device file, so a `getActions()`/`<Device>Cmd.java` search won't surface
  them. Replies parse in `device/protocol/ble/BleMsgParser.java`
  (`parseWifiStatus`/`parseWifiIP`/`parseAwsKey`/`parseBaseInfo`/…). See the
  shared-command-layer trap below.
- **Use cases** (which command + args a feature sends, and reply parsing) →
  `device/impl/<device>/usecase/*Case.java`. Notifications/replies are parsed
  in `*NotifyCase.java` (e.g. `BlindTiltNotifyCase` has `positionNotify` /
  `calibrationNotify`) and read handlers in `*Read*Case.java`.
- **Generic reply helpers** → `device/protocol/ble/BleMsgParser.java`,
  `device/protocol/ReplyParserKt.java` (`statusCode()` = `reply[0]`).
- **Shared constants** → `device/consts/`, plus reused per-device constants
  (note: `WoHumidifierUtil.WOCODE_HUMIDIFIER_CODE_STATUS_CODE = -127 = 0x81` is
  reused as the blind-tilt group-read sub-byte).

## Wire-mapping traps (canonical)

The recurring ways a decomp line misleads — a parser line gives you the *bit*,
not the *meaning*. This is the single source of truth for both proto skills:
`add-proto` applies these **inline while writing** each field; `verify-proto`
**audits against** them. Parenthetical evidence is from past ports.

- **Boolean polarity** — confirm a flag's *meaning*, not just its bit position,
  by tracing how the app *consumes* it (status handler, UI, run-data value); the
  field name lies. (Inverted `moving` in blind tilt, `calibrated` in curtain.)
- **`pair_mode` is the device-type *value*, not a flag** — the type byte takes
  two values differing by bit 5 (e.g. `0x58`/`0x78`); the lower is pairing.
  `isForThisType` shows both accepted values.
- **Field widths from the *read* path** — when a builder appends an opaque helper
  (`HexUtil.longToBytes(...)`, not in the pruned tree), confirm the width from
  the read side (`subArray(reply, 1, 5)` ⇒ 4 bytes). (Delay timestamps are 4
  bytes; an early port packed 8.)
- **Command-map bytes omit the leading `0x57`** — `CmdMapper`
  (`mapCmd`/`mapGeneralCmd`, `MAGIC_NUM = 87`) prepends it; map `{15,69,1}` is
  `57 0F 45 01` on the wire.
- **Java bytes are signed** — `-1`=`0xFF`, `-126`=`0x82`, `-127`=`0x81`; read `& 0xFF`.
- **Firmware-gated payloads** — `actionPayload` fw ≥ 20 → `05 FF`, else `01 01`,
  built in `Wo<Device>Device.java`.
- **Adverts may span two BLE fields** — service (`0xFD3D`) + manufacturer
  (`0x0969`, bytes 0–6 = MAC), delivered in separate frames; or live in a single
  field. Check which.
- **Constants reused from other devices** — blind tilt's group sub-byte is
  `WOCODE_HUMIDIFIER_CODE_STATUS_CODE` (`0x81`), not `0x46`.
- **Prefer the per-device builder** (`Wo<Device>Device.java`) over the generic
  `CmdGenerator.java` when they differ — the per-device one is what runs.
- **The shared/generic command layer is invisible to a per-device search** — an
  empty `getActions()` and no `<Device>Cmd.java` map do *not* mean command-less.
  Generic commands live only in `CmdGenerator.java` + `impl/common/...`
  orchestrators (see *Shared/generic commands* above) and aren't named after the
  device. Spot a Wi-Fi device by its `Mqtt<Device>Status.java`
  (`online`/`wifiConnectionFailed`) or use of `WifiDeviceTools.java`; its BLE
  onboarding surface is modeled in `proto/wifi_setup/` — reuse it. These are
  *connected* GATT write/notify flows, unlike passive-advertisement status.
