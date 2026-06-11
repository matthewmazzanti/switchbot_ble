#!/usr/bin/env python
"""One-off: print the first BLE advertisement seen for each Curtain 3 MAC.

Bootstraps a bleak scanner, waits for one advertisement from each target MAC,
decodes it with the `proto/curtain3` parsers, and exits once both are seen (or
after --secs).

Run (Linux / BlueZ — addresses are real MACs there):

    uv run python tools/scan_curtain3.py
    uv run python tools/scan_curtain3.py --secs 30   # give up after 30s

Needs the BLE adapter reachable to the user running it (no root on most BlueZ
setups; if you hit a DBus/permission error, run it outside the sandbox).
"""

from __future__ import annotations

import argparse
import asyncio

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from switchbot.proto.core.core import (
    MANUFACTURER_ID,
    SWITCHBOT_SERVICE,
    device_type,
    is_pairing,
)
from switchbot.proto.curtain3 import Curtain3ManufacturerData, Curtain3ServiceData

# The dual-config pair. Keyed upper-case for case-insensitive matching against
# whatever casing the backend hands back.
TARGETS = {
    "F8:58:26:DD:C4:92": "dev1",
    "DE:8B:03:B9:39:B8": "dev2",
}


def _hex(b: bytes) -> str:
    return b.hex(" ")


def decode(name: str, address: str, adv: AdvertisementData) -> str:
    lines = [f"\n[{name}] {address}  rssi={adv.rssi}"]

    svc = adv.service_data.get(SWITCHBOT_SERVICE)
    if svc is None:
        lines.append("  service-data: (not in this frame)")
    else:
        lines.append(f"  service-data {_hex(svc)}")
        s = Curtain3ServiceData.parse(svc)
        t = svc[0]
        lines.append(
            f"    type=0x{t:02x} (id=0x{device_type(t):02x}"
            f"{', PAIRING' if is_pairing(t) else ''})"
        )
        lines.append(
            f"    is_primary={s.is_primary} in_group={s.in_group} "
            f"calibrated={s.calibrated} pos={s.position} batt={s.battery} "
            f"too_hot={s.too_hot}  (chain nibble={svc[4] & 0x0F})"
        )

    mfg = adv.manufacturer_data.get(MANUFACTURER_ID)
    if mfg is None:
        lines.append("  mfg-data: (not in this frame)")
    else:
        lines.append(f"  mfg-data    {_hex(mfg)}")
        m = Curtain3ManufacturerData.parse(mfg)
        lines.append(
            f"    pre_group={m.pre_group} ear_type={m.ear_type} "
            f"geomag={m.geomag_alarm} temp_hi={m.temp_too_high} "
            f"temp_lo={m.temp_too_low}"
        )
    return "\n".join(lines)


async def scan(secs: float) -> None:
    seen: set[str] = set()
    done = asyncio.Event()

    def on_detect(device: BLEDevice, adv: AdvertisementData) -> None:
        name = TARGETS.get((device.address or "").upper())
        if name is None or name in seen:
            return
        print(decode(name, device.address, adv))
        seen.add(name)
        if len(seen) == len(TARGETS):
            done.set()

    scanner = BleakScanner(detection_callback=on_detect)
    print(f"Scanning for {', '.join(TARGETS)} ...")
    await scanner.start()
    try:
        await asyncio.wait_for(done.wait(), timeout=secs)
    except asyncio.TimeoutError:
        pass
    finally:
        await scanner.stop()
        missing = set(TARGETS.values()) - seen
        if missing:
            print(f"\nNote: never saw {', '.join(sorted(missing))} in {secs:g}s.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--secs", type=float, default=30.0, help="give up after N seconds")
    args = ap.parse_args()
    asyncio.run(scan(args.secs))


if __name__ == "__main__":
    main()
