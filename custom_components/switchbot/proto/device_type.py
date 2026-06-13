"""Known SwitchBot device-type identities.

Values are the *model identity* — the advertisement type byte with the reserved
and pairing bits masked off (i.e. what `core.device_type()` returns). The
on-wire byte differs by the pairing bit (set in normal operation). Mirrors the
app's own `DeviceType` enum.
"""

from enum import IntEnum


class DeviceType(IntEnum):
    BLIND_TILT = 0x58
    CURTAIN3 = 0x5B
    # Water Leak Detector. On the wire the type byte is 0x26 in normal
    # operation and 0x06 in pairing/"add" mode (DeviceByteType
    # WO_BLE_TYPE_WATERDETECTOR = 38 / _ADD = 6); the masked identity is 0x06.
    LEAK = 0x06
