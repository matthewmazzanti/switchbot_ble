"""Tests for Curtain 3 advertisement data parsing."""

import dataclasses as dc

from switchbot.proto.core import device_type
from switchbot.proto.curtain3.advertisement import (
    DEVICE_TYPE,
    Curtain3ManufacturerData,
    Curtain3ServiceData,
)


class TestCurtain3ServiceData:
    def _mk(self, **overrides) -> Curtain3ServiceData:
        base = Curtain3ServiceData(
            pair_mode=False,
            is_primary=True,
            calibrated=True,
            battery=80,
            position=50,
            in_group=False,
            too_hot=False,
        )
        return dc.replace(base, **overrides)

    def test_roundtrip(self):
        for adv in (
            self._mk(),
            self._mk(pair_mode=True, in_group=True, too_hot=True),
            self._mk(calibrated=False, is_primary=False, battery=0, position=100),
        ):
            assert Curtain3ServiceData.parse(adv.to_bytes()) == adv

    def test_device_type_identity(self):
        # 0x7B normal / 0x5B pairing both mask to the Curtain 3 identity.
        assert device_type(0x5B) == DEVICE_TYPE
        assert device_type(0x7B) == DEVICE_TYPE

    def test_pair_mode_device_type(self):
        assert self._mk(pair_mode=True).to_bytes()[0] & 0x7F == 0x5B
        assert self._mk(pair_mode=False).to_bytes()[0] & 0x7F == 0x7B

    def test_calibration_bit(self):
        assert self._mk(calibrated=True).to_bytes()[1] & 0x40
        assert not (self._mk(calibrated=False).to_bytes()[1] & 0x40)

    def test_too_hot_bit(self):
        assert self._mk(too_hot=True).to_bytes()[5] & 0x07 == 7
        assert self._mk(too_hot=False).to_bytes()[5] & 0x07 == 0

    def test_parses_real_packet(self):
        # Real Curtain 3 service broadcast (advertising pairing form 0x5B):
        # battery 87%, fully open, primary, uncalibrated, not too hot.
        adv = Curtain3ServiceData.parse(bytes.fromhex("5b80d7001100"))
        assert adv.pair_mode is True
        assert adv.is_primary is True
        assert adv.calibrated is False
        assert adv.battery == 87
        assert adv.position == 0
        assert adv.in_group is False
        assert adv.too_hot is False


class TestCurtain3ManufacturerData:
    def _mk(self, **overrides) -> Curtain3ManufacturerData:
        base = Curtain3ManufacturerData(
            temp_too_high=False,
            temp_too_low=False,
            geomag_alarm=False,
            ear_type=0,
            pre_group=False,
        )
        return dc.replace(base, **overrides)

    def test_roundtrip(self):
        for adv in (
            self._mk(),
            self._mk(temp_too_high=True, ear_type=3),
            self._mk(temp_too_low=True, pre_group=True),
            self._mk(geomag_alarm=True, ear_type=15),
        ):
            assert Curtain3ManufacturerData.parse(adv.to_bytes()) == adv

    def test_temp_flags_in_byte7_high_bits(self):
        assert self._mk(temp_too_high=True).to_bytes()[7] & 0xC0 == 0x80
        assert self._mk(temp_too_low=True).to_bytes()[7] & 0xC0 == 0x40

    def test_parses_real_packet(self):
        # Real Curtain 3 manufacturer data (placeholder MAC + captured fields).
        mfr = Curtain3ManufacturerData.parse(
            bytes.fromhex("aabbccddeeff03020011000157")
        )
        assert mfr.temp_too_high is False
        assert mfr.temp_too_low is False
        assert mfr.geomag_alarm is False
        assert mfr.ear_type == 1
        assert mfr.pre_group is False
