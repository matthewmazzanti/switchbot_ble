"""Tests for Blind Tilt advertisement data parsing (two independent fields)."""

import dataclasses as dc

from switchbot.proto.blind_tilt.advertisement import (
    BlindTiltManufacturerData,
    BlindTiltServiceData,
)


class TestServiceData:
    def test_roundtrip(self):
        svc = BlindTiltServiceData(device_type=0x58, battery=80)
        assert BlindTiltServiceData.parse(svc.to_bytes()) == svc

    def test_battery_in_byte_2(self):
        assert BlindTiltServiceData(device_type=0x58, battery=63).to_bytes()[2] == 63
        assert BlindTiltServiceData.parse(bytes([0x78, 0x00, 0x2A])).battery == 0x2A


class TestManufacturerData:
    def _mk(self, **overrides) -> BlindTiltManufacturerData:
        base = BlindTiltManufacturerData(
            direction_set=False,
            direction=0,
            calibrated=False,
            moving=False,
            position=0,
            link_length=0,
            connect_allow=False,
            stuck_flag=False,
        )
        return dc.replace(base, **overrides)

    def test_roundtrip_basic(self):
        mfr = self._mk(
            direction_set=True, calibrated=True, position=50, connect_allow=True
        )
        assert BlindTiltManufacturerData.parse(mfr.to_bytes()) == mfr

    def test_roundtrip_moving(self):
        mfr = self._mk(moving=True, position=25, link_length=3)
        assert BlindTiltManufacturerData.parse(mfr.to_bytes()) == mfr

    def test_position_in_byte_8(self):
        assert self._mk(position=73).to_bytes()[8] & 0x7F == 73

    def test_moving_bit_set_means_moving(self):
        """Bit 7 of manufacturer byte 8 is SET while moving."""
        assert self._mk(moving=True).to_bytes()[8] & 0x80
        assert not (self._mk(moving=False).to_bytes()[8] & 0x80)

    def test_stuck_gated_by_moving(self):
        """The stuck flag only reports stuck when not moving."""
        assert self._mk(stuck_flag=True, moving=False).stuck is True
        assert self._mk(stuck_flag=True, moving=True).stuck is False
        assert self._mk(stuck_flag=False, moving=False).stuck is False
