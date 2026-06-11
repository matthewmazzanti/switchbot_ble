# Curtain 3 dual-group — planning (scratch, trim later)

Goal: support a SwitchBot Curtain 3 **dual group** (two curtains, one window) in
HA. Scaffolding notes from the decomp investigation + design decisions so far.

## Decisions locked

- **Vocabulary:** `primary` / `secondary` for roles (was master/slave —
  renamed, committed `1e8dc48`). `left` / `right` / `both` for user-facing
  entities. No linked-list naming (see two-node ceiling).
- **Device model:** ONE HA "group" device (identified by the primary) exposing
  `cover.primary` + `cover.secondary` + `cover.both`, plus per-member battery.
  Standalone curtains stay a single cover (today's path).
- **Two-node ceiling is real:** the app has no `WO_CURTAIN_2_*` data path and its
  command index is a 2-bit member mask (1=member0, 2=member1, 3=both). A 3+ chain
  is not creatable via the app. So `secondary` (not `next`) is honest.
- **Role detection (advert flags):** a curtain is born primary; grouping demotes
  exactly one to secondary (decomp: `getMeta(isMaster, true)` default-true;
  pairing sets one true / one false). Three states:

  | state | `is_primary` | `in_group` |
  |---|---|---|
  | standalone     | True  | False |
  | group primary  | True  | True  |
  | group secondary| False | False |

  `is_primary=False` ⇒ secondary. `in_group` splits standalone vs group head.
  (Caveat: inferred from app *meta* defaults; not yet observed on a standalone
  advert byte — cheap to confirm by scanning an ungrouped unit.)

- **State is fully passive.** Each MAC advertises its own position+battery, so
  monitoring BOTH adverts yields both members' live state with no polling. A
  connection is needed ONLY for (a) commands, (b) the one-time chain read at
  setup. (Resolves the old state-sourcing fork — no `GetCurtainInfo` poll.)

- **Architecture: two coordinators + a thin glue object (NOT one unified
  coordinator).** Rather than bend the single-address passive coordinator to two
  MACs, use two idiomatic `Curtain3Coordinator`s (one per curtain — own address,
  own availability, own `track_unavailable`, own `data`) and a `Curtain3Group`
  glue object that subscribes to nothing. The glue owns the three genuinely
  group-level concerns: identity (`device_info`), the unique-id namespace, and the
  command path. Primary is `connectable=True` (command target); secondary is
  `connectable=False` (pure advert source — relayed to via the primary, never
  connected to directly).
  - *Why:* the combine has to live *somewhere* (`cover.both` needs both
    positions); putting it in the glue/entity layer keeps each coordinator on the
    framework's happy path. Earlier unified-coordinator approach (one coordinator,
    dual `async_register_callback`, MAC-routing in `_parse`, gated combined state,
    overridden availability) worked but leaned on the abstraction; replaced.

- **Per-entity availability falls out for free.** Each member's entities read
  their own coordinator's availability, so `cover.secondary` goes unavailable when
  *its* beacons time out while the primary/`both` stay live. No gated combined
  state needed; the "don't publish a missing half" concern is handled per-entity.

- **`device_info` is injected, not derived from the coordinator.** Entities attach
  to a device via `device_info.identifiers`, independent of their state
  coordinator. The glue hands every entity ONE `device_info` (primary
  `identifiers`, BOTH MACs in `connections`), so secondary-backed entities land on
  the same device. Needed a small `generic_entity.Sensor/BinarySensor` change:
  optional `device_info` param (falls back to `coordinator.device_info`).

- **`cover.both` is the only multi-coordinator entity.** It subscribes to both
  coordinators (override `async_added_to_hass`, add a 2nd `async_add_listener`
  → same `_handle_coordinator_update`), is `available` only when both are, and
  renders the averaged position. Everything else is a vanilla single-coordinator
  entity.

## Config flow + setup (simple model)

- **Config flow = advert-only, no connect.** Discovery only offers **primaries**
  (`is_primary=True`); secondaries (`is_primary=False`) never appear in the
  picker. On add, store just `{primary_mac, is_group=in_group}` in `entry.data`.
  After the user picks, branch on `in_group`: False → standalone single-cover
  device; True → group device.
- **Setup does the connect.** `async_setup_entry` is async; for a group it reads
  the chain once to learn the secondary:
  ```
  async_setup_entry(entry):                 # entry.data = {primary_mac, is_group}
      if is_group:
          try: secondary_mac = (await read_chain_info(primary_mac)).next_mac
          except BleError: raise ConfigEntryNotReady   # HA retries w/ backoff
          coordinator = GroupCoordinator(primary_mac, secondary_mac)
      else:
          coordinator = Curtain3Coordinator(primary_mac)   # standalone
      entry.runtime_data = coordinator
      entry.async_on_unload(coordinator.async_start())
      await async_forward_entry_setups(entry, PLATFORMS)
  ```
  Re-reads the chain every setup (restart/reload) = "re-interview on startup",
  done as ordinary setup. No persistent cache, no drift detector, no
  re-registerable callback.
- **Accepted tradeoffs:** runtime re-grouping is picked up on next reload/restart
  (not live); every startup needs the primary reachable before the group works
  (mitigated by `ConfigEntryNotReady` retry).

## Open design questions (runtime layout — interrogating next)

1. **`cover.both` semantics:** position when member0 ≠ member1 (avg? min?), and
   is it a positionable cover or open/close/stop-only?
2. **left/right physical identification:** deferred — needs a visual identify
   (shake); `OPEN_INVERSE` only gives member0/1, not room side. v1: name
   primary/secondary, let users rename.

## Proto / core gaps before building HA layer

- [ ] Proto `GetChainInfo` reply parser (`pre_mac` [2..7], `next_mac` [14..19]).
      Maybe `GetCurtainInfo` parser too (pos0/batt0/pos1/batt1, link_length [3])
      even though state is advert-sourced — useful for the setup read / debugging.
- [x] Core: **send-and-return-bytes** + coordinator-free exchange. Done —
      collapsed `ConnectableSwitchbotCoordinator` into `core.async_command(hass,
      address, payload) -> bytes` (free function; returns the raw OK-checked
      reply) + `SwitchbotCoordinator.async_send_command` (adds the per-device
      lock). Setup chain-read can now call `async_command` with no coordinator.
- [ ] `verify-proto` on chain commands: `PROTOCOL.md` shows `GetChainInfo` as
      `…02 FF 01` but decomp `CmdGenerator` emits `…02 00 01` (`{2,0,1}`).
      Decomp authoritative → send `00`.
- [ ] **Wiring gap:** a group is NOT its own `DeviceType` (both members are
      `CURTAIN3`), so the registry/`build_coordinator` path (keyed on
      `device_type`) and the `(hass, address, name, adv)` factory signature don't
      fit — no slot for `secondary_mac`, no group/standalone discriminator. Need
      a group construction path: `entry.data` carries `{primary, secondary,
      is_group}`; setup branches on `is_group` and constructs the group
      coordinator directly (outside the DeviceType registry).

## Deferred (NOT v1)

- Persistent `secondary_mac` cache in `entry.data` + background refresh (avoids
  startup connect). Skipped for simplicity; re-read on setup instead.
- Live drift detection (passive `in_group` nibble watch, on-connect re-read,
  re-registerable secondary callback).
- Physical left/right auto-identification via shake.

## Sequencing (rough)

1. ✅ `devices/curtain3_group.py`: `Curtain3Group` glue object (two per-member
   `Curtain3Coordinator`s, primary connectable / secondary advert-only) + command
   routing + per-member covers + `cover.both` (dual-coordinator) + per-member
   battery & calibrated entities. `generic_entity` gained an injectable
   `device_info`; `Curtain3Coordinator` gained a `connectable` kwarg. Unwired so
   far.
2. Proto: chain-info reply parser + verify chain command bytes.
3. Core: send-and-return-bytes primitive.
4. Wiring: group construction path (entry.data {primary, secondary, is_group};
   setup branches on is_group; not DeviceType-keyed).
5. Config flow: primaries-only discovery → advert-only add; setup chain read.
6. Tests + run against the real pair (F8:58.. primary / DE:8B.. secondary).
