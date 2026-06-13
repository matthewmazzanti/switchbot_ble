# SwitchBot BLE

A custom [Home Assistant](https://www.home-assistant.io/) integration for
SwitchBot Bluetooth-LE devices. It talks to the devices directly over BLE — no
cloud, no hub required — using Home Assistant's passive-bluetooth stack.

> **Independent project — not affiliated with SwitchBot.** See
> [Disclaimer](#disclaimer) below.

## Supported devices

| Device     | Status                                   |
| ---------- | ---------------------------------------- |
| Curtain 3  | Supported                                |
| Blind Tilt | Supported                                |
| Water Leak Detector | Supported                       |

Classic Curtain is deferred (the hardware on hand is a Curtain 3, so that's
what's wired up).

## Installation

### HACS (custom repository)

1. In HACS → ⋮ → **Custom repositories**, add `https://github.com/matthewmazzanti/switchbot_ble` with type **Integration**.
2. Install **SwitchBot BLE** from HACS, then restart Home Assistant.

### Manual

Copy `custom_components/switchbot/` from this repo into your Home Assistant
config under `custom_components/`, then restart Home Assistant.

Either way, devices are picked up automatically via Bluetooth discovery.

> **Note:** the domain is `switchbot`, which overrides Home Assistant's built-in
> SwitchBot integration. Remove or rename one if you do not intend that.

## Development

The dev shell auto-loads via direnv (`.envrc`). See [`CLAUDE.md`](CLAUDE.md) for
the architecture, layout, and workflows.

- `just check` — pyright + ruff + pytest (the pre-commit gate)
- `just test` — run the test suite
- `just run-hass` — run Home Assistant in a container with this component mounted

## Disclaimer

This project is an independent, community-developed integration. It is **not
affiliated with, authorized, endorsed, or sponsored by SwitchBot or Wonderlabs,
Inc.** "SwitchBot" and related names and logos are trademarks of their
respective owners and are used here only nominatively, to identify the devices
this software interoperates with.

It is an **interoperability reimplementation**: the BLE wire protocol it speaks
(frame layouts, command bytes, advertisement fields) consists of functional
facts about the devices, determined in order to interoperate with hardware the
author owns. No source code or other copyrightable expression from any SwitchBot
application is reproduced or distributed here.

Use at your own risk. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).

## License

[MIT](LICENSE) © 2026 Matthew Mazzanti
