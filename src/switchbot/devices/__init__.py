from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from ..platforms import SwitchbotDevice
from ..proto import DeviceType
from ..proto.core import device_type as model_identity
from . import curtain3
from .blind_tilt import BlindTiltCoordinator
from .leak import LeakCoordinator

# Device dispatch is two `match`es over DeviceType (the proto type-byte identity),
# each fanning out to per-device logic — instead of a central registry dataclass.
# `discovered` is the config-flow side (identity + addability); `build_device` is
# the setup side. Adding a device touches both (the cost of dropping the central
# registry). See PLAN-curtain3-group.md "Cleanup".


def discovered(svc: bytes) -> tuple[int, str] | None:
    """Config flow: a discovered device's `(DeviceType, card name)`, or None if
    the model is unsupported or this unit isn't independently addable."""
    match model_identity(svc[0]):
        case DeviceType.CURTAIN3:
            return (DeviceType.CURTAIN3, "Curtain 3") if curtain3.addable(svc) else None
        case DeviceType.BLIND_TILT:
            return (DeviceType.BLIND_TILT, "Blind Tilt")
        case DeviceType.LEAK:
            return (DeviceType.LEAK, "Water Leak Detector")
        case _:
            return None


async def build_device(
    hass: HomeAssistant,
    *,
    device_type: int,
    address: str,
    name: str,
    adv: bluetooth.BluetoothServiceInfoBleak | None,
) -> SwitchbotDevice:
    """Setup: build the per-entry runtime device, dispatching on the stored
    DeviceType. Curtain 3 interviews the chain (async); the rest construct
    directly."""
    match device_type:
        case DeviceType.CURTAIN3:
            return await curtain3.build(hass, address, name, adv)
        case DeviceType.BLIND_TILT:
            return BlindTiltCoordinator(hass, address, name, adv)
        case DeviceType.LEAK:
            return LeakCoordinator(hass, address, name, adv)
        case _:
            raise ValueError(f"unsupported device type: {device_type}")
