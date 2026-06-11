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

- **Coordinator can listen to two MACs (verified).** Override the PUBLIC
  `async_start()` (not protected `_async_start`): call `super().async_start()`
  for the primary, then `bluetooth.async_register_callback` the secondary MAC
  (`connectable=False`, passive-only), and return a composed unsub. `self.address`
  stays the primary, so availability + connection target are correctly keyed to
  it. (Public-API only; no reach into `_on_stop`.)

- **Secondary advert drives STATE, not availability.** Its handler updates the
  secondary slice + `async_update_listeners()`, but does NOT go through the base
  event path (which would flip `_available`). Availability stays primary-only, so
  a chatty secondary can't mask an unreachable primary.

- **Coarse fan-out is accepted (v1).** `async_update_listeners()` pokes every
  entity on every advert from either MAC; unchanged values don't emit
  `state_changed` (HA dedups), so it's cheap. Selective per-member dispatch would
  need the processor stack (deliberately unused) — not worth it.

- **Combined state = gated, both required (locked).** `Curtain3GroupState(primary,
  secondary)` — both non-optional, built only once BOTH members have advertised
  once, then last-seen of each retained (the `blind_tilt` sticky pattern). A group
  with a missing half isn't published. Availability stays primary-keyed (base
  path); during the brief initial window before the secondary is first heard the
  group is `available` but `data is None` (entities read unknown), same as
  blind_tilt. Availability is also gated on `data is not None` (overridden
  `available`), so the group reads unavailable — not available-unknown — until
  both members are first seen; sticky state keeps it available if the secondary
  later goes silent.

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
- [ ] Core: a **send-and-return-bytes** command variant. `_send_command_once`
      already captures the notify `raw` but discards it after the status check
      (`core.py:224`); thread it back so setup can read the chain reply.
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

1. ✅ `devices/curtain3_group.py`: group coordinator (two-MAC subscribe + primary
   command path, gated combined state, gated availability) + primary/secondary/
   both covers + per-member battery & calibrated entities. Unwired so far.
2. Proto: chain-info reply parser + verify chain command bytes.
3. Core: send-and-return-bytes primitive.
4. Wiring: group construction path (entry.data {primary, secondary, is_group};
   setup branches on is_group; not DeviceType-keyed).
5. Config flow: primaries-only discovery → advert-only add; setup chain read.
6. Tests + run against the real pair (F8:58.. primary / DE:8B.. secondary).
