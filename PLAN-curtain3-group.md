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

## Config flow + setup (decision deferred to setup)

- **Dispatch = two `match`es over `DeviceType`** (`devices/__init__.py`), no
  registry: `discovered(svc)` (config flow) and `build_device(...)` (setup), each
  delegating to per-device logic. `entry.data` persists the `DeviceType` value
  (int) + address + name.
- **Config flow = advert-only, no connect.** `discovered` rejects unsupported
  models and **Curtain 3 secondaries** (`is_primary=False` → reached through the
  primary, not its own entry). It does NOT decide group-vs-standalone — that's
  deferred to setup. (`is_group` / `CONF_IS_GROUP` removed.)
- **Setup interviews, every time.** `curtain3.build` runs the chain read fresh on
  every setup (`resolve_secondary` → `GetChainInfo.next_mac`): a real MAC ⇒
  group (build `Curtain3Group`), empty (`EMPTY_MAC`) ⇒ standalone. One read
  decides *both* "is it a group?" and the secondary MAC. Raises
  `ConfigEntryNotReady` on BLE failure → HA retries with backoff.
  - *Why interview always:* a group must connect for the secondary regardless, so
    a passive advert pre-check only saved a connect for standalones — not worth a
    second code path or relying on advert freshness. The interview is the single
    source of truth.
- **Accepted tradeoffs:** standalone curtains now connect once at setup too (were
  connection-free) → need to be reachable (mitigated by `ConfigEntryNotReady`
  retry); ~2s connect latency per setup. Runtime re-grouping is picked up on the
  next reload/restart (not live).

## Open design questions (runtime layout — interrogating next)

1. **`cover.both` semantics:** position when member0 ≠ member1 (avg? min?), and
   is it a positionable cover or open/close/stop-only?
2. **left/right physical identification:** deferred — needs a visual identify
   (shake); `OPEN_INVERSE` only gives member0/1, not room side. v1: name
   primary/secondary, let users rename.

## Proto / core gaps before building HA layer

- [x] Proto reply parsers — done **across the board** (`responses.py`), not just
      `GetChainInfo`: ChainInfo/CurtainInfo/MoveInfo/Direction/WorkMode/CaliMode/
      CaliDistance/DelayInfo/SettingsInfo/LightAction, each byte-for-byte verified
      vs decomp (workflow: map + adversarial verify). `ChainInfoReply.next_mac`
      [14:20] is the setup-read field. See [[proto-completeness]].
- [x] Core: **send-and-return-bytes** + coordinator-free exchange. Done —
      collapsed `ConnectableSwitchbotCoordinator` into `core.async_command(hass,
      address, payload) -> bytes` (free function; returns the raw OK-checked
      reply) + `SwitchbotCoordinator.async_send_command` (adds the per-device
      lock). Setup chain-read can now call `async_command` with no coordinator.
- [x] Chain command bytes confirmed: request is `57 0F 46 02 00 01` (`00`, per
      decomp `CmdGenerator` + the workflow agents) — proto's `GetChainInfo` is
      already correct; only the `PROTOCOL.md` doc had the stale `FF`. Fix that doc
      line when next touching docs.
- [x] **Wiring gap (resolved):** a group is NOT its own `DeviceType`, so it can't
      be a registry row. Resolved by dropping the registry for `match`-over-
      `DeviceType` dispatch — `curtain3.build` (the CURTAIN3 case) interviews the
      chain and constructs a group or standalone itself, no group discriminator
      needed in the entry.

## Deferred (NOT v1)

- Persistent `secondary_mac` cache in `entry.data` + background refresh (avoids
  startup connect). Skipped for simplicity; re-read on setup instead.
- Live drift detection (passive `in_group` nibble watch, on-connect re-read,
  re-registerable secondary callback).
- Physical left/right auto-identification via shake.

## Cleanup (post-implementation)

- [x] Member index constants moved into `proto/` as `CurtainIndex(IntEnum)`
  (PRIMARY/SECONDARY/BOTH), consolidating the old INDEX_* in both proto + group;
  `MotionMode(IntEnum)` too. `index: CurtainIndex` locked on SetPercentage/Stop +
  the group command path (the 1/2/3 bitmask). NB: `index` is non-uniform —
  GetMoveInfo/calibration/settings use a 0-based device index, left as `int`.
  (Found + fixed: GetMoveInfo's default 1 was reading the secondary; now 0.)
- [ ] Remaining `IntEnum`s for the response "related state" ints surfaced by the
  parsers (`motion_status`, `action_mode`, `threshold_type`, cali mode, work
  mode, …) — give names + validation instead of bare ints.
- [x] Device registry reworked → `match`-over-`DeviceType` dispatch (`discovered`
  + `build_device` in `devices/__init__.py`), delegating to per-device logic.
  `REGISTRY`/`DeviceEntry`/`build_coordinator` removed; the entry persists the
  `DeviceType` value (int), and the per-device "metadata" (card name) is inlined
  in the `discovered` match. Cost: the device list lives in two matches.

## Sequencing (rough)

1. ✅ `devices/curtain3_group.py`: `Curtain3Group` glue object (two per-member
   `Curtain3Coordinator`s, primary connectable / secondary advert-only) + command
   routing + per-member covers + `cover.both` (dual-coordinator) + per-member
   battery & calibrated entities. `generic_entity` gained an injectable
   `device_info`; `Curtain3Coordinator` gained a `connectable` kwarg. Unwired so
   far.
2. ✅ Proto: full reply parsers + verified chain command bytes.
3. ✅ Core: `async_request`/`async_send_command` (typed call/respond primitive).
4. ✅ Wiring: `match`-over-`DeviceType` dispatch (`discovered` + `build_device`);
   `curtain3.build` interviews the chain at setup → group vs standalone.
5. ✅ Config flow: primaries-only `discovered`, advert-only add (DeviceType in
   entry.data); group/standalone decision deferred to the setup interview.
6. Tests + run against the real pair (F8:58.. primary / DE:8B.. secondary).
