"""Curtain 3 BLE advertisement data parsing.

Per WoCurtain3Parser (which extends WoCurtainParser): the core fields live in
the service-data broadcast (UUID 0xFD3D), plus a Curtain-3 `too_hot` flag in
byte 5; additional alarm/config fields live in the manufacturer data
(company id 0x0969, MAC at bytes 0-5).

Only the service-data core (battery/position/calibrated) is currently surfaced
as entities; the rest is modeled here for completeness.
"""

from dataclasses import dataclass

from ..core import PAIRING_BIT, is_pairing
from ..device_type import DeviceType

# On the wire the type byte is 0x7B in normal operation and 0x5B in pairing mode.
DEVICE_TYPE = DeviceType.CURTAIN3


@dataclass(frozen=True, slots=True)
class Curtain3ServiceData:
    """Service-data broadcast (UUID 0xFD3D), >= 6 bytes."""

    pair_mode: bool
    is_primary: bool  # byte 1 bit 7; the group's controllable node
    calibrated: bool  # byte 1 bit 6; set = calibrated
    battery: int  # 0-100
    position: int  # 0-100
    in_group: bool
    too_hot: bool  # byte 5 bits 2:0 == 7 (Curtain 3 only)

    def to_bytes(self) -> bytes:
        chain = 2 if self.in_group else 0
        # fmt: off
        return bytes([
            # byte 0: device type; pairing bit set in normal operation
            DEVICE_TYPE | (0 if self.pair_mode else PAIRING_BIT),
            # byte 1: is_primary (bit 7), calibrated (bit 6)
            (self.is_primary << 7) | (self.calibrated << 6),
            # byte 2: battery in bits 6:0
            self.battery & 0x7F,
            # byte 3: position in bits 6:0
            self.position & 0x7F,
            # byte 4: chain position in bits 3:0
            chain & 0x0F,
            # byte 5: too-hot alarm in bits 2:0
            0x07 if self.too_hot else 0x00,
        ])
        # fmt: on

    @classmethod
    def parse(cls, data: bytes) -> Curtain3ServiceData:
        if len(data) < 6:
            raise ValueError(f"service data needs >= 6 bytes, got {len(data)}")
        return cls(
            pair_mode=is_pairing(data[0]),
            is_primary=bool(data[1] & 0x80),
            calibrated=bool(data[1] & 0x40),
            battery=data[2] & 0x7F,
            position=data[3] & 0x7F,
            in_group=(data[4] & 0x0F) > 1,
            too_hot=(data[5] & 0x07) == 7,
        )


@dataclass(frozen=True, slots=True)
class Curtain3ManufacturerData:
    """Manufacturer data (company id 0x0969), MAC at bytes 0-5. The Curtain-3
    alarm/config fields; >= 13 bytes (the app gates geomag on length > 12)."""

    temp_too_high: bool  # byte 7 bits 7:6 == 0b10
    temp_too_low: bool  # byte 7 bits 7:6 == 0b01
    geomag_alarm: bool  # byte 7 bit 2
    ear_type: int  # byte 11 bits 3:0
    pre_group: bool  # byte 11 bit 7

    def to_bytes(self) -> bytes:
        b7 = (0x80 if self.temp_too_high else 0x40 if self.temp_too_low else 0x00) | (
            0x04 if self.geomag_alarm else 0x00
        )
        b11 = (self.pre_group << 7) | (self.ear_type & 0x0F)
        # 0-5 MAC, 6 rsvd, 7 temp/geomag, 8-10 rsvd, 11 ear/pre_group, 12 rsvd
        return bytes([0, 0, 0, 0, 0, 0, 0, b7, 0, 0, 0, b11, 0])

    @classmethod
    def parse(cls, data: bytes) -> Curtain3ManufacturerData:
        if len(data) < 13:
            raise ValueError(f"manufacturer data needs >= 13 bytes, got {len(data)}")
        return cls(
            temp_too_high=(data[7] & 0xC0) == 0x80,
            temp_too_low=(data[7] & 0xC0) == 0x40,
            geomag_alarm=(data[7] & 0x04) == 0x04,
            ear_type=data[11] & 0x0F,
            pre_group=bool(data[11] & 0x80),
        )
