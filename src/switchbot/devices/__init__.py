from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from ..platforms import SwitchbotDevice
from ..proto import DeviceType
from .blind_tilt import BlindTiltCoordinator
from .curtain3 import Curtain3Coordinator
from .leak import LeakCoordinator

# (hass, address, name, last-seen advertisement) -> the device's runtime object
CoordinatorFactory = Callable[
    [HomeAssistant, str, str, bluetooth.BluetoothServiceInfoBleak | None],
    SwitchbotDevice,
]


@dataclass(frozen=True)
class DeviceEntry:
    device_type: str  # config-entry key
    name: str  # default display name
    coordinator: CoordinatorFactory


# Single source of truth for supported devices, keyed by the proto model-identity
# (`DeviceType`, i.e. the type byte with reserved + pairing bits masked off).
REGISTRY: dict[int, DeviceEntry] = {
    DeviceType.BLIND_TILT: DeviceEntry(
        "blind_tilt", "Blind Tilt", BlindTiltCoordinator
    ),
    DeviceType.CURTAIN3: DeviceEntry("curtain3", "Curtain 3", Curtain3Coordinator),
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
