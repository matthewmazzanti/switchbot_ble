---
name: add-hass
description: Wire an already-written protocol layer (proto/<device>/) into the Home Assistant integration — coordinator, entities, config-flow, platforms. Use after add-proto, when the device's wire protocol exists and is verified.
---

# Wire a device into the integration

Given a verified `custom_components/switchbot/proto/<device>/`, add the Home Assistant layer.
Read `custom_components/switchbot/CLAUDE.md` for the architecture and conventions, and use
`custom_components/switchbot/devices/blind_tilt.py` as the reference implementation.

## 1. Confirm the scope with the user FIRST

The proto usually exposes far more than a first pass should surface (e.g. dozens
of commands, several advertisement fields). Do **not** default to wiring up
everything.

- Read the proto and enumerate what *could* become entities, grouped by
  platform: the primary control (cover/switch/…), sensors (battery, position,
  light, …), binary sensors (calibrated, moving, stuck, …), and optional
  controls/diagnostics (calibration, light rules, timers, direction, …).
- Propose a scope — **default to a minimal first pass** (the primary entity +
  battery) — and **confirm with the user via `AskUserQuestion`** before
  building. Offer the minimal set, a fuller set, and let them adjust.
- Build only the agreed entities. List what you deferred so it's easy to extend
  later. The proto already covers the wire side, so adding more entities later
  is cheap.

## 2. The device coordinator + state

Create `custom_components/switchbot/devices/<device>.py`:

- State: a **flat, frozen, typed** dataclass with **no `None` fields**. If the
  advertisement spans multiple BLE fields, give a `<Device>State` a
  `combine(...)` classmethod that builds it from the per-field proto dataclasses
  (see `blind_tilt.py`). If the surfaced entities come from a **single** field,
  just use that proto dataclass directly as the state (see `curtain3.py`).
- `class <Device>Coordinator(SwitchbotCoordinator[<Device>State])`:
  - `__init__`: choose `mode` (ACTIVE if you need scan-response data) and
    `connectable` (True if you issue GATT commands). Initialize any
    last-seen fields, then `super().__init__(..., initial=self._parse(adv) if
    adv else None)`.
  - `_parse(service_info) -> <Device>State | None`: parse whichever proto
    field(s) the frame carries, **retain the last-seen of each** (stickiness),
    and return the combined state — or `None` until all required parts have
    been seen. This is where combine/stickiness lives (not in proto).
  - Command methods (if controllable): an `async_send_command(payload)` that
    connects via `establish_connection` under an `asyncio.Lock` and writes
    `WRITE_CHAR_UUID`, plus per-action helpers that build bytes from
    `proto/<device>` commands.
  - `create_platform_entities(platform)`: the **single source of truth** for
    the device's entities. Reuse `generic_entity.Sensor` / `BinarySensor` with
    flat `lambda data: data.<field>` callbacks; add a dedicated entity class
    (e.g. a cover) only when a platform needs behavior.

## 3. Register the device

- Add a member to **`proto.DeviceType`** (the model-identity enum) for the new
  device, then add **one `REGISTRY` entry** in `devices/__init__.py` keyed on it:
  `DeviceType.<NAME>: DeviceEntry("<device>", "<Display Name>",
  <Device>Coordinator)`. That's it — `build_coordinator` derives from
  the registry, and `config_flow` detects the device automatically via the same
  registry + `device_type()` masking (so `0x__`-normal and pairing forms both
  match). Nothing to add in `config_flow.py`.
  - A **variant that shares another device's coordinator** just maps its own
    `DEVICE_TYPE` to that existing coordinator — no new coordinator class.
- `__init__.py` — ensure `PLATFORMS` includes any platform the device uses that
  isn't already listed.

## 4. Verify

- `just check` (pyright + ruff + pytest) must be clean.
- Then exercise it in the real app: `just run-hass` (podman, needs `sudo` — if
  it prompts, ask the user to run `! just run-hass`). Confirm the device is
  discovered, entities appear, and commands work.
- Flag anything that can only be confirmed against real hardware (e.g. battery
  scale, position direction).

## Conventions (don't violate)

- Device-major: no per-device logic in the platform files; they stay 3-line
  forwarders via `platform_setup_entry_factory`.
- Flat typed state, no Optionals reaching entities.
- Light passive-bluetooth coordinator family only (no processor/descriptor
  stack). State on `entry.runtime_data`.
