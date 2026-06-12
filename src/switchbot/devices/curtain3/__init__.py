"""Curtain 3 Home Assistant integration: standalone device + dual group.

`single.py` is the standalone curtain (coordinator + entities); `group.py` is
the two-member dual group (member coordinators + glue + entities).
"""

from .group import Curtain3Group
from .single import Curtain3Coordinator, parse_advertisement

__all__ = ["Curtain3Coordinator", "Curtain3Group", "parse_advertisement"]
