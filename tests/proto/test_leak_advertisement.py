"""Tests for Water Leak Detector advertisement data parsing."""

import dataclasses as dc

from switchbot.proto.core import device_type
from switchbot.proto.leak.advertisement import (
    DEVICE_TYPE,
    LeakManufacturerData,
    LeakServiceData,
)


class TestLeakServiceData:
    def test_roundtrip(self):
        for adv in (LeakServiceData(pair_mode=False), LeakServiceData(pair_mode=True)):
            assert LeakServiceData.parse(adv.to_bytes()) == adv

    def test_device_type_identity(self):
        # 0x26 normal / 0x06 pairing ("add") both mask to the leak identity.
        assert device_type(0x26) == DEVICE_TYPE
        assert device_type(0x06) == DEVICE_TYPE

    def test_pair_mode_device_type(self):
        # WO_BLE_TYPE_WATERDETECTOR = 38 (0x26) / _ADD = 6 (0x06).
        assert LeakServiceData(pair_mode=False).to_bytes()[0] == 0x26
        assert LeakServiceData(pair_mode=True).to_bytes()[0] == 0x06

    def test_parse_pair_mode(self):
        assert LeakServiceData.parse(bytes([0x06])).pair_mode is True
        assert LeakServiceData.parse(bytes([0x26])).pair_mode is False


class TestLeakManufacturerData:
    def _mk(self, **overrides) -> LeakManufacturerData:
        base = LeakManufacturerData(
            sequence=42,
            battery=85,
            alarm_mode=1,
            current_state=1,
            alarming=True,
            alarm_volume=2,
            beat_state=True,
            alarm_num=1,
            state_change_time=0x01020304,
            alarm_duration=10,
            alarm_interval=30,
            test_utc=0x05060708,
        )
        return dc.replace(base, **overrides)

    def test_roundtrip(self):
        for adv in (
            self._mk(),
            self._mk(alarm_mode=0, current_state=0, alarming=False, beat_state=False),
            self._mk(battery=0, alarm_volume=0, alarm_num=0),
            self._mk(battery=100, alarm_volume=3, alarm_num=3, sequence=255),
        ):
            assert LeakManufacturerData.parse(adv.to_bytes()) == adv

    def test_parses_known_frame(self):
        # Bytes 0-5 are MAC (ignored); fields start at byte 6. Byte 8 = 0xF5:
        # alarm_mode(7)=1, current_state(6)=1, alarming(5)=1, volume(4:3)=2,
        # beat_state(2)=1, alarm_num(1:0)=1.
        frame = bytes.fromhex("aaaaaaaaaaaa2ad5f5010203040a1e05060708")
        adv = LeakManufacturerData.parse(frame)
        assert adv.sequence == 0x2A
        assert adv.battery == 85  # 0xD5 & 0x7F
        assert adv.alarm_mode == 1
        assert adv.current_state == 1
        assert adv.alarming is True
        assert adv.alarm_volume == 2
        assert adv.beat_state is True
        assert adv.alarm_num == 1
        assert adv.state_change_time == 0x01020304
        assert adv.alarm_duration == 0x0A
        assert adv.alarm_interval == 0x1E
        assert adv.test_utc == 0x05060708

    def test_byte8_bit_positions(self):
        # Anchor each flag to its exact bit in byte 8.
        assert self._mk(alarm_mode=1).to_bytes()[8] & 0x80
        assert self._mk(current_state=1).to_bytes()[8] & 0x40
        assert self._mk(alarming=True).to_bytes()[8] & 0x20
        assert self._mk(beat_state=True).to_bytes()[8] & 0x04
        assert (self._mk(alarm_volume=3).to_bytes()[8] & 0x18) >> 3 == 3
        assert self._mk(alarm_num=3).to_bytes()[8] & 0x03 == 3

    def test_battery_masks_high_bit(self):
        # data[7] & 0x7F — high bit is not part of the battery level.
        assert LeakManufacturerData.parse(self._mk(battery=85).to_bytes()).battery == 85
        raw = bytearray(self._mk(battery=85).to_bytes())
        raw[7] |= 0x80
        assert LeakManufacturerData.parse(bytes(raw)).battery == 85

    def test_in_alert(self):
        # isInAlert: current measured state matches the configured alarm mode.
        assert self._mk(alarm_mode=1, current_state=1).in_alert is True
        assert self._mk(alarm_mode=0, current_state=0).in_alert is True
        assert self._mk(alarm_mode=1, current_state=0).in_alert is False
        assert self._mk(alarm_mode=0, current_state=1).in_alert is False
