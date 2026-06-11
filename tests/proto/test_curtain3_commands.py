"""Tests for Curtain 3 command serialization."""

from switchbot.proto.core import FixedCommand
from switchbot.proto.curtain3.commands import (
    CalibrateIndex,
    Calibration,
    CalibrationMode,
    CalibrationPause,
    CalibrationTest,
    ClearDelay,
    ClearLightActions,
    ContinueMove,
    DisableNotify,
    EnableNotify,
    GetAdvancedInfo,
    GetCaliDistance,
    GetCaliMode,
    GetChainInfo,
    GetChainStatus,
    GetCurtainInfo,
    GetDelay,
    GetDirection,
    GetLightActionList,
    GetLightData,
    GetLightInfo,
    GetLightSource,
    GetMoveInfo,
    GetSettingInfo,
    GetTimer,
    GetTimerCount,
    GetWorkMode,
    Reboot,
    ResetPwm,
    SetDelay,
    SetLightEnable,
    SetLightSource,
    SetLinkage,
    SetMotionMode,
    SetOpenDirection,
    SetOpenInverse,
    SetPercentage,
    SetTimer,
    SetTimerCount,
    SetTouchGo,
    Shake,
    Stop,
    TinyAdjust,
    Ungroup,
)

# ---------------------------------------------------------------------------
# Known wire format tests
# ---------------------------------------------------------------------------


class TestFixedCommandWireFormat:
    def test_clear_delay(self):
        assert ClearDelay().to_bytes() == bytes([0x57, 0x0F, 0x45, 0x06, 0x00])

    def test_clear_light_actions(self):
        assert ClearLightActions().to_bytes() == bytes([0x57, 0x0F, 0x45, 0x03, 0x03])

    def test_tiny_adjust(self):
        assert TinyAdjust().to_bytes() == bytes([0x57, 0x0F, 0x45, 0x05, 0x0A, 0x03])

    def test_ungroup(self):
        assert Ungroup().to_bytes() == bytes([0x57, 0x0F, 0x45, 0x02, 0x01, 0x00])

    def test_reboot(self):
        assert Reboot().to_bytes() == bytes([0x57, 0x0F, 0x45, 0x82, 0x03])

    def test_disable_notify(self):
        assert DisableNotify().to_bytes() == bytes([0x57, 0x0E, 0x00])

    def test_get_direction(self):
        assert GetDirection().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x05, 0x00])

    def test_get_cali_distance(self):
        assert GetCaliDistance().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x81, 0x03])

    def test_get_cali_mode(self):
        assert GetCaliMode().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x81, 0x04])

    def test_get_curtain_info(self):
        assert GetCurtainInfo().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x81, 0x01])

    def test_get_setting_info(self):
        assert GetSettingInfo().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x04, 0x01])

    def test_get_advanced_info(self):
        assert GetAdvancedInfo().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x04, 0x02])

    def test_get_light_info(self):
        assert GetLightInfo().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x03, 0x00])

    def test_get_light_source(self):
        assert GetLightSource().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x03, 0x02])

    def test_get_delay(self):
        assert GetDelay().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x06])

    def test_get_timer_count(self):
        assert GetTimerCount().to_bytes() == bytes([0x57, 0x08, 0x02])

    def test_get_chain_info(self):
        assert GetChainInfo().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x02, 0x00, 0x01])

    def test_get_chain_status(self):
        assert GetChainStatus().to_bytes() == bytes(
            [0x57, 0x0F, 0x46, 0x02, 0x00, 0x02]
        )

    def test_get_work_mode(self):
        assert GetWorkMode().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x82, 0x03])

    def test_shake(self):
        assert Shake().to_bytes() == bytes([0x57, 0x01, 0x00])


# ---------------------------------------------------------------------------
# Parameterized command wire format
# ---------------------------------------------------------------------------


class TestSetPercentageWireFormat:
    def test_single(self):
        cmd = SetPercentage(index=1, position=50)
        assert cmd.to_bytes() == bytes([0x57, 0x0F, 0x45, 0x01, 0x01, 0x01, 50, 0x00])

    def test_group(self):
        cmd = SetPercentage(index=3, position=50, position2=75)
        assert cmd.to_bytes() == bytes([0x57, 0x0F, 0x45, 0x01, 0x01, 0x03, 50, 75])


class TestStopWireFormat:
    def test_single(self):
        assert Stop(index=1).to_bytes() == bytes([0x57, 0x0F, 0x45, 0x01, 0x00, 0x01])

    def test_group(self):
        assert Stop(index=3).to_bytes() == bytes([0x57, 0x0F, 0x45, 0x01, 0x00, 0x03])


class TestContinueMoveWireFormat:
    def test_open(self):
        cmd = ContinueMove(index=0, direction=1)
        assert cmd.to_bytes() == bytes([0x57, 0x0F, 0x45, 0x05, 0x04, 0x00, 0x01])

    def test_close(self):
        cmd = ContinueMove(index=0, direction=2)
        assert cmd.to_bytes() == bytes([0x57, 0x0F, 0x45, 0x05, 0x04, 0x00, 0x02])


class TestSettingsWireFormat:
    def test_motion_mode(self):
        cmd = SetMotionMode(index=1, mode=0)
        assert cmd.to_bytes() == bytes([0x57, 0x0F, 0x45, 0x04, 0x01, 0x01, 0x00, 0x00])

    def test_touch_go(self):
        cmd = SetTouchGo(index=1, enable=True)
        assert cmd.to_bytes() == bytes([0x57, 0x0F, 0x45, 0x04, 0x03, 0x01, 0x01, 0x01])

    def test_light_enable(self):
        cmd = SetLightEnable(index=1, enable=True)
        assert cmd.to_bytes() == bytes([0x57, 0x0F, 0x45, 0x04, 0x04, 0x01, 0x01, 0x01])

    def test_open_direction(self):
        cmd = SetOpenDirection(index=3, direction1=0, direction2=1)
        assert cmd.to_bytes() == bytes([0x57, 0x0F, 0x45, 0x04, 0x06, 0x03, 0x00, 0x01])


class TestResetPwmWireFormat:
    def test_default(self):
        assert ResetPwm().to_bytes() == bytes([0x57, 0x0F, 0x45, 0x82, 0x02, 50, 50])


# ---------------------------------------------------------------------------
# Fixed command roundtrips
# ---------------------------------------------------------------------------


class TestFixedCommandRoundtrip:
    def test_stop_default(self):
        assert Stop.from_bytes(Stop().to_bytes()) == Stop()

    def test_clear_delay(self):
        assert ClearDelay.from_bytes(ClearDelay().to_bytes()) == ClearDelay()

    def test_ungroup(self):
        assert Ungroup.from_bytes(Ungroup().to_bytes()) == Ungroup()

    def test_reboot(self):
        assert Reboot.from_bytes(Reboot().to_bytes()) == Reboot()

    def test_shake(self):
        assert Shake.from_bytes(Shake().to_bytes()) == Shake()

    def test_subclass_of_fixed_command(self):
        assert issubclass(ClearDelay, FixedCommand)
        assert issubclass(Reboot, FixedCommand)
        assert issubclass(Shake, FixedCommand)


# ---------------------------------------------------------------------------
# Parameterized command roundtrips
# ---------------------------------------------------------------------------


class TestSetPercentageRoundtrip:
    def test_single(self):
        cmd = SetPercentage(index=1, position=50)
        assert SetPercentage.from_bytes(cmd.to_bytes()) == cmd

    def test_group(self):
        cmd = SetPercentage(index=3, position=25, position2=75)
        assert SetPercentage.from_bytes(cmd.to_bytes()) == cmd

    def test_zero(self):
        cmd = SetPercentage(index=1, position=0)
        assert SetPercentage.from_bytes(cmd.to_bytes()) == cmd

    def test_full(self):
        cmd = SetPercentage(index=1, position=100)
        assert SetPercentage.from_bytes(cmd.to_bytes()) == cmd


class TestStopRoundtrip:
    def test_single(self):
        cmd = Stop(index=1)
        assert Stop.from_bytes(cmd.to_bytes()) == cmd

    def test_group(self):
        cmd = Stop(index=3)
        assert Stop.from_bytes(cmd.to_bytes()) == cmd


class TestGetMoveInfoRoundtrip:
    def test_roundtrip(self):
        cmd = GetMoveInfo(index=1)
        assert GetMoveInfo.from_bytes(cmd.to_bytes()) == cmd


class TestCalibrationRoundtrip:
    def test_start(self):
        cmd = Calibration(action=1)
        assert Calibration.from_bytes(cmd.to_bytes()) == cmd

    def test_stop(self):
        cmd = Calibration(action=2)
        assert Calibration.from_bytes(cmd.to_bytes()) == cmd


class TestCalibrationTestRoundtrip:
    def test_roundtrip(self):
        cmd = CalibrationTest(action=1)
        assert CalibrationTest.from_bytes(cmd.to_bytes()) == cmd


class TestContinueMoveRoundtrip:
    def test_open(self):
        cmd = ContinueMove(index=0, direction=1)
        assert ContinueMove.from_bytes(cmd.to_bytes()) == cmd

    def test_close(self):
        cmd = ContinueMove(index=1, direction=2)
        assert ContinueMove.from_bytes(cmd.to_bytes()) == cmd


class TestCalibrationPauseRoundtrip:
    def test_roundtrip(self):
        cmd = CalibrationPause(index=0)
        assert CalibrationPause.from_bytes(cmd.to_bytes()) == cmd


class TestCalibrateIndexRoundtrip:
    def test_roundtrip(self):
        cmd = CalibrateIndex(dev_index=1, item_index=2)
        assert CalibrateIndex.from_bytes(cmd.to_bytes()) == cmd


class TestCalibrationModeRoundtrip:
    def test_roundtrip(self):
        cmd = CalibrationMode(index=0, mode=1)
        assert CalibrationMode.from_bytes(cmd.to_bytes()) == cmd


class TestSetMotionModeRoundtrip:
    def test_performance(self):
        cmd = SetMotionMode(index=1, mode=0)
        assert SetMotionMode.from_bytes(cmd.to_bytes()) == cmd

    def test_quiet(self):
        cmd = SetMotionMode(index=1, mode=1)
        assert SetMotionMode.from_bytes(cmd.to_bytes()) == cmd


class TestSetOpenInverseRoundtrip:
    def test_single(self):
        cmd = SetOpenInverse(index=0, inverse=(True,))
        assert SetOpenInverse.from_bytes(cmd.to_bytes()) == cmd

    def test_group(self):
        cmd = SetOpenInverse(index=0, inverse=(True, False))
        assert SetOpenInverse.from_bytes(cmd.to_bytes()) == cmd


class TestSetTouchGoRoundtrip:
    def test_enable(self):
        cmd = SetTouchGo(index=1, enable=True)
        assert SetTouchGo.from_bytes(cmd.to_bytes()) == cmd

    def test_disable(self):
        cmd = SetTouchGo(index=1, enable=False)
        assert SetTouchGo.from_bytes(cmd.to_bytes()) == cmd


class TestSetLightEnableRoundtrip:
    def test_enable(self):
        cmd = SetLightEnable(index=1, enable=True)
        assert SetLightEnable.from_bytes(cmd.to_bytes()) == cmd


class TestSetOpenDirectionRoundtrip:
    def test_roundtrip(self):
        cmd = SetOpenDirection(index=3, direction1=0, direction2=1)
        assert SetOpenDirection.from_bytes(cmd.to_bytes()) == cmd


class TestSetLightSourceRoundtrip:
    def test_roundtrip(self):
        cmd = SetLightSource(index=0, source=1)
        assert SetLightSource.from_bytes(cmd.to_bytes()) == cmd


class TestGetLightActionListRoundtrip:
    def test_roundtrip(self):
        cmd = GetLightActionList(index=2)
        assert GetLightActionList.from_bytes(cmd.to_bytes()) == cmd


class TestGetLightDataRoundtrip:
    def test_roundtrip(self):
        cmd = GetLightData(time_range=2, source=1, index=False)
        assert GetLightData.from_bytes(cmd.to_bytes()) == cmd

    def test_index_true(self):
        cmd = GetLightData(time_range=0, source=0, index=True)
        assert GetLightData.from_bytes(cmd.to_bytes()) == cmd


class TestSetDelayRoundtrip:
    def test_roundtrip(self):
        cmd = SetDelay(
            timestamp=1700000000,
            mode=0,
            action=bytes([0x01, 0x01, 0x03, 50, 0]),
        )
        assert SetDelay.from_bytes(cmd.to_bytes()) == cmd

    def test_wire_format(self):
        # 4-byte big-endian timestamp (0x6553F100), then mode, then action.
        cmd = SetDelay(timestamp=0x6553F100, mode=0, action=bytes([0x01, 0x01, 50]))
        assert cmd.to_bytes() == bytes(
            [0x57, 0x0F, 0x45, 0x06, 0x01, 0x65, 0x53, 0xF1, 0x00, 0x00, 0x01, 0x01, 50]
        )


class TestSetLinkageRoundtrip:
    def test_roundtrip(self):
        cmd = SetLinkage(secondary_mac=bytes([0xAA, 0xBB, 0xCC, 0xDD, 0xEE, 0xFF]))
        assert SetLinkage.from_bytes(cmd.to_bytes()) == cmd


class TestResetPwmRoundtrip:
    def test_default(self):
        cmd = ResetPwm()
        assert ResetPwm.from_bytes(cmd.to_bytes()) == cmd

    def test_custom(self):
        cmd = ResetPwm(left=30, right=70)
        assert ResetPwm.from_bytes(cmd.to_bytes()) == cmd


class TestGetTimerRoundtrip:
    def test_roundtrip(self):
        for i in range(4):
            cmd = GetTimer(index=i)
            assert GetTimer.from_bytes(cmd.to_bytes()) == cmd


class TestSetTimerCountRoundtrip:
    def test_roundtrip(self):
        cmd = SetTimerCount(count=3)
        assert SetTimerCount.from_bytes(cmd.to_bytes()) == cmd


class TestSetTimerRoundtrip:
    def test_with_repeat(self):
        cmd = SetTimer(
            index=0,
            enable=True,
            action_mode=0,
            repeat_days=0b0111110,
            hour=7,
            minute=30,
            action=bytes([0x05, 0x00, 50]),
        )
        assert SetTimer.from_bytes(cmd.to_bytes()) == cmd

    def test_no_repeat(self):
        cmd = SetTimer(
            index=1,
            enable=True,
            action_mode=1,
            repeat_days=None,
            hour=18,
            minute=0,
            action=bytes([0x07, 0x02]),
        )
        assert SetTimer.from_bytes(cmd.to_bytes()) == cmd


class TestEnableNotifyRoundtrip:
    def test_roundtrip(self):
        cmd = EnableNotify(
            time_unit=0xC0,
            interval=0x00,
            read_info_cmd=b"\x57\x0f\x46\x81\x01",
        )
        assert EnableNotify.from_bytes(cmd.to_bytes()) == cmd
