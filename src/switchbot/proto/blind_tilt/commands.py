"""Blind Tilt BLE command dataclasses (app -> device).

Each command is a frozen dataclass with to_bytes() / from_bytes() for
roundtrip serialization against the SwitchBot BLE wire format.
"""

import struct
from dataclasses import dataclass
from typing import ClassVar

from ..core import (
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

# Blind-tilt-only subsystem bytes
SUB_CAL_STEP = 0x09
# Group read sub-byte. The app reuses WOCODE_HUMIDIFIER_CODE_STATUS_CODE
# (= -127 = 0x81) here, not 0x46.
SUB_GROUP = 0x81

# Firmware >= MODERN_FW uses the "modern" action header; older uses legacy.
MODERN_FW = 20
_ACTION_MODERN = bytes([0x05, 0xFF])
_ACTION_LEGACY = bytes([0x01, 0x01])


def action_header(fw_version: int) -> bytes:
    """Return the 2-byte action header for *fw_version*."""
    return _ACTION_MODERN if fw_version >= MODERN_FW else _ACTION_LEGACY


def action_bytes(position: int, fw_version: int) -> bytes:
    """Encode the 3-byte mode/target/position action payload."""
    return action_header(fw_version) + bytes([position])


def parse_action(data: bytes, fw_version: int) -> int:
    """Validate the 3-byte action header for *fw_version* and return position."""
    expected = action_header(fw_version)
    if data[:2] != expected:
        raise ValueError(
            f"Action header {data[:2].hex()} doesn't match fw_version={fw_version}"
        )
    return data[2]


# ---------------------------------------------------------------------------
# Movement (SUB_MOVE)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SetPosition:  # 57 0F 45 01 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_MOVE)
    position: int

    def to_bytes(self, *, fw_version: int) -> bytes:
        return build(self._HEADER, action_bytes(self.position, fw_version))

    @classmethod
    def from_bytes(cls, data: bytes, *, fw_version: int) -> SetPosition:
        p = tail(cls._HEADER, data)
        return cls(position=parse_action(p[:3], fw_version))


@dataclass(frozen=True, slots=True)
class Stop(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_set(SUB_MOVE, 0x00, 0x01)


@dataclass(frozen=True, slots=True)
class GetPosition(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_MOVE, 0x00)


# ---------------------------------------------------------------------------
# Calibration (SUB_CALIBRATION / SUB_CAL_STEP)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StartCalibration(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_set(SUB_CALIBRATION, 0x01)


@dataclass(frozen=True, slots=True)
class StopCalibration(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_set(SUB_CALIBRATION, 0x02)


@dataclass(frozen=True, slots=True)
class SaveCalibration:  # 57 0F 45 05 09 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_CALIBRATION, 0x09)
    preset: int  # 1=zero, 2=mid, 3=full

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.preset)

    @classmethod
    def from_bytes(cls, data: bytes) -> SaveCalibration:
        p = tail(cls._HEADER, data)
        return cls(preset=p[0])


@dataclass(frozen=True, slots=True)
class GetCalibration(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_CALIBRATION)


@dataclass(frozen=True, slots=True)
class GetCalibrationStep(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_CAL_STEP)


# ---------------------------------------------------------------------------
# Settings (SUB_SETTINGS)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SetActionMode:  # 57 0F 45 04 01 01 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_SETTINGS, 0x01, 0x01)
    mode: int

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.mode)

    @classmethod
    def from_bytes(cls, data: bytes) -> SetActionMode:
        p = tail(cls._HEADER, data)
        return cls(mode=p[0])


@dataclass(frozen=True, slots=True)
class SetDirection:  # 57 0F 45 04 06 01 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_SETTINGS, 0x06, 0x01)
    horizontal: bool = True

    def to_bytes(self) -> bytes:
        direction = (not self.horizontal) | 0x02
        return build(self._HEADER, direction)

    @classmethod
    def from_bytes(cls, data: bytes) -> SetDirection:
        p = tail(cls._HEADER, data)
        return cls(horizontal=not p[0] & 0x01)


@dataclass(frozen=True, slots=True)
class GetAdvancedInfo(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_SETTINGS, 0x02)


@dataclass(frozen=True, slots=True)
class GetActionMode(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_SETTINGS, 0x03)


# ---------------------------------------------------------------------------
# Light (SUB_LIGHT)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SetLightAction:  # 57 0F 45 03 01 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_LIGHT, 0x01)
    index: int
    position: int

    def to_bytes(self, *, fw_version: int) -> bytes:
        return build(
            self._HEADER,
            self.index & 0x0F,
            0x01,
            action_bytes(self.position, fw_version),
        )

    @classmethod
    def from_bytes(cls, data: bytes, *, fw_version: int) -> SetLightAction:
        p = tail(cls._HEADER, data)
        if p[0] & 0x10:
            raise ValueError("This is a light rule, not a light action")
        index = p[0] & 0x0F
        return cls(index=index, position=parse_action(p[2:5], fw_version))


@dataclass(frozen=True, slots=True)
class SetLightRule:  # 57 0F 45 03 01 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_LIGHT, 0x01)
    index: int
    enable: bool
    threshold_type: int  # 1=higher, 2=lower
    threshold: int  # 0-15
    repeat_days: int  # weekday bitmap, bits 0-6
    start_hour: int
    start_minute: int
    duration_minutes: int

    def to_bytes(self) -> bytes:
        idx_flag = (self.index & 0x0F) | 0x10
        thresh_flags = (self.enable << 6) | (self.threshold_type & 0x03) << 4
        return build(
            self._HEADER,
            idx_flag,
            thresh_flags,
            self.threshold & 0x0F,
            self.repeat_days & 0x7F,
            self.start_hour,
            self.start_minute,
            struct.pack(">H", self.duration_minutes),
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> SetLightRule:
        p = tail(cls._HEADER, data)
        if not (p[0] & 0x10):
            raise ValueError("This is a light action, not a light rule")
        return cls(
            index=p[0] & 0x0F,
            enable=bool(p[1] & 0x40),
            threshold_type=(p[1] >> 4) & 0x03,
            threshold=p[2] & 0x0F,
            repeat_days=p[3] & 0x7F,
            start_hour=p[4],
            start_minute=p[5],
            duration_minutes=struct.unpack(">H", p[6:8])[0],
        )


@dataclass(frozen=True, slots=True)
class SetLightSource:  # 57 0F 45 03 02 ..
    _HEADER: ClassVar[bytes] = ext_set(SUB_LIGHT, 0x02)
    index: int
    external: bool = False

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.index, self.external)

    @classmethod
    def from_bytes(cls, data: bytes) -> SetLightSource:
        p = tail(cls._HEADER, data)
        return cls(index=p[0], external=bool(p[1]))


@dataclass(frozen=True, slots=True)
class ClearLightActions(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_set(SUB_LIGHT, 0x03)


@dataclass(frozen=True, slots=True)
class ClearAiLight(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_set(SUB_LIGHT, 0x05)


@dataclass(frozen=True, slots=True)
class GetLightInfo(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_LIGHT, 0x00)


@dataclass(frozen=True, slots=True)
class GetLightAction:  # 57 0F 46 03 01 ..
    _HEADER: ClassVar[bytes] = ext_get(SUB_LIGHT, 0x01)
    index: int

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.index)

    @classmethod
    def from_bytes(cls, data: bytes) -> GetLightAction:
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
        source = (p[1] >> 1) & 0x7F
        index = bool(p[1] & 0x01)
        return cls(time_range=p[0], source=source, index=index)


@dataclass(frozen=True, slots=True)
class GetAiLightCount(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_LIGHT, 0x06)


@dataclass(frozen=True, slots=True)
class GetAiLightAction(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_LIGHT, 0x07)


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
    position: int

    def to_bytes(self, *, fw_version: int) -> bytes:
        ts = struct.pack(">I", self.timestamp)  # 4-byte big-endian UTC timestamp
        action = action_bytes(self.position, fw_version)
        if fw_version < MODERN_FW:
            return build(self._HEADER, ts, 0xFF, 0x01, action)
        return build(self._HEADER, ts, 0x01, action)

    @classmethod
    def from_bytes(cls, data: bytes, *, fw_version: int) -> SetDelay:
        p = tail(cls._HEADER, data)
        timestamp = struct.unpack(">I", p[:4])[0]
        if fw_version < MODERN_FW:
            if p[4] != 0xFF:
                raise ValueError(f"Expected 0xFF pad for legacy fw, got {p[4]:#04x}")
            position = parse_action(p[6:9], fw_version)
        else:
            position = parse_action(p[5:8], fw_version)
        return cls(timestamp=timestamp, position=position)


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
    repeat_days: int | None  # weekday bitmap bits 0-6, or None for no repeat
    hour: int
    minute: int
    position: int

    def to_bytes(self, *, fw_version: int) -> bytes:
        idx_byte = ((self.index << 4) & 0xF0) | TIMER_IDX_TAG
        repeat_byte = 0x80 if self.repeat_days is None else self.repeat_days & 0x7F
        return build(
            self._HEADER,
            idx_byte,
            self.enable << 7,
            repeat_byte,
            self.hour,
            self.minute,
            0x01,
            action_bytes(self.position, fw_version),
        )

    @classmethod
    def from_bytes(cls, data: bytes, *, fw_version: int) -> SetTimer:
        p = tail(cls._HEADER, data)
        if (p[0] & 0x0F) != TIMER_IDX_TAG:
            raise ValueError(f"Bad index byte low nibble: {p[0]:#04x}")
        position = parse_action(p[6:9], fw_version)
        return cls(
            index=(p[0] >> 4) & 0x0F,
            enable=bool(p[1] & 0x80),
            repeat_days=None if p[2] == 0x80 else p[2] & 0x7F,
            hour=p[3],
            minute=p[4],
            position=position,
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
    time_unit: int  # top 2 bits used (masked with 0xC0)
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
# Link / Group (SUB_LINK / SUB_GROUP)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GetDeviceLink:  # 57 0F 46 02 .. 04
    _HEADER: ClassVar[bytes] = ext_get(SUB_LINK)
    index: int

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.index, 0x04)

    @classmethod
    def from_bytes(cls, data: bytes) -> GetDeviceLink:
        p = tail(cls._HEADER, data)
        return cls(index=p[0])


@dataclass(frozen=True, slots=True)
class GetGroupLinks(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_LINK, 0xFF, 0x03)


@dataclass(frozen=True, slots=True)
class GetGroupFirmwareBattery(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_GROUP, 0x06)


@dataclass(frozen=True, slots=True)
class GetGroupChargeInfo(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_GROUP, 0x07)


# ---------------------------------------------------------------------------
# Work Mode (SUB_WORK_MODE)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GetWorkMode(FixedCommand):
    _WIRE: ClassVar[bytes] = ext_get(SUB_WORK_MODE, 0x03)
