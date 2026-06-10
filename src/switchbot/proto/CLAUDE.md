# Protocol layer (`proto/`)

Pure SwitchBot BLE wire protocol: **no Home Assistant imports**, fully typed,
roundtrip-tested. One subpackage per device family (`blind_tilt/`, `curtain3/`)
plus shared `core/` wire helpers. Each module decodes/encodes a single concept
1:1 with the wire; combining fields and retaining state is the *consumer's* job
(the coordinator), not this layer's.

## Wire conventions (`core/`)

- Every command frame starts with `MAGIC = 0x57`.
- `ext_set(*sub)` → `57 0F 45 <sub...>`, `ext_get(*sub)` → `57 0F 46 <sub...>`
  (`CMD_EXT=0x0F`, `EXT_SET=0x45`, `EXT_GET=0x46`). Also `notify`, `timer_get`,
  `timer_set`. `SUB_*` constants name the subsystem bytes.
- `FixedCommand` is the base for parameterless fixed-wire commands.
- The blind-tilt "action" payload is firmware-versioned: fw ≥ 20 →
  `05 FF <position>` (modern), fw < 20 → `01 01 <position>` (legacy).
- **Device type / pair mode.** The advertisement type byte encodes the model
  *and* pairing state: bit 5 (`PAIRING_BIT`) is clear in pairing mode, and the
  remaining bits are the model identity. `core.device_type(b)` (`& 0x5F`) gives
  the identity; `core.is_pairing(b)` reports pairing. Identities are catalogued
  in the `proto.DeviceType` IntEnum (each advert module sets `DEVICE_TYPE =
  DeviceType.X`); the integration's registry keys on `DeviceType`, not raw bytes.

## Advertisements span two BLE fields

A device's advertisement may be split across **service data** (UUID `0xFD3D`)
and **manufacturer data** (company id `0x0969` / 2409), delivered in separate
radio frames — parse each independently (one dataclass per field) and let the
coordinator combine/retain them. Some devices keep the core in one field
(curtain 3's core is all service data; its manufacturer data only adds extras).
Where manufacturer data carries device fields, bytes 0–6 are the MAC.

## The decompiled app is the source of truth

`decomp/src/` (run `just decomp` to populate) is the authoritative reference —
see `decomp/CLAUDE.md` for the map. **Every command, field, and response must
be verified against it, citing `file:line`.** Do not guess bit layouts. The
hand-guessed predecessor got `moving` polarity and the battery source wrong;
the decompiled app settled both.

`docs/protocol/BLIND_TILT.md` records the verified blind-tilt layout.

## Tests

Roundtrip `parse`/`to_bytes` (and combined `parse(...)` for split adverts) in
`tests/proto/`. These are HA-free in principle, but importing through the
`switchbot` package still triggers HA (see the root CLAUDE.md gotcha).
