"""Curtain 3 Home Assistant integration: standalone device + dual group.

`single.py` is the standalone curtain (coordinator + entities); `group.py` is
the two-member dual group (member coordinators + glue + entities).
"""

import typing as ty

from ...core import CONF_IS_GROUP
from ...proto.curtain3 import Curtain3ServiceData
from .group import Curtain3Group, build_group
from .single import Curtain3Coordinator, parse_advertisement

__all__ = [
    "Curtain3Coordinator",
    "Curtain3Group",
    "build_group",
    "discovery",
    "parse_advertisement",
]


def discovery(svc: bytes) -> dict[str, ty.Any] | None:
    """Config-flow discovery hook (advert-only).

    Only a *primary* curtain is independently addable — a secondary member never
    appears in the picker (it's absorbed into its group via the chain read at
    setup). For a primary, record `is_group` (from the advert's in_group) so setup
    can branch to a group vs a standalone device. Returns None to reject.
    """
    try:
        adv = Curtain3ServiceData.parse(svc)
    except ValueError:
        return None
    if not adv.is_primary:
        return None
    return {CONF_IS_GROUP: adv.in_group}
