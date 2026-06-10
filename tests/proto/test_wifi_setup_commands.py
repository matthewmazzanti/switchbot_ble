"""Tests for the shared Wi-Fi onboarding commands."""

import pytest

from switchbot.proto.wifi_setup.commands import (
    GetDeviceInfo,
    GetWifiIp,
    GetWifiStatus,
    NetSetupOver,
    ReadCurrentSsid,
    ReadScanSsidInfo,
    ReadSsidSignal,
    ScanSsid,
    SetRegion,
    SetSsid,
    SetWifiPassword,
    UtcTime,
)


class TestFixedCommands:
    def test_exact_wire(self):
        # Anchored to CmdGenerator output (57 0F <sub> ...).
        assert NetSetupOver().to_bytes() == bytes.fromhex("570f03")
        assert GetWifiStatus().to_bytes() == bytes.fromhex("570f04")
        assert GetWifiIp().to_bytes() == bytes.fromhex("570f1302")
        assert GetDeviceInfo().to_bytes() == bytes.fromhex("570003")

    def test_roundtrip(self):
        for cmd in (NetSetupOver(), GetWifiStatus(), GetWifiIp(), GetDeviceInfo()):
            assert type(cmd).from_bytes(cmd.to_bytes()) == cmd


class TestParamCommands:
    def test_set_region(self):
        assert SetRegion(2).to_bytes() == bytes.fromhex("570f0c02")
        assert SetRegion.from_bytes(bytes.fromhex("570f0c02")) == SetRegion(2)

    def test_scan_ssid(self):
        assert ScanSsid(1).to_bytes() == bytes.fromhex("570f1001")
        assert ScanSsid.from_bytes(bytes.fromhex("570f1001")) == ScanSsid(1)

    def test_read_scan_ssid_info(self):
        assert ReadScanSsidInfo(0, 1).to_bytes() == bytes.fromhex("570f110001")
        assert ReadScanSsidInfo.from_bytes(bytes.fromhex("570f110203")) == (
            ReadScanSsidInfo(2, 3)
        )

    def test_read_ssid_signal(self):
        assert ReadSsidSignal(3).to_bytes() == bytes.fromhex("570f1203")

    def test_read_current_ssid(self):
        assert ReadCurrentSsid(0).to_bytes() == bytes.fromhex("570f0f00")

    def test_utc_time(self):
        # 57 00 05 01 <8-byte big-endian unix seconds>.
        assert UtcTime(0x01020304).to_bytes() == bytes.fromhex(
            "57000501" + "0000000001020304"
        )
        assert UtcTime.from_bytes(UtcTime(1_700_000_000).to_bytes()) == (
            UtcTime(1_700_000_000)
        )


class TestSetSsid:
    def test_single_chunk(self):
        # 57 0F 01 <total=2> <idx=0> "Hi"
        assert SetSsid(b"Hi").to_packets() == [bytes.fromhex("570f0102004869")]

    def test_multi_chunk_split_at_11(self):
        ssid = b"0123456789AB"  # 12 bytes -> 11 + 1
        packets = SetSsid(ssid).to_packets()
        assert len(packets) == 2
        # total_len=0x0c in both; chunk indices 0 then 1.
        assert packets[0] == bytes.fromhex("570f010c00") + b"0123456789A"
        assert packets[1] == bytes.fromhex("570f010c01") + b"B"

    def test_roundtrip(self):
        for ssid in (b"Hi", b"my-network", b"0123456789AB", b"x" * 32):
            assert SetSsid.from_packets(SetSsid(ssid).to_packets()) == SetSsid(ssid)

    def test_rejects_out_of_order(self):
        packets = SetSsid(b"0123456789AB").to_packets()
        with pytest.raises(ValueError, match="out of order"):
            SetSsid.from_packets(list(reversed(packets)))


class TestSetWifiPassword:
    def test_simple(self):
        # p=0x70, w=0x77; total_len=2, idx=0.
        assert SetWifiPassword(b"pw").to_packets() == [bytes.fromhex("570f0202007077")]

    def test_empty_is_open_network_sentinel(self):
        assert SetWifiPassword(b"").to_packets() == [bytes.fromhex("570f02010000")]
        assert SetWifiPassword.from_packets([bytes.fromhex("570f02010000")]) == (
            SetWifiPassword(b"")
        )

    def test_roundtrip(self):
        for pw in (b"", b"hunter2", b"a-longer-passphrase-here", b"z" * 24):
            assert SetWifiPassword.from_packets(
                SetWifiPassword(pw).to_packets()
            ) == SetWifiPassword(pw)
