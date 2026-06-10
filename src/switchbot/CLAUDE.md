# Integration architecture

Four layers, bottom-up:

1. **`proto/`** — pure wire protocol. No HA imports. Typed, tested. (Its own
   CLAUDE.md covers conventions.)
2. **`core.py`** — framework base on HA's *light* passive-bluetooth coordinator:
   - `SwitchbotCoordinator[T]` extends `PassiveBluetoothDataUpdateCoordinator`.
     It owns the BLE subscription, the typed `data: T | None` state, and (per
     subclass) the command/GATT path. Subclasses implement `_parse(service_info)
     -> T | None` and `create_platform_entities(platform)`.
   - `SwitchbotEntity[T]` extends `PassiveBluetoothCoordinatorEntity`; a thin
     view that re-renders on coordinator updates. Availability comes from the
     coordinator.
3. **`devices/<model>.py`** — the per-device object (a `SwitchbotCoordinator`
   subclass): parses advertisements into a typed state, holds the command
   methods, and declares the device's entities.
4. **Platform files + `config_flow.py`** — `sensor.py`/`binary_sensor.py`/
   `cover.py` are 3-line forwarders via `platform_setup_entry_factory`.
   `config_flow.py` is Bluetooth-discovery-only.

## Conventions (keep these)

- **Device-major authorship.** `create_platform_entities(platform)` is the
  single source of truth for what a device exposes. Platform files stay thin
  forwarders — never put per-device logic in them. (HA forces domain-major
  *registration*; we keep device-major *authorship* on top.)
- **Typed, flat, non-optional state.** The coordinator combines its inputs into
  one flat frozen dataclass with no `None` fields, so entities read
  `data.position` / `data.battery` directly. Don't expose a loosely-typed dict.
- **Stickiness in the coordinator.** When a device's advertisement spans
  multiple BLE fields (e.g. blind tilt: manufacturer + service data, delivered
  in separate frames), the coordinator retains the last-seen of each and only
  emits state once all required parts have been seen. Parsing of each field
  stays pure in `proto/`; combining/retention is the coordinator's job.
- **State lives on `entry.runtime_data`** (a `ConfigEntry[SwitchbotCoordinator]`),
  not a global registry.
- **Light coordinator family, not the processor stack.** We use
  `PassiveBluetoothDataUpdateCoordinator` + `PassiveBluetoothCoordinatorEntity`
  — NOT `PassiveBluetoothProcessorCoordinator` and its entity-key/descriptor
  dicts.
- **Single device registry.** `devices/__init__.py` holds a `REGISTRY` keyed by
  each proto module's `DEVICE_TYPE` (model identity) → `DeviceEntry(device_type,
  name, coordinator)`. Both `build_coordinator` and `config_flow` derive from
  it, so registering a device (or a variant sharing a coordinator) is one entry
  — don't hardcode type bytes in the config flow.

## Adding a device

Get the protocol right first, then wire it in:
- new device → `add-proto`; protocol already exists but unchecked (e.g. an
  inlined lib) → `verify-proto`; a **variant of an existing device** (its decomp
  parser/device class extends another's) reuses that proto — share it, don't
  duplicate;
- then `add-hass` to add the coordinator/entities + one registry entry.

References: `blind_tilt.py` (two-field advert, combined flat state) and
`curtain3.py` (single-field state used directly; a reused/variant protocol).
