# SwitchBot BLE — Home Assistant custom component

A custom Home Assistant integration for SwitchBot Bluetooth-LE devices. At
runtime it loads as `custom_components.switchbot`; locally the package is
`src/switchbot/` (imported as `switchbot`). Currently supports **blind tilt**
and **curtain 3** (classic curtain is deferred — the hardware on hand is a
Curtain 3, so that's what's wired up).

## Dev environment

- The dev shell **auto-loads via direnv** (`.envrc`) when you enter the project,
  so its tools are already on PATH — Python 3.14, `uv`, `just`, `pyright`, and
  the APK decompile toolchain (`apkeep`, `unzip`, `jq`, `jadx`). Don't wrap
  commands in `nix develop`.
- If the flake/env changes, the **running session won't pick it up** — ask the
  user to restart Claude Code (which reloads direnv) rather than trying to
  refresh the env inline.
- Python deps are managed by `uv` (Python 3.14, Home Assistant 2026.6.1).
- The dev shell and the `home-assistant:stable` container (see `just run-hass`)
  both ship Python 3.14 — keep them aligned.

## Commands

- `just check` — pyright + ruff + pytest (the pre-commit gate).
- `just test` — `uv run pytest`.
- `uv run pyright src/switchbot` / `uv run ruff check src tests` / `just format`.
- `just run-hass` — run HA in podman with this component mounted (needs `sudo`;
  if it prompts, run it yourself via `! just run-hass`).
- `just decomp` — (re)generate `./decomp/` from the SwitchBot APK.

## Skills (project workflows)

Index only — see each skill for the canonical "what/when".

- `add-proto` — write a new device's protocol layer from the decompiled app.
- `verify-proto` — audit/fix existing protocol against the decompiled app
  (for proto that wasn't written against decomp, or after an app update).
- `add-hass` — wire a verified protocol layer into the integration.

**Adding a device:** write or check the protocol (`add-proto` for new,
`verify-proto` for existing/inlined), then `add-hass`.

## Layout

```
src/switchbot/
  proto/        pure wire protocol (HA-free, typed, tested) — see its CLAUDE.md
  core.py       coordinator + entity base (on HA passive-bluetooth)
  devices/      per-model coordinator + entity definitions
  *.py          thin platform files (sensor/binary_sensor/cover) + config_flow
tests/proto/    protocol roundtrip tests
docs/protocol/  decompiled-app protocol notes (BLIND_TILT.md, PROTOCOL.md)
tools/apk/      APK download/decompile script
decomp/         decompiled app source (gitignored; see decomp/CLAUDE.md)
```

See `src/switchbot/CLAUDE.md` for the integration architecture and conventions.

## Gotchas

- Importing the `switchbot` package pulls in HA's bluetooth import graph, which
  needs `aiousbwatcher` / `serialx` / `aioesphomeapi` (HA normally installs
  these from integration manifests at runtime; they're dev deps here so the
  package — and the proto tests — import locally).
- `decomp/`, `.claude/`, and the `new_proto` symlink are gitignored.
- Work happens on feature branches off `dev`; commit only when asked.
