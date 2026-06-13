"""Curtain 3 BLE response parsing (device -> app).

One frozen dataclass per notify reply, decoded byte-for-byte against the
decompiled app (`decomp/.../ble/BleMsgParser.java` plus a few replies parsed
inline in the curtain UI/viewmodels). Each models the *raw wire* fields with
`parse()` / `to_bytes()` for roundtripping; app-derived conveniences (mm,
seconds, left/right) are exposed as `@property`.

`data` is the full reply including the leading status byte (`data[0]`); the
accept/reject signal is `core.CommandReply` (already checked by the command
path), so these payload parsers assume a successful reply and don't re-validate
it. `to_bytes()` emits a canonical OK status byte and zeroes bytes the app never
reads.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Self

from ..core import RESP_STATUS_OK, build

# A chain neighbour MAC of all-zeros (the protocol's EMPTY_MAC) means "no
# neighbour"; all-FF is treated the same defensively.
_NO_MAC = (bytes(6), b"\xff" * 6)


def _mac_or_none(raw: bytes) -> bytes | None:
    mac = bytes(raw)
    return None if mac in _NO_MAC else mac


@dataclass(frozen=True, slots=True)
class ChainInfoReply:
    """Reply to GetChainInfo — the chain's neighbour MACs.

    BleMsgParser.parseCurtainChainInfo:298. The app reads only two 6-byte MAC
    slices; bytes 1 and 8-13 are present on the wire but unread (left zeroed
    here). A neighbour MAC of all-zeros (the protocol's `EMPTY_MAC`) means "no
    neighbour" and is decoded to None — so a standalone curtain reports
    next_mac=None. MACs are raw bytes; colon-hex formatting is the consumer's job.
    """

    pre_mac: bytes | None  # upstream neighbour (WO_CURTAIN_PRE_MAC), None if head
    next_mac: bytes | None  # downstream neighbour = the secondary, None if none

    @classmethod
    def parse(cls, data: bytes) -> Self:
        if len(data) < 20:
            raise ValueError(f"chain-info reply needs >= 20 bytes, got {len(data)}")
        return cls(pre_mac=_mac_or_none(data[2:8]), next_mac=_mac_or_none(data[14:20]))

    def to_bytes(self) -> bytes:
        # byte 0 status, byte 1 + bytes 8-13 reserved (unread by the app)
        empty = bytes(6)
        return build(
            RESP_STATUS_OK,
            0,
            self.pre_mac or empty,
            empty,
            self.next_mac or empty,
        )


@dataclass(frozen=True, slots=True)
class CurtainInfoReply:
    """Reply to GetCurtainInfo — motion + both members' position/battery.

    BleMsgParser.parseCurtainInfo:329-344. `dev1_*` are meaningful only when
    `link_length > 1`. `action_mode` is the high nibble left in place (the app
    masks `& 0xF0` without shifting).
    """

    delay_enabled: bool  # byte 1 bit 6
    motion_status: int  # byte 1 bits 3:0
    action_mode: int  # byte 2 bits 7:4 (masked, not shifted)
    timer_num: int  # byte 2 bits 2:0
    link_length: int  # byte 3, clamped to >= 1
    dev0_solar_plugin: bool  # byte 4 bit 7
    dev0_position: int  # byte 4 bits 6:0
    dev0_charging: bool  # byte 5 bit 7
    dev0_battery: int  # byte 5 bits 6:0
    dev1_solar_plugin: bool  # byte 6 bit 7
    dev1_position: int  # byte 6 bits 6:0
    dev1_charging: bool  # byte 7 bit 7
    dev1_battery: int  # byte 7 bits 6:0

    @classmethod
    def parse(cls, data: bytes) -> Self:
        if len(data) < 8:
            raise ValueError(f"curtain-info reply needs >= 8 bytes, got {len(data)}")
        return cls(
            delay_enabled=bool(data[1] & 0x40),
            motion_status=data[1] & 0x0F,
            action_mode=data[2] & 0xF0,
            timer_num=data[2] & 0x07,
            link_length=data[3] if data[3] > 1 else 1,
            dev0_solar_plugin=bool(data[4] & 0x80),
            dev0_position=data[4] & 0x7F,
            dev0_charging=bool(data[5] & 0x80),
            dev0_battery=data[5] & 0x7F,
            dev1_solar_plugin=bool(data[6] & 0x80),
            dev1_position=data[6] & 0x7F,
            dev1_charging=bool(data[7] & 0x80),
            dev1_battery=data[7] & 0x7F,
        )

    def to_bytes(self) -> bytes:
        return build(
            RESP_STATUS_OK,
            (self.delay_enabled << 6) | (self.motion_status & 0x0F),
            (self.action_mode & 0xF0) | (self.timer_num & 0x07),
            self.link_length & 0xFF,
            (self.dev0_solar_plugin << 7) | (self.dev0_position & 0x7F),
            (self.dev0_charging << 7) | (self.dev0_battery & 0x7F),
            (self.dev1_solar_plugin << 7) | (self.dev1_position & 0x7F),
            (self.dev1_charging << 7) | (self.dev1_battery & 0x7F),
        )


@dataclass(frozen=True, slots=True)
class MoveInfoReply:
    """Reply to GetMoveInfo — whether the curtain is still moving.

    Consumed at CurtainAutoCaliViewModel:1587 / guarded at
    CurtainManualViewModel:161; any non-zero byte 1 means moving.
    """

    moving: bool  # byte 1 != 0

    @classmethod
    def parse(cls, data: bytes) -> Self:
        if len(data) < 2:
            raise ValueError(f"move-info reply needs >= 2 bytes, got {len(data)}")
        return cls(moving=bool(data[1]))

    def to_bytes(self) -> bytes:
        return build(RESP_STATUS_OK, 1 if self.moving else 0)


@dataclass(frozen=True, slots=True)
class DirectionReply:
    """Reply to GetDirection — the open/master direction bit.

    CurtainCalibrateSuccessActivity:98-107; `(reply[1] & 1) == 0` ⇒ master-left
    (CurtainUtil:317-319). Stored as the raw bit; `is_master_left` is the view.
    """

    direction: int  # byte 1 bit 0: 0 = left (master-left), 1 = right

    @property
    def is_master_left(self) -> bool:
        return self.direction == 0

    @classmethod
    def parse(cls, data: bytes) -> Self:
        if len(data) < 2:
            raise ValueError(f"direction reply needs >= 2 bytes, got {len(data)}")
        return cls(direction=data[1] & 0x01)

    def to_bytes(self) -> bytes:
        return build(RESP_STATUS_OK, self.direction & 0x01)


@dataclass(frozen=True, slots=True)
class WorkModeReply:
    """Reply to GetWorkMode — the work-mode / PWM-state byte.

    AddCurtainActivity:1611 reads `reply[4]` (bytes 1-3 unread here).
    """

    work_mode: int  # byte 4

    @classmethod
    def parse(cls, data: bytes) -> Self:
        if len(data) < 5:
            raise ValueError(f"work-mode reply needs >= 5 bytes, got {len(data)}")
        return cls(work_mode=data[4])

    def to_bytes(self) -> bytes:
        return build(RESP_STATUS_OK, 0, 0, 0, self.work_mode & 0xFF)


@dataclass(frozen=True, slots=True)
class CaliModeReply:
    """Reply to GetCaliMode — the calibration-mode byte.

    CurtainUtil:99-115; value 1 ⇒ already auto-calibrated.
    """

    cali_mode: int  # byte 1

    @property
    def auto_calibrated(self) -> bool:
        return self.cali_mode == 1

    @classmethod
    def parse(cls, data: bytes) -> Self:
        if len(data) < 2:
            raise ValueError(f"cali-mode reply needs >= 2 bytes, got {len(data)}")
        return cls(cali_mode=data[1] & 0xFF)

    def to_bytes(self) -> bytes:
        return build(RESP_STATUS_OK, self.cali_mode & 0xFF)


@dataclass(frozen=True, slots=True)
class CaliDistanceReply:
    """Reply to GetCaliDistance — each curtain's calibrated travel count.

    CurtainAutoCaliViewModel:328-360. `index_byte == 1` marks a single curtain;
    the physical distance is `raw * 5 * 0.1` mm (exposed as properties).
    """

    index_byte: int  # byte 1 (1 = single curtain)
    distance1_raw: int  # bytes 2-5, big-endian
    distance2_raw: int  # bytes 6-9, big-endian

    @property
    def single_curtain(self) -> bool:
        return self.index_byte == 1

    @property
    def distance1_mm(self) -> int:
        return int(self.distance1_raw * 5 * 0.1)

    @property
    def distance2_mm(self) -> int:
        return int(self.distance2_raw * 5 * 0.1)

    @classmethod
    def parse(cls, data: bytes) -> Self:
        if len(data) < 10:
            raise ValueError(f"cali-distance reply needs >= 10 bytes, got {len(data)}")
        return cls(
            index_byte=data[1],
            distance1_raw=int.from_bytes(data[2:6], "big"),
            distance2_raw=int.from_bytes(data[6:10], "big"),
        )

    def to_bytes(self) -> bytes:
        return build(
            RESP_STATUS_OK,
            self.index_byte & 0xFF,
            self.distance1_raw.to_bytes(4, "big"),
            self.distance2_raw.to_bytes(4, "big"),
        )


@dataclass(frozen=True, slots=True)
class DelayInfoReply:
    """Reply to GetDelay — the delay timer.

    BleMsgParser.parseCurtainDelayInfo:312-318: 4-byte big-endian UTC timestamp,
    a mode byte, then the opaque action payload.
    """

    timestamp: int  # bytes 1-4, big-endian UTC epoch
    mode: int  # byte 5
    action: bytes  # bytes 6..end

    @classmethod
    def parse(cls, data: bytes) -> Self:
        if len(data) < 6:
            raise ValueError(f"delay reply needs >= 6 bytes, got {len(data)}")
        return cls(
            timestamp=int.from_bytes(data[1:5], "big"),
            mode=data[5],
            action=bytes(data[6:]),
        )

    def to_bytes(self) -> bytes:
        return build(
            RESP_STATUS_OK,
            self.timestamp.to_bytes(4, "big"),
            self.mode & 0xFF,
            self.action,
        )


@dataclass(frozen=True, slots=True)
class SettingsInfoReply:
    """Reply to GetSettingInfo — the per-device curtain settings flags (byte 1).

    BleMsgParser.parseCurtainSettingsInfo (call sites pass deviceIndex 0 ⇒ the
    settings byte is reply[1]).
    """

    open_inverse: bool  # bit 7 (WO_CURTAIN_OPEN_INVERSE)
    touch_and_go: bool  # bit 6 (WO_CURTAIN_TOUCH_AND_GO)
    light_enable: bool  # bit 5 (WO_CURTAIN_LIGHT)
    voice_enable: bool  # bit 4 (WO_CURTAIN_VOICE)
    open_direction: bool  # bit 3 (WO_CURTAIN_OPEN_DIRECTION)

    @classmethod
    def parse(cls, data: bytes) -> Self:
        if len(data) < 2:
            raise ValueError(f"settings reply needs >= 2 bytes, got {len(data)}")
        b = data[1]
        return cls(
            open_inverse=bool(b & 0x80),
            touch_and_go=bool(b & 0x40),
            light_enable=bool(b & 0x20),
            voice_enable=bool(b & 0x10),
            open_direction=bool(b & 0x08),
        )

    def to_bytes(self) -> bytes:
        b = (
            (self.open_inverse << 7)
            | (self.touch_and_go << 6)
            | (self.light_enable << 5)
            | (self.voice_enable << 4)
            | (self.open_direction << 3)
        )
        return build(RESP_STATUS_OK, b)


@dataclass(frozen=True, slots=True)
class LightActionReply:
    """Reply to GetLightInfo / GetLightActionList — a light-sensing action.

    BleMsgParser.parseCurtainLightAction:353-368 (both commands share this
    parser). Times are raw on the wire (hour/minute bytes, a 16-bit minute
    duration); seconds-since-midnight / seconds are exposed as properties.
    """

    index: int  # byte 1 bits 3:0 — device index in the chain
    action_mode: int  # byte 1 bits 7:4
    enabled: bool  # byte 2 bit 6
    threshold_type: int  # byte 2 bits 5:4
    threshold: int  # byte 2 bits 3:0 — light level
    repeat_days: int  # byte 3 bits 6:0 — weekday bitmap
    start_hour: int  # byte 4
    start_minute: int  # byte 5
    time_length_min: int  # bytes 6-7, big-endian — active duration in minutes
    action: bytes  # bytes 8..end — opaque action payload

    @property
    def start_time_s(self) -> int:
        """Start time as seconds since midnight."""
        return self.start_hour * 3600 + self.start_minute * 60

    @property
    def time_length_s(self) -> int:
        return self.time_length_min * 60

    @classmethod
    def parse(cls, data: bytes) -> Self:
        if len(data) < 8:
            raise ValueError(f"light-action reply needs >= 8 bytes, got {len(data)}")
        return cls(
            index=data[1] & 0x0F,
            action_mode=(data[1] >> 4) & 0x0F,
            enabled=bool(data[2] & 0x40),
            threshold_type=(data[2] & 0x30) >> 4,
            threshold=data[2] & 0x0F,
            repeat_days=data[3] & 0x7F,
            start_hour=data[4],
            start_minute=data[5],
            time_length_min=(data[6] << 8) | data[7],
            action=bytes(data[8:]),
        )

    def to_bytes(self) -> bytes:
        return build(
            RESP_STATUS_OK,
            ((self.action_mode & 0x0F) << 4) | (self.index & 0x0F),
            (self.enabled << 6)
            | ((self.threshold_type & 0x03) << 4)
            | (self.threshold & 0x0F),
            self.repeat_days & 0x7F,
            self.start_hour & 0xFF,
            self.start_minute & 0xFF,
            (self.time_length_min >> 8) & 0xFF,
            self.time_length_min & 0xFF,
            self.action,
        )
