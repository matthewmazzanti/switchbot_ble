"""Blind Tilt BLE response/notification dataclasses (device -> app).

Responses are parsed from notification/read data (no 0x57 prefix).
"""

import struct
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PositionResponse:
    """7-byte position response / movement notification."""

    status: int
    # Raw state byte. The app doesn't decode open/close direction from BLE; its
    # only tristate (from cloud status) is 0=stopped, 1=moving, 2=stuck.
    run_status: int
    position: int

    def to_bytes(self) -> bytes:
        return bytes([self.status, self.run_status, 0, 0, 0, 0, self.position])

    @classmethod
    def from_bytes(cls, data: bytes) -> PositionResponse:
        if len(data) < 7:
            raise ValueError(f"Need 7 bytes, got {len(data)}")
        return cls(status=data[0], run_status=data[1], position=data[6])


@dataclass(frozen=True, slots=True)
class CalibrationResponse:
    """2-byte calibration status response."""

    status: int
    calibrated: bool
    direction_set: bool
    direction: int  # 0=default, 1=reversed

    def to_bytes(self) -> bytes:
        flags = 0
        if self.calibrated:
            flags |= 0x04
        if self.direction_set:
            flags |= 0x02
        flags |= self.direction & 0x01
        return bytes([self.status, flags])

    @classmethod
    def from_bytes(cls, data: bytes) -> CalibrationResponse:
        if len(data) < 2:
            raise ValueError(f"Need 2 bytes, got {len(data)}")
        return cls(
            status=data[0],
            calibrated=bool(data[1] & 0x04),
            direction_set=bool(data[1] & 0x02),
            direction=data[1] & 0x01,
        )


@dataclass(frozen=True, slots=True)
class CalibrationStepResponse:
    """2-byte calibration step response / notification."""

    status: int
    step: int  # 0-15
    enable_next: bool
    exit: bool
    direction_error: bool

    def to_bytes(self) -> bytes:
        flags = self.step & 0x0F
        if self.enable_next:
            flags |= 0x10
        if self.exit:
            flags |= 0x20
        if self.direction_error:
            flags |= 0x40
        return bytes([self.status, flags])

    @classmethod
    def from_bytes(cls, data: bytes) -> CalibrationStepResponse:
        if len(data) < 2:
            raise ValueError(f"Need 2 bytes, got {len(data)}")
        return cls(
            status=data[0],
            step=data[1] & 0x0F,
            enable_next=bool(data[1] & 0x10),
            exit=bool(data[1] & 0x20),
            direction_error=bool(data[1] & 0x40),
        )


@dataclass(frozen=True, slots=True)
class ActionModeResponse:
    """2-byte action mode response."""

    status: int
    silent: bool

    def to_bytes(self) -> bytes:
        return bytes([self.status, 0x01 if self.silent else 0x00])

    @classmethod
    def from_bytes(cls, data: bytes) -> ActionModeResponse:
        if len(data) < 2:
            raise ValueError(f"Need 2 bytes, got {len(data)}")
        return cls(status=data[0], silent=bool(data[1] & 0x01))


@dataclass(frozen=True, slots=True)
class DelayResponse:
    """6-byte delay response."""

    status: int
    timestamp: int  # 4-byte big-endian Unix timestamp
    position: int

    def to_bytes(self) -> bytes:
        ts = struct.pack(">I", self.timestamp)
        return bytes([self.status]) + ts + bytes([self.position])

    @classmethod
    def from_bytes(cls, data: bytes) -> DelayResponse:
        if len(data) < 6:
            raise ValueError(f"Need 6 bytes, got {len(data)}")
        timestamp = struct.unpack(">I", data[1:5])[0]
        return cls(status=data[0], timestamp=timestamp, position=data[5])


@dataclass(frozen=True, slots=True)
class StatusResponse:
    """1-byte generic status response."""

    status: int

    def to_bytes(self) -> bytes:
        return bytes([self.status])

    @classmethod
    def from_bytes(cls, data: bytes) -> StatusResponse:
        if len(data) < 1:
            raise ValueError("Need at least 1 byte")
        return cls(status=data[0])
