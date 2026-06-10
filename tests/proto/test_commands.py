"""Tests for Blind Tilt command serialization."""

from switchbot.proto.blind_tilt.commands import (
    ClearAiLight,
    ClearDelay,
    ClearLightActions,
    DisableNotify,
    EnableNotify,
    FixedCommand,
    GetActionMode,
    GetAdvancedInfo,
    GetAiLightAction,
    GetAiLightCount,
    GetCalibration,
    GetCalibrationStep,
    GetDelay,
    GetDeviceLink,
    GetGroupChargeInfo,
    GetGroupFirmwareBattery,
    GetGroupLinks,
    GetLightAction,
    GetLightData,
    GetLightInfo,
    GetLightSource,
    GetPosition,
    GetTimer,
    GetTimerCount,
    GetWorkMode,
    SaveCalibration,
    SetActionMode,
    SetDelay,
    SetDirection,
    SetLightAction,
    SetLightRule,
    SetLightSource,
    SetPosition,
    SetTimer,
    SetTimerCount,
    StartCalibration,
    Stop,
    StopCalibration,
)

# ---------------------------------------------------------------------------
# Known wire format tests
# ---------------------------------------------------------------------------


class TestFixedCommandWireFormat:
    def test_stop(self):
        assert Stop().to_bytes() == bytes([0x57, 0x0F, 0x45, 0x01, 0x00, 0x01])

    def test_start_calibration(self):
        assert StartCalibration().to_bytes() == bytes([0x57, 0x0F, 0x45, 0x05, 0x01])

    def test_stop_calibration(self):
        assert StopCalibration().to_bytes() == bytes([0x57, 0x0F, 0x45, 0x05, 0x02])

    def test_clear_delay(self):
        assert ClearDelay().to_bytes() == bytes([0x57, 0x0F, 0x45, 0x06, 0x00])

    def test_clear_light_actions(self):
        assert ClearLightActions().to_bytes() == bytes([0x57, 0x0F, 0x45, 0x03, 0x03])

    def test_clear_ai_light(self):
        assert ClearAiLight().to_bytes() == bytes([0x57, 0x0F, 0x45, 0x03, 0x05])

    def test_disable_notify(self):
        assert DisableNotify().to_bytes() == bytes([0x57, 0x0E, 0x00])

    def test_get_position(self):
        assert GetPosition().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x01, 0x00])

    def test_get_calibration(self):
        assert GetCalibration().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x05])

    def test_get_calibration_step(self):
        assert GetCalibrationStep().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x09])

    def test_get_action_mode(self):
        assert GetActionMode().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x04, 0x03])

    def test_get_advanced_info(self):
        assert GetAdvancedInfo().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x04, 0x02])

    def test_get_work_mode(self):
        assert GetWorkMode().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x82, 0x03])

    def test_get_light_info(self):
        assert GetLightInfo().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x03, 0x00])

    def test_get_light_source(self):
        assert GetLightSource().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x03, 0x02])

    def test_get_ai_light_count(self):
        assert GetAiLightCount().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x03, 0x06])

    def test_get_ai_light_action(self):
        assert GetAiLightAction().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x03, 0x07])

    def test_get_delay(self):
        assert GetDelay().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x06])

    def test_get_timer_count(self):
        assert GetTimerCount().to_bytes() == bytes([0x57, 0x08, 0x02])

    def test_get_group_firmware_battery(self):
        assert GetGroupFirmwareBattery().to_bytes() == bytes(
            [0x57, 0x0F, 0x46, 0x81, 0x06]
        )

    def test_get_group_charge_info(self):
        assert GetGroupChargeInfo().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x81, 0x07])

    def test_get_group_links(self):
        assert GetGroupLinks().to_bytes() == bytes([0x57, 0x0F, 0x46, 0x02, 0xFF, 0x03])

    def test_get_device_link(self):
        assert GetDeviceLink(index=0xFF).to_bytes() == bytes(
            [0x57, 0x0F, 0x46, 0x02, 0xFF, 0x04]
        )


# ---------------------------------------------------------------------------
# Fixed command roundtrips
# ---------------------------------------------------------------------------


class TestFixedCommandRoundtrip:
    def test_stop(self):
        assert Stop.from_bytes(Stop().to_bytes()) == Stop()

    def test_start_calibration(self):
        assert (
            StartCalibration.from_bytes(StartCalibration().to_bytes())
            == StartCalibration()
        )

    def test_disable_notify(self):
        assert DisableNotify.from_bytes(DisableNotify().to_bytes()) == DisableNotify()

    def test_get_timer_count(self):
        assert GetTimerCount.from_bytes(GetTimerCount().to_bytes()) == GetTimerCount()

    def test_subclass_of_fixed_command(self):
        assert issubclass(Stop, FixedCommand)
        assert issubclass(GetPosition, FixedCommand)


# ---------------------------------------------------------------------------
# Parameterized command wire format
# ---------------------------------------------------------------------------


class TestSetPositionWireFormat:
    def test_modern_fw(self):
        cmd = SetPosition(position=50)
        assert cmd.to_bytes(fw_version=20) == bytes(
            [0x57, 0x0F, 0x45, 0x01, 0x05, 0xFF, 50]
        )

    def test_legacy_fw(self):
        cmd = SetPosition(position=75)
        assert cmd.to_bytes(fw_version=1) == bytes(
            [0x57, 0x0F, 0x45, 0x01, 0x01, 0x01, 75]
        )


class TestSetDirectionWireFormat:
    def test_horizontal(self):
        assert SetDirection(horizontal=True).to_bytes() == bytes(
            [0x57, 0x0F, 0x45, 0x04, 0x06, 0x01, 0x02]
        )

    def test_vertical(self):
        assert SetDirection(horizontal=False).to_bytes() == bytes(
            [0x57, 0x0F, 0x45, 0x04, 0x06, 0x01, 0x03]
        )


# ---------------------------------------------------------------------------
# Parameterized command roundtrips
# ---------------------------------------------------------------------------


class TestSetPositionRoundtrip:
    def test_modern(self):
        cmd = SetPosition(position=50)
        assert SetPosition.from_bytes(cmd.to_bytes(fw_version=20), fw_version=20) == cmd

    def test_legacy(self):
        cmd = SetPosition(position=0)
        assert SetPosition.from_bytes(cmd.to_bytes(fw_version=1), fw_version=1) == cmd

    def test_full(self):
        cmd = SetPosition(position=100)
        assert SetPosition.from_bytes(cmd.to_bytes(fw_version=20), fw_version=20) == cmd


class TestSetDirectionRoundtrip:
    def test_horizontal(self):
        cmd = SetDirection(horizontal=True)
        assert SetDirection.from_bytes(cmd.to_bytes()) == cmd

    def test_vertical(self):
        cmd = SetDirection(horizontal=False)
        assert SetDirection.from_bytes(cmd.to_bytes()) == cmd


class TestSetActionModeRoundtrip:
    def test_roundtrip(self):
        cmd = SetActionMode(mode=3)
        assert SetActionMode.from_bytes(cmd.to_bytes()) == cmd


class TestSaveCalibrationRoundtrip:
    def test_zero(self):
        cmd = SaveCalibration(preset=1)
        assert SaveCalibration.from_bytes(cmd.to_bytes()) == cmd

    def test_full(self):
        cmd = SaveCalibration(preset=3)
        assert SaveCalibration.from_bytes(cmd.to_bytes()) == cmd


class TestGetLightActionRoundtrip:
    def test_roundtrip(self):
        cmd = GetLightAction(index=5)
        assert GetLightAction.from_bytes(cmd.to_bytes()) == cmd


class TestGetLightDataRoundtrip:
    def test_roundtrip(self):
        cmd = GetLightData(time_range=2, source=1, index=False)
        assert GetLightData.from_bytes(cmd.to_bytes()) == cmd

    def test_roundtrip_index_1(self):
        cmd = GetLightData(time_range=0, source=0, index=True)
        assert GetLightData.from_bytes(cmd.to_bytes()) == cmd


class TestGetTimerRoundtrip:
    def test_roundtrip(self):
        for i in range(4):
            cmd = GetTimer(index=i)
            assert GetTimer.from_bytes(cmd.to_bytes()) == cmd


class TestSetTimerCountRoundtrip:
    def test_roundtrip(self):
        cmd = SetTimerCount(count=5)
        assert SetTimerCount.from_bytes(cmd.to_bytes()) == cmd


class TestSetLightSourceRoundtrip:
    def test_builtin(self):
        cmd = SetLightSource(index=0, external=False)
        assert SetLightSource.from_bytes(cmd.to_bytes()) == cmd

    def test_external(self):
        cmd = SetLightSource(index=1, external=True)
        assert SetLightSource.from_bytes(cmd.to_bytes()) == cmd


# ---------------------------------------------------------------------------
# Complex command roundtrips
# ---------------------------------------------------------------------------


class TestSetDelayRoundtrip:
    def test_modern_wire_format(self):
        # 4-byte big-endian timestamp (0x6553F100), then 0x01, then 05 FF <pos>.
        cmd = SetDelay(timestamp=0x6553F100, position=50)
        assert cmd.to_bytes(fw_version=20) == bytes(
            [0x57, 0x0F, 0x45, 0x06, 0x01, 0x65, 0x53, 0xF1, 0x00, 0x01, 0x05, 0xFF, 50]
        )

    def test_modern(self):
        cmd = SetDelay(timestamp=1700000000, position=50)
        assert SetDelay.from_bytes(cmd.to_bytes(fw_version=20), fw_version=20) == cmd

    def test_legacy(self):
        cmd = SetDelay(timestamp=1700000000, position=75)
        assert SetDelay.from_bytes(cmd.to_bytes(fw_version=1), fw_version=1) == cmd


class TestSetLightActionRoundtrip:
    def test_modern(self):
        cmd = SetLightAction(index=2, position=80)
        assert (
            SetLightAction.from_bytes(cmd.to_bytes(fw_version=20), fw_version=20) == cmd
        )

    def test_legacy(self):
        cmd = SetLightAction(index=0, position=0)
        assert (
            SetLightAction.from_bytes(cmd.to_bytes(fw_version=1), fw_version=1) == cmd
        )


class TestSetLightRuleRoundtrip:
    def test_roundtrip(self):
        cmd = SetLightRule(
            index=1,
            enable=True,
            threshold_type=2,
            threshold=10,
            repeat_days=0b1111111,
            start_hour=8,
            start_minute=30,
            duration_minutes=120,
        )
        assert SetLightRule.from_bytes(cmd.to_bytes()) == cmd

    def test_disabled(self):
        cmd = SetLightRule(
            index=0,
            enable=False,
            threshold_type=1,
            threshold=5,
            repeat_days=0,
            start_hour=0,
            start_minute=0,
            duration_minutes=0,
        )
        assert SetLightRule.from_bytes(cmd.to_bytes()) == cmd


class TestEnableNotifyRoundtrip:
    def test_roundtrip(self):
        cmd = EnableNotify(time_unit=0xC0, interval=0x00, read_info_cmd=b"\xf2\x01\x00")
        assert EnableNotify.from_bytes(cmd.to_bytes()) == cmd

    def test_wire_format(self):
        cmd = EnableNotify(time_unit=0x00, interval=0x00, read_info_cmd=b"\xf2\x01\x00")
        assert cmd.to_bytes() == bytes(
            [0x57, 0x0E, 0x01, 0x00, 0x00, 0xFF, 0xFF, 0xF2, 0x01, 0x00]
        )


class TestGetDeviceLinkRoundtrip:
    def test_roundtrip(self):
        cmd = GetDeviceLink(index=0x02)
        assert GetDeviceLink.from_bytes(cmd.to_bytes()) == cmd

    def test_wire_format(self):
        cmd = GetDeviceLink(index=0xFF)
        assert cmd.to_bytes() == bytes([0x57, 0x0F, 0x46, 0x02, 0xFF, 0x04])


class TestSetTimerRoundtrip:
    def test_modern_with_repeat(self):
        cmd = SetTimer(
            index=0,
            enable=True,
            repeat_days=0b0111110,
            hour=7,
            minute=30,
            position=100,
        )
        assert SetTimer.from_bytes(cmd.to_bytes(fw_version=20), fw_version=20) == cmd

    def test_no_repeat(self):
        cmd = SetTimer(
            index=2,
            enable=True,
            repeat_days=None,
            hour=18,
            minute=0,
            position=0,
        )
        assert SetTimer.from_bytes(cmd.to_bytes(fw_version=20), fw_version=20) == cmd

    def test_legacy(self):
        cmd = SetTimer(
            index=1,
            enable=False,
            repeat_days=0b1000001,
            hour=12,
            minute=0,
            position=50,
        )
        assert SetTimer.from_bytes(cmd.to_bytes(fw_version=1), fw_version=1) == cmd
