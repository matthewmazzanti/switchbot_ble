---
name: verify-proto
description: Verify an existing proto/<device>/ against the decompiled SwitchBot app — compare every command, advertisement field, and response byte-for-byte, report alignment with file:line evidence, and fix mismatches. Use when the proto already exists and wasn't written against decomp (inlined but never checked — e.g. curtain), to audit after an app update, or as an optional independent check on a large/high-risk surface. Not needed after add-proto, which verifies inline as it writes.
---

# Verify a protocol layer against the decompiled app

Compare an existing `src/switchbot/proto/<device>/` to the authoritative
decompiled app and fix any mismatch. The decompiled app is the source of truth
— never accept the Python as correct on faith. (Verification caught an inverted
`moving` bit + wrong battery source + 8-vs-4-byte timestamp + wrong subsystem
byte in blind tilt, and an inverted `calibrated` bit + wrong `pair_mode` +
8-vs-4-byte timestamp in curtain.)

**Passing tests do NOT mean aligned.** Roundtrip (`to_bytes`↔`parse`) tests stay
green even when the bit interpretation is wrong, because encode/decode are
symmetric. Verify against the decomp, not the test suite — and assume existing
tests may *encode the bug* (curtain shipped a `test_calibration_bit_inverted`
that asserted the wrong polarity).

## 1. Prepare

- Ensure `decomp/` is populated: `just decomp` if `decomp/VERSION` is missing.
  Read `decomp/CLAUDE.md` for the investigation map.
- Read the modules under `src/switchbot/proto/<device>/` (advertisement,
  commands, responses) and the `core/` helpers they use.
- Locate the authoritative sources (patterns in `decomp/CLAUDE.md`):
  advertisement `protocol/scan/delegate/Wo<Device>Parser.java`; responses
  `impl/<device>/usecase/*NotifyCase.java` and `*Read*Case.java`. For commands,
  the source varies by device:
  - some have a `protocol/<Device>Cmd.java` byte map (omits the leading `0x57`;
    `CmdMapper` prepends it) + argument builders in
    `impl/<device>/dto/Wo<Device>Device.java` (blind tilt);
  - others have **no map** and build everything in `protocol/CmdGenerator.java`,
    with per-device `*Action.java` classes delegating to it (curtain). Check
    both; grep `CmdGenerator.java` for `<device>` builders.

  Also audit coverage of the **shared/generic** command layer — a `<device>`
  grep and an empty `getActions()` miss it (the *shared-command-layer trap* in
  `decomp/CLAUDE.md`). Treat a missing shared surface (e.g. a Wi-Fi device's
  onboarding, modeled in `proto/wifi_setup/`) as a coverage gap.

## 2. Compare every item

For each command, advertisement field, and response: compute the exact bytes
the Python emits (or the indices/masks it parses) and compare to the decompiled
source. Record **ALIGNED / MISMATCH with a `file:line` citation** for each.

If the surface is large, **fan out parallel comparisons** — e.g. one agent per
command group plus one for responses — giving each the relevant proto snippet +
the decomp paths and asking for a citation-backed table. (This is how the
blind-tilt command/response surface was checked.)

Check each item against the **wire-mapping traps in `decomp/CLAUDE.md`** (boolean
polarity, `pair_mode`-is-a-value, field widths from the read path, the `0x57`
prepend, signed bytes, firmware-gated payloads, split adverts, reused constants,
per-device-over-generic builder, the shared command layer) — that canonical list
is not restated here. The audit difference is *stance*: don't just read each trap
off, actively try to **refute** the Python against the decomp, and assume the
existing tests may encode the same wrong assumption (see the intro warning).

## 3. Fix and record

- Fix every MISMATCH in the proto. Add/extend `tests/proto/` with byte-level
  assertions that lock the corrected format — and **audit existing tests**: any
  that asserted the old behavior (or whose name encodes a wrong assumption, like
  `*_bit_inverted`) must be corrected, not left green.
- Correct stale comments (e.g. enum meanings the app never actually decodes).
- Note anything only confirmable on real hardware (e.g. battery scale, position
  direction).

## 4. Gate

`just test` (or `uv run pytest tests/proto`), `uv run pyright src/switchbot`,
`uv run ruff check src tests`. Then report the alignment results.
