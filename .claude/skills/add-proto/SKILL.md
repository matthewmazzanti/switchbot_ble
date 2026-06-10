---
name: add-proto
description: Reverse-engineer and write the pure protocol layer (proto/<device>/) for a SwitchBot device, verified byte-for-byte against the decompiled app. Use when adding support for a new device's wire protocol (advertisement, commands, responses), before wiring it into Home Assistant (see add-hass).
---

# Add a device's protocol layer

Write `src/switchbot/proto/<device>/` — the pure, HA-free, typed wire protocol —
verified against the decompiled app. This is protocol work only; wiring into the
integration is the separate `add-hass` skill. `proto/blind_tilt/` is the
reference implementation; read it and `src/switchbot/proto/CLAUDE.md` first.

## 1. Ground in the decompiled app

The decompiled app is the source of truth — never guess bit layouts.

- Ensure `decomp/` is populated: if `decomp/VERSION` is missing, run `just decomp`
  (downloads + decompiles; needs the dev-shell tools). Read `decomp/CLAUDE.md`
  for the investigation map.
- Locate the device's authoritative sources (by the patterns in
  `decomp/CLAUDE.md`):
  - advertisement: `protocol/scan/delegate/Wo<Device>Parser.java`
  - commands — source varies by device: either a `protocol/<Device>Cmd.java`
    name→bytes map (**omits the leading 0x57**; `CmdMapper` prepends it) +
    argument builders in `impl/<device>/dto/Wo<Device>Device.java`, or **no map**
    with everything built in `protocol/CmdGenerator.java` (per-device
    `*Action.java` classes delegate to it). Check both.
  - responses/notifications: `impl/<device>/usecase/*NotifyCase.java` and
    `*Read*Case.java`
- Remember Java bytes are signed: `-1`=0xFF, `-126`=0x82, `-127`=0x81.
- **Check whether this is a variant of an existing device.** If the decomp
  parser/device class *extends* another (e.g. `WoCurtain3Parser extends
  WoCurtainParser`, `WoCurtain3Device extends WoCurtainDevice`), the variant
  reuses that protocol — share the existing `proto/<base>` (especially the
  commands) and only model the genuinely-new fields. Don't create a redundant
  package or re-derive shared commands. (Curtain 3 reuses curtain's commands +
  advertisement core, adding only alarm fields.) Device-type identities live in
  the `proto.DeviceType` IntEnum; each advert module sets `DEVICE_TYPE =
  DeviceType.X` (reserved+pairing bits masked), and the registry keys on it.
- **Don't stop at the per-device commands — also look for the shared/generic
  command layer.** `getActions()`, `<Device>Cmd.java`, and `*Action.java` only
  cover this model's *specific* commands; cross-device commands (Wi-Fi
  onboarding, OTA, time, region, …) live unnamed in `CmdGenerator.java` +
  `impl/common/...`, so an empty `getActions()` is *not* command-less. This is
  the **shared-command-layer trap in `decomp/CLAUDE.md`** (see also *Shared/
  generic commands* in its source map) — the leak-detector port missed it at
  first. Wi-Fi devices' onboarding is already modeled in `proto/wifi_setup/`:
  reuse it.

## 2. Write the modules

Under `src/switchbot/proto/<device>/`, mirroring `blind_tilt/`:

- `advertisement.py` — one frozen dataclass **per BLE field** (service data
  `0xFD3D` and/or manufacturer data `0x0969`). Each gets `parse(bytes)` and
  `to_bytes()`. Keep intra-field derived values as `@property`. Do NOT combine
  fields or retain state here — that's the coordinator's job.
- `commands.py` — command dataclasses using the `core` helpers (`ext_set`,
  `ext_get`, `notify`, `timer_get/set`, `FixedCommand`, `build`). Headers +
  argument bytes from the command source identified in step 1 (the `cmdMap` +
  `Wo<Device>Device.java`, or `CmdGenerator.java`).
- `responses.py` — reply dataclasses from the notify/read parsers
  (`reply[0]` is the status byte).
- `__init__.py` — export the public classes.

Use relative imports within proto (`from ..core import ...`). No HA imports.
Add a brief `# <Java file>` citation comment for any non-obvious bit layout.

Apply the **wire-mapping traps in `decomp/CLAUDE.md`** while writing each field —
a parser line gives you the *bit*, not the *meaning*. Transcribe each from its
source and cite it; the canonical list (boolean polarity, `pair_mode`-is-a-value,
field widths from the read path, signed bytes, the `0x57` prepend, split adverts,
reused constants, the shared command layer) is there, not restated here.

If `core/` lacks a needed subsystem/helper, add it there.

## 3. Verify as you write — don't guess

Verification is **inline, not a separate phase**: write each command, field, and
response by reading its authoritative decomp source, and cite the `file:line` in
a comment. Transcribe from the source, never from intuition; the roundtrip tests
(next step) are the regression net.

You do **not** need a full separate comparison pass over code you just derived
from the source — that's redundant. `verify-proto` is for the other case
(existing proto of unknown provenance, or audits). Only for an unusually large
or high-risk surface, consider running `/verify-proto` afterward as an
independent adversarial check.

## 4. Test

Add tests in `tests/proto/test_<device>_*.py`. Roundtrips (`parse`↔`to_bytes`)
are necessary but **not sufficient** — they pass even if you transcribed a
polarity or source wrong, because encode/decode are symmetric. So also add
**byte-level assertions anchored to the app's actual bytes** (the exact frame /
indices / masks the decomp uses), which is what actually catches a wrong
interpretation. Run `uv run pytest tests/proto` (or `just test`); pyright must
be clean: `uv run pyright src/switchbot`.

## 5. Hand off

Stop here — do not touch `devices/`, `config_flow.py`, or platform files.
Report the alignment results (and anything that needs real-hardware
confirmation). The next step is `add-hass`.
