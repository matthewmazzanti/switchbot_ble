from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from ..platforms import SwitchbotDevice
from ..proto import DeviceType
from .blind_tilt import BlindTiltCoordinator
from .curtain3 import Curtain3Coordinator
from .curtain3 import discovery as curtain3_discovery
from .leak import LeakCoordinator

# (hass, address, name, last-seen advertisement) -> the device's runtime object
CoordinatorFactory = Callable[
    [HomeAssistant, str, str, bluetooth.BluetoothServiceInfoBleak | None],
    SwitchbotDevice,
]
# Optional per-device config-flow filter. Given the service-data bytes, returns
# extra entry.data to store, or None to reject the discovery (not addable).
DiscoveryHook = Callable[[bytes], dict[str, Any] | None]


@dataclass(frozen=True)
class DeviceEntry:
    device_type: str  # config-entry key
    name: str  # default display name
    coordinator: CoordinatorFactory
    discovery: DiscoveryHook | None = None


# Single source of truth for supported devices, keyed by the proto model-identity
# (`DeviceType`, i.e. the type byte with reserved + pairing bits masked off).
# TODO(rethink): as DeviceEntry grows (factory + discovery hook + future setup
# hooks), weigh replacing this dict/dataclass with a function-based dispatch that
# matches on the type byte and injects per-device logic inline — the open
# question is cleanly carrying the per-device metadata (device_type, name). See
# PLAN-curtain3-group.md "Cleanup".
REGISTRY: dict[int, DeviceEntry] = {
    DeviceType.BLIND_TILT: DeviceEntry(
        "blind_tilt", "Blind Tilt", BlindTiltCoordinator
    ),
    DeviceType.CURTAIN3: DeviceEntry(
        "curtain3", "Curtain 3", Curtain3Coordinator, curtain3_discovery
    ),
    DeviceType.LEAK: DeviceEntry("leak", "Water Leak Detector", LeakCoordinator),
}

_BY_DEVICE_TYPE: dict[str, DeviceEntry] = {
    entry.device_type: entry for entry in REGISTRY.values()
}


def build_coordinator(
    hass: HomeAssistant,
    device_type: str,
    address: str,
    name: str,
    adv: bluetooth.BluetoothServiceInfoBleak | None,
) -> SwitchbotDevice:
    entry = _BY_DEVICE_TYPE.get(device_type)
    if entry is None:
        raise ValueError(device_type)
    return entry.coordinator(hass, address, name, adv)
