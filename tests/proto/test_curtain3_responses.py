"""Tests for Curtain 3 response parsing.

Roundtrip `parse(to_bytes(x)) == x` for each reply, plus parse-from-fixed-bytes
checks pinning the decomp-verified byte offsets.
"""

import pytest

from switchbot.proto.curtain3.responses import (
    CaliDistanceReply,
    CaliModeReply,
    ChainInfoReply,
    CurtainInfoReply,
    DelayInfoReply,
    DirectionReply,
    LightActionReply,
    MoveInfoReply,
    SettingsInfoReply,
    WorkModeReply,
)


class TestRoundtrip:
    def test_chain_info(self):
        r = ChainInfoReply(
            pre_mac=bytes.fromhex("aabbccddeeff"),
            next_mac=bytes.fromhex("112233445566"),
        )
        assert ChainInfoReply.parse(r.to_bytes()) == r

    def test_curtain_info(self):
        r = CurtainInfoReply(
            delay_enabled=True,
            motion_status=3,
            action_mode=0x20,
            timer_num=2,
            link_length=2,
            dev0_solar_plugin=True,
            dev0_position=78,
            dev0_charging=False,
            dev0_battery=96,
            dev1_solar_plugin=False,
            dev1_position=100,
            dev1_charging=True,
            dev1_battery=82,
        )
        assert CurtainInfoReply.parse(r.to_bytes()) == r

    def test_move_info(self):
        for moving in (True, False):
            r = MoveInfoReply(moving=moving)
            assert MoveInfoReply.parse(r.to_bytes()) == r

    def test_direction(self):
        for d in (0, 1):
            r = DirectionReply(direction=d)
            assert DirectionReply.parse(r.to_bytes()) == r

    def test_work_mode(self):
        r = WorkModeReply(work_mode=0x42)
        assert WorkModeReply.parse(r.to_bytes()) == r

    def test_cali_mode(self):
        r = CaliModeReply(cali_mode=1)
        assert CaliModeReply.parse(r.to_bytes()) == r

    def test_cali_distance(self):
        r = CaliDistanceReply(
            index_byte=1, distance1_raw=12345, distance2_raw=6789
        )
        assert CaliDistanceReply.parse(r.to_bytes()) == r

    def test_delay_info(self):
        r = DelayInfoReply(
            timestamp=0x6500ABCD, mode=2, action=bytes([0x01, 0x01, 0x32])
        )
        assert DelayInfoReply.parse(r.to_bytes()) == r

    def test_settings_info(self):
        r = SettingsInfoReply(
            open_inverse=True,
            touch_and_go=False,
            light_enable=True,
            voice_enable=False,
            open_direction=True,
        )
        assert SettingsInfoReply.parse(r.to_bytes()) == r

    def test_light_action(self):
        r = LightActionReply(
            index=1,
            action_mode=2,
            enabled=True,
            threshold_type=1,
            threshold=7,
            repeat_days=0x7F,
            start_hour=6,
            start_minute=30,
            time_length_min=120,
            action=bytes([0x05, 0xFF, 0x32]),
        )
        assert LightActionReply.parse(r.to_bytes()) == r


class TestParseFixed:
    def test_chain_info_offsets(self):
        # status, rsvd, pre_mac[2:8], own[8:14], next_mac[14:20]
        data = bytes(
            [0x01, 0x00]
            + [0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0xA6]
            + [0xFF] * 6
            + [0xB1, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6]
        )
        r = ChainInfoReply.parse(data)
        assert r.pre_mac == bytes.fromhex("a1a2a3a4a5a6")
        assert r.next_mac == bytes.fromhex("b1b2b3b4b5b6")

    def test_chain_info_empty_neighbour(self):
        # All-zero next_mac (EMPTY_MAC) => no neighbour => None (standalone).
        data = bytes([0x01, 0x00] + [0xA1] * 6 + [0x00] * 6 + [0x00] * 6)
        r = ChainInfoReply.parse(data)
        assert r.pre_mac == bytes([0xA1] * 6)
        assert r.next_mac is None
        # roundtrips: None -> zeros -> None
        assert ChainInfoReply.parse(r.to_bytes()) == r

    def test_curtain_info_real_layout(self):
        # byte1=0x43 (delay on, motion 3), byte2=0x22 (action 0x20, timer 2),
        # byte3=2 link, byte4=0xCE (solar, pos 78), byte5=0x60 (no chg, batt 96),
        # byte6=0x64 (no solar, pos 100), byte7=0xD2 (chg, batt 82).
        data = bytes([0x01, 0x43, 0x22, 0x02, 0xCE, 0x60, 0x64, 0xD2])
        r = CurtainInfoReply.parse(data)
        assert r.delay_enabled is True
        assert r.motion_status == 3
        assert r.action_mode == 0x20
        assert r.timer_num == 2
        assert r.link_length == 2
        assert (r.dev0_solar_plugin, r.dev0_position) == (True, 78)
        assert (r.dev0_charging, r.dev0_battery) == (False, 96)
        assert (r.dev1_position, r.dev1_charging, r.dev1_battery) == (100, True, 82)

    def test_link_length_clamped(self):
        # wire byte 3 == 0 still reports a length of 1.
        data = bytes([0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        assert CurtainInfoReply.parse(data).link_length == 1

    def test_direction_polarity(self):
        assert DirectionReply.parse(bytes([0x01, 0x00])).is_master_left is True
        assert DirectionReply.parse(bytes([0x01, 0x01])).is_master_left is False

    def test_cali_distance_derived(self):
        r = CaliDistanceReply(index_byte=1, distance1_raw=100, distance2_raw=40)
        assert r.single_curtain is True
        assert r.distance1_mm == 50  # 100 * 5 * 0.1
        assert r.distance2_mm == 20

    def test_cali_mode_auto(self):
        assert CaliModeReply.parse(bytes([0x01, 0x01])).auto_calibrated is True
        assert CaliModeReply.parse(bytes([0x01, 0x00])).auto_calibrated is False

    def test_work_mode_offset(self):
        # work_mode is byte 4, not byte 1.
        assert WorkModeReply.parse(bytes([0x01, 0, 0, 0, 0x07])).work_mode == 0x07

    def test_light_action_times(self):
        r = LightActionReply.parse(
            bytes([0x01, 0x21, 0x57, 0x7F, 0x06, 0x1E, 0x00, 0x78, 0x05, 0xFF])
        )
        assert r.index == 1
        assert r.action_mode == 2
        assert r.enabled is True
        assert r.start_time_s == 6 * 3600 + 30 * 60
        assert r.time_length_min == 120
        assert r.time_length_s == 7200
        assert r.action == bytes([0x05, 0xFF])


class TestLengthGuards:
    def test_short_replies_raise(self):
        for cls, n in [
            (ChainInfoReply, 19),
            (CurtainInfoReply, 7),
            (MoveInfoReply, 1),
            (WorkModeReply, 4),
            (CaliDistanceReply, 9),
            (DelayInfoReply, 5),
            (SettingsInfoReply, 1),
            (LightActionReply, 7),
        ]:
            with pytest.raises(ValueError):
                cls.parse(bytes(n))
