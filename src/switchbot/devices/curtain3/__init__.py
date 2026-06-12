"""Curtain 3 Home Assistant integration: standalone device + dual group.

`single.py` is the standalone curtain (coordinator + entities); `group.py` is
the two-member dual group (member coordinators + glue + entities). This module
is the family entry point the dispatch matches delegate to: `build` (setup) and
`addable` (config flow).
"""

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant

from ...platforms import SwitchbotDevice
from ...proto.curtain3 import Curtain3ServiceData
from .group import Curtain3Group, resolve_secondary
from .single import Curtain3Coordinator, parse_advertisement

__all__ = [
    "Curtain3Coordinator",
    "Curtain3Group",
    "addable",
    "build",
    "parse_advertisement",
]


def addable(svc: bytes) -> bool:
    """Config-flow filter: only a *primary* curtain is independently addable.

    A secondary is reached through its primary and never becomes its own entry,
    so reject it. (Whether the primary is standalone or a group head is decided
    later, at setup — see `build`.)
    """
    try:
        return Curtain3ServiceData.parse(svc).is_primary
    except ValueError:
        return False


async def build(
    hass: HomeAssistant,
    address: str,
    name: str,
    adv: bluetooth.BluetoothServiceInfoBleak | None,
) -> SwitchbotDevice:
    """Setup: interview the chain and build a group or a standalone curtain.

    The chain read (`resolve_secondary`) is the single source of truth, run fresh
    every setup — so regrouping/ungrouping is picked up on reload rather than
    being baked into the config entry.
    """
    secondary = await resolve_secondary(hass, address, name)
    if secondary is not None:
        return Curtain3Group(hass, address, secondary, name, adv)
    return Curtain3Coordinator(hass, address, name, adv)
