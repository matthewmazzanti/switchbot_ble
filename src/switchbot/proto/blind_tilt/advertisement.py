"""Blind Tilt BLE advertisement data parsing.

The advertisement is split across two BLE fields (per the decompiled app's
WoBlindTiltParser); each is parsed independently here. Combining them and
retaining the last-seen of each is the consumer's job (see the coordinator).

  Service data (UUID 0xFD3D) -> BlindTiltServiceData:
    byte 0  device type (& 0x7f in {0x58, 0x78})
    byte 2  battery (bits 6:0)

  Manufacturer data (company id 0x0969 / 2409) -> BlindTiltManufacturerData;
  only bytes 7-10 are device fields (bytes 0-6 are the MAC):
    byte 7  direction_set (bit 7), direction (bit 6), stuck flag (bit 3),
            calibrated (bit 0)
    byte 8  moving (bit 7, SET = moving), position (bits 6:0)
    byte 9  link_length (bits 2:0)
    byte 10 connect_allow (bit 7)
"""

from dataclasses import dataclass

from ..core import device_type
from ..device_type import DeviceType

# On the wire the type byte is 0x78 in normal operation and 0x58 in pairing mode.
DEVICE_TYPE = DeviceType.BLIND_TILT


@dataclass(frozen=True, slots=True)
class BlindTiltServiceData:
    """Service data (UUID 0xFD3D) payload."""

    device_type: int  # model identity (pairing bit masked off)
    battery: int  # 0-100

    def to_bytes(self) -> bytes:
        return bytes([self.device_type, 0x00, self.battery & 0x7F])

    @classmethod
    def parse(cls, data: bytes) -> BlindTiltServiceData:
        if len(data) < 3:
            raise ValueError(f"service data needs >= 3 bytes, got {len(data)}")
        return cls(device_type=device_type(data[0]), battery=data[2] & 0x7F)


@dataclass(frozen=True, slots=True)
class BlindTiltManufacturerData:
    """Manufacturer data (company id 0x0969) payload (bytes 7-10)."""

    direction_set: bool
    direction: int  # 0=default, 1=reversed
    calibrated: bool
    moving: bool  # True = motor running
    position: int  # 0-100
    link_length: int  # 0-7
    connect_allow: bool
    stuck_flag: bool  # raw byte7 bit3; see `stuck`

    @property
    def stuck(self) -> bool:
        # Per the app: the stuck flag only counts when not currently moving.
        return self.stuck_flag and not self.moving

    def to_bytes(self) -> bytes:
        """Encode the 11-byte manufacturer-data payload (bytes 0-6 are MAC)."""
        # fmt: off
        return bytes([
            0, 0, 0, 0, 0, 0,  # 0-5: MAC (not modeled)
            0,                 # 6
            # byte 7: direction_set(7), direction(6), stuck flag(3), calibrated(0)
            (self.direction_set << 7)
            | (self.direction << 6)
            | (self.stuck_flag << 3)
            | self.calibrated,
            # byte 8: moving(7, SET = moving), position(6:0)
            (self.moving << 7) | (self.position & 0x7F),
            # byte 9: link_length in bits 2:0
            self.link_length & 0x07,
            # byte 10: connect_allow in bit 7
            self.connect_allow << 7,
        ])
        # fmt: on

    @classmethod
    def parse(cls, data: bytes) -> BlindTiltManufacturerData:
        if len(data) < 11:
            raise ValueError(f"manufacturer data needs >= 11 bytes, got {len(data)}")
        return cls(
            direction_set=bool(data[7] & 0x80),
            direction=(data[7] >> 6) & 0x01,
            calibrated=bool(data[7] & 0x01),
            moving=bool(data[8] & 0x80),
            position=data[8] & 0x7F,
            link_length=data[9] & 0x07,
            connect_allow=bool(data[10] & 0x80),
            stuck_flag=bool(data[7] & 0x08),
        )
