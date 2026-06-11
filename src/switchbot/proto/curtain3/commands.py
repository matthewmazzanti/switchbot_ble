"""Curtain 3 BLE command dataclasses (app -> device).

Each command is a frozen dataclass with to_bytes() / from_bytes() for
roundtrip serialization against the SwitchBot BLE wire format.
"""

import struct
from dataclasses import dataclass
from typing import ClassVar

from ..core import (
    MAGIC,
    SUB_CALIBRATION,
    SUB_DELAY,
    SUB_LIGHT,
    SUB_LINK,
    SUB_MOVE,
    SUB_SETTINGS,
    SUB_WORK_MODE,
    TIMER_IDX_TAG,
    FixedCommand,
    build,
    ext_get,
    ext_set,
    notify,
    tail,
    timer_get,
    timer_set,
)

# Curtain-only subsystem bytes
SUB_INFO = 0x81

# Motion modes (CurtainConst)
MOTION_PERFORMANCE = 0
MOTION_QUIET = 1
MOTION_SLOW = 2

# Device index values
INDEX_SINGLE = 1
INDEX_BOTH = 3


# ---------------------------------------------------------------------------
# Movement (SUB_MOVE)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SetPercentage:  # 57 0F 45 01 01 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_MOVE, 0x01)
    index: int
    position: int
    position2: int = 0

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.index, self.position, self.position2)

    @classmethod
    def from_bytes(cls, data: bytes) -> SetPercentage:
        p = tail(cls._HEADER, data)
        return cls(index=p[0], position=p[1], position2=p[2])


@dataclass(frozen=True, slots=True)
class Stop:  # 57 0F 45 01 00 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_MOVE, 0x00)
    index: int = INDEX_SINGLE

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.index)

    @classmethod
    def from_bytes(cls, data: bytes) -> Stop:
        p = tail(cls._HEADER, data)
        return cls(index=p[0])


@dataclass(frozen=True, slots=True)
class GetMoveInfo:  # 57 0F 46 01 ..
    _HEADER: ClassVar[bytes] = ext_get(SUB_MOVE)
    index: int = INDEX_SINGLE

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.index)

    @classmethod
    def from_bytes(cls, data: bytes) -> GetMoveInfo:
        p = tail(cls._HEADER, data)
        return cls(index=p[0])


# ---------------------------------------------------------------------------
# Calibration (SUB_CALIBRATION)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Calibration:  # 57 0F 45 05 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_CALIBRATION)
    action: int  # 1=start, 2=stop

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.action)

    @classmethod
    def from_bytes(cls, data: bytes) -> Calibration:
        p = tail(cls._HEADER, data)
        return cls(action=p[0])


@dataclass(frozen=True, slots=True)
class CalibrationTest:  # 57 0F 45 05 03 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_CALIBRATION, 0x03)
    action: int

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.action)

    @classmethod
    def from_bytes(cls, data: bytes) -> CalibrationTest:
        p = tail(cls._HEADER, data)
        return cls(action=p[0])


@dataclass(frozen=True, slots=True)
class ContinueMove:  # 57 0F 45 05 04 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_CALIBRATION, 0x04)
    index: int
    direction: int  # 1=open, 2=close

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.index, self.direction)

    @classmethod
    def from_bytes(cls, data: bytes) -> ContinueMove:
        p = tail(cls._HEADER, data)
        return cls(index=p[0], direction=p[1])


@dataclass(frozen=True, slots=True)
class CalibrationPause:  # 57 0F 45 05 05 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_CALIBRATION, 0x05)
    index: int = 0

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.index)

    @classmethod
    def from_bytes(cls, data: bytes) -> CalibrationPause:
        p = tail(cls._HEADER, data)
        return cls(index=p[0])


@dataclass(frozen=True, slots=True)
class CalibrateIndex:  # 57 0F 45 05 08 .. ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_CALIBRATION, 0x08)
    dev_index: int
    item_index: int

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.dev_index, self.item_index)

    @classmethod
    def from_bytes(cls, data: bytes) -> CalibrateIndex:
        p = tail(cls._HEADER, data)
        return cls(dev_index=p[0], item_index=p[1])


@dataclass(frozen=True, slots=True)
class CalibrationMode:  # 57 0F 45 05 08 .. .. ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_CALIBRATION, 0x08)
    index: int
    mode: int

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.index, self.mode, self.mode)

    @classmethod
    def from_bytes(cls, data: bytes) -> CalibrationMode:
        p = tail(cls._HEADER, data)
        return cls(index=p[0], mode=p[1])


@dataclass(frozen=True, slots=True)
class TinyAdjust(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_set(SUB_CALIBRATION, 0x0A, 0x03)


@dataclass(frozen=True, slots=True)
class GetDirection(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_CALIBRATION, 0x00)


@dataclass(frozen=True, slots=True)
class GetCaliDistance(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_INFO, 0x03)


@dataclass(frozen=True, slots=True)
class GetCaliMode(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_INFO, 0x04)


# ---------------------------------------------------------------------------
# Settings (SUB_SETTINGS)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SetMotionMode:  # 57 0F 45 04 01 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_SETTINGS, 0x01)
    index: int
    mode: int  # 0=performance, 1=quiet, 2=slow

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.index, self.mode, self.mode)

    @classmethod
    def from_bytes(cls, data: bytes) -> SetMotionMode:
        p = tail(cls._HEADER, data)
        return cls(index=p[0], mode=p[1])


@dataclass(frozen=True, slots=True)
class SetOpenInverse:  # 57 0F 45 04 02 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_SETTINGS, 0x02)
    index: int
    inverse: tuple[bool, ...]

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.index, *[int(b) for b in self.inverse])

    @classmethod
    def from_bytes(cls, data: bytes) -> SetOpenInverse:
        p = tail(cls._HEADER, data)
        return cls(index=p[0], inverse=tuple(bool(b) for b in p[1:]))


@dataclass(frozen=True, slots=True)
class SetTouchGo:  # 57 0F 45 04 03 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_SETTINGS, 0x03)
    index: int
    enable: bool

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.index, self.enable, self.enable)

    @classmethod
    def from_bytes(cls, data: bytes) -> SetTouchGo:
        p = tail(cls._HEADER, data)
        return cls(index=p[0], enable=bool(p[1]))


@dataclass(frozen=True, slots=True)
class SetLightEnable:  # 57 0F 45 04 04 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_SETTINGS, 0x04)
    index: int
    enable: bool

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.index, self.enable, self.enable)

    @classmethod
    def from_bytes(cls, data: bytes) -> SetLightEnable:
        p = tail(cls._HEADER, data)
        return cls(index=p[0], enable=bool(p[1]))


@dataclass(frozen=True, slots=True)
class SetOpenDirection:  # 57 0F 45 04 06 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_SETTINGS, 0x06)
    index: int
    direction1: int
    direction2: int

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.index, self.direction1, self.direction2)

    @classmethod
    def from_bytes(cls, data: bytes) -> SetOpenDirection:
        p = tail(cls._HEADER, data)
        return cls(index=p[0], direction1=p[1], direction2=p[2])


@dataclass(frozen=True, slots=True)
class GetSettingInfo(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_SETTINGS, 0x01)


@dataclass(frozen=True, slots=True)
class GetAdvancedInfo(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_SETTINGS, 0x02)


# ---------------------------------------------------------------------------
# Light (SUB_LIGHT)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SetLightSource:  # 57 0F 45 03 02 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_LIGHT, 0x02)
    index: int
    source: int

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.index, self.source)

    @classmethod
    def from_bytes(cls, data: bytes) -> SetLightSource:
        p = tail(cls._HEADER, data)
        return cls(index=p[0], source=p[1])


@dataclass(frozen=True, slots=True)
class ClearLightActions(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_set(SUB_LIGHT, 0x03)


@dataclass(frozen=True, slots=True)
class GetLightInfo(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_LIGHT, 0x00)


@dataclass(frozen=True, slots=True)
class GetLightActionList:  # 57 0F 46 03 01 ..
    _HEADER: ClassVar[bytes] = ext_get(SUB_LIGHT, 0x01)
    index: int

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.index)

    @classmethod
    def from_bytes(cls, data: bytes) -> GetLightActionList:
        p = tail(cls._HEADER, data)
        return cls(index=p[0])


@dataclass(frozen=True, slots=True)
class GetLightSource(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_LIGHT, 0x02)


@dataclass(frozen=True, slots=True)
class GetLightData:  # 57 0F 46 03 04 ..
    _HEADER: ClassVar[bytes] = ext_get(SUB_LIGHT, 0x04)
    time_range: int
    source: int
    index: bool = True

    def to_bytes(self) -> bytes:
        src_idx = ((self.source & 0x7F) << 1) | self.index
        return build(self._HEADER, self.time_range, src_idx)

    @classmethod
    def from_bytes(cls, data: bytes) -> GetLightData:
        p = tail(cls._HEADER, data)
        return cls(time_range=p[0], source=(p[1] >> 1) & 0x7F, index=bool(p[1] & 0x01))


# ---------------------------------------------------------------------------
# Delay (SUB_DELAY)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ClearDelay(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_set(SUB_DELAY, 0x00)


@dataclass(frozen=True, slots=True)
class SetDelay:  # 57 0F 45 06 01 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_DELAY, 0x01)
    timestamp: int
    mode: int
    action: bytes

    def to_bytes(self) -> bytes:
        # 4-byte big-endian UTC timestamp (the app's read path reads reply[1:5]).
        return build(
            self._HEADER, struct.pack(">I", self.timestamp), self.mode, self.action
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> SetDelay:
        p = tail(cls._HEADER, data)
        timestamp = struct.unpack(">I", p[:4])[0]
        return cls(timestamp=timestamp, mode=p[4], action=bytes(p[5:]))


@dataclass(frozen=True, slots=True)
class GetDelay(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_DELAY)


# ---------------------------------------------------------------------------
# Timers
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GetTimer:  # 57 08 ..
    _HEADER: ClassVar[bytes] = timer_get()
    index: int

    def to_bytes(self) -> bytes:
        idx_byte = ((self.index << 4) & 0xF0) | TIMER_IDX_TAG
        return build(self._HEADER, idx_byte)

    @classmethod
    def from_bytes(cls, data: bytes) -> GetTimer:
        p = tail(cls._HEADER, data)
        if (p[0] & 0x0F) != TIMER_IDX_TAG:
            raise ValueError(f"Bad index byte low nibble: {p[0]:#04x}")
        return cls(index=(p[0] >> 4) & 0x0F)


@dataclass(frozen=True, slots=True)
class GetTimerCount(FixedCommand):
    _WIRE: ClassVar[bytes] = timer_get(0x02)


@dataclass(frozen=True, slots=True)
class SetTimer:  # 57 09 ..
    _HEADER: ClassVar[bytes] = timer_set()
    index: int
    enable: bool
    action_mode: int
    repeat_days: int | None  # weekday bitmap bits 0-6, or None for no repeat
    hour: int
    minute: int
    action: bytes

    def to_bytes(self) -> bytes:
        idx_byte = ((self.index << 4) & 0xF0) | TIMER_IDX_TAG
        enable_mode = (self.enable << 7) | (self.action_mode & 0x7F)
        repeat_byte = 0x80 if self.repeat_days is None else self.repeat_days & 0x7F
        return build(
            self._HEADER,
            idx_byte,
            enable_mode,
            repeat_byte,
            self.hour,
            self.minute,
            self.action,
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> SetTimer:
        p = tail(cls._HEADER, data)
        if (p[0] & 0x0F) != TIMER_IDX_TAG:
            raise ValueError(f"Bad index byte low nibble: {p[0]:#04x}")
        return cls(
            index=(p[0] >> 4) & 0x0F,
            enable=bool(p[1] & 0x80),
            action_mode=p[1] & 0x7F,
            repeat_days=None if p[2] == 0x80 else p[2] & 0x7F,
            hour=p[3],
            minute=p[4],
            action=bytes(p[5:]),
        )


@dataclass(frozen=True, slots=True)
class SetTimerCount:  # 57 09 02 ..
    _HEADER: ClassVar[bytes] = timer_set(0x02)
    count: int

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.count)

    @classmethod
    def from_bytes(cls, data: bytes) -> SetTimerCount:
        p = tail(cls._HEADER, data)
        return cls(count=p[0])


# ---------------------------------------------------------------------------
# Notify
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DisableNotify(FixedCommand):
    _WIRE: ClassVar[bytes] = notify(0x00)


@dataclass(frozen=True, slots=True)
class EnableNotify:  # 57 0E 01 ..
    _HEADER: ClassVar[bytes] = notify(0x01)
    time_unit: int  # top 2 bits (masked with 0xC0)
    interval: int
    read_info_cmd: bytes

    def to_bytes(self) -> bytes:
        return build(
            self._HEADER,
            self.time_unit & 0xC0,
            self.interval,
            0xFF,
            0xFF,
            self.read_info_cmd,
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> EnableNotify:
        p = tail(cls._HEADER, data)
        return cls(
            time_unit=p[0] & 0xC0,
            interval=p[1],
            read_info_cmd=bytes(p[4:]),
        )


# ---------------------------------------------------------------------------
# Link (SUB_LINK)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SetLinkage:  # 57 0F 45 02 01 01 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_LINK, 0x01, 0x01)
    secondary_mac: bytes  # 6-byte MAC of the linked secondary curtain

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.secondary_mac)

    @classmethod
    def from_bytes(cls, data: bytes) -> SetLinkage:
        p = tail(cls._HEADER, data)
        return cls(secondary_mac=bytes(p[:6]))


@dataclass(frozen=True, slots=True)
class Ungroup(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_set(SUB_LINK, 0x01, 0x00)


@dataclass(frozen=True, slots=True)
class GetChainInfo(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_LINK, 0x00, 0x01)


@dataclass(frozen=True, slots=True)
class GetChainStatus(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_LINK, 0x00, 0x02)


# ---------------------------------------------------------------------------
# Work Mode (SUB_WORK_MODE)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Reboot(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_set(SUB_WORK_MODE, 0x03)


@dataclass(frozen=True, slots=True)
class ResetPwm:  # 57 0F 45 82 02 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_WORK_MODE, 0x02)
    left: int = 50
    right: int = 50

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.left, self.right)

    @classmethod
    def from_bytes(cls, data: bytes) -> ResetPwm:
        p = tail(cls._HEADER, data)
        return cls(left=p[0], right=p[1])


@dataclass(frozen=True, slots=True)
class GetWorkMode(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_WORK_MODE, 0x03)


# ---------------------------------------------------------------------------
# Info (SUB_INFO — curtain-specific)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GetCurtainInfo(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_INFO, 0x01)


# ---------------------------------------------------------------------------
# Non-extended commands
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Shake(FixedCommand):
    _WIRE: ClassVar[bytes] = build(MAGIC, 0x01, 0x00)
