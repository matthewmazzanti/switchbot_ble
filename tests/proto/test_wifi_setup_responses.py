"""Tests for the shared Wi-Fi onboarding responses."""

from switchbot.proto.wifi_setup.responses import (
    AwsKeyResponse,
    AwsStatus,
    BaseInfoResponse,
    ReplyStatus,
    StatusResponse,
    WifiIpResponse,
    WifiStatusResponse,
    WifiVersionResponse,
    is_success,
)


class TestStatus:
    def test_success_codes(self):
        # checkReplySuccess: OK (1) and BTL (6) only.
        assert is_success(ReplyStatus.OK)
        assert is_success(ReplyStatus.BTL)
        assert not is_success(ReplyStatus.ERROR)
        assert not is_success(ReplyStatus.PASSWORD_INVALID)

    def test_status_response(self):
        assert StatusResponse.from_bytes(b"\x01").ok is True
        assert StatusResponse.from_bytes(b"\x02").ok is False
        assert StatusResponse(1).to_bytes() == b"\x01"


class TestWifiStatus:
    def test_parses_known_reply(self):
        # [0]=status, [1]=net status, [2]=aws status(0x31=49 OK), [3:9]=MAC.
        reply = bytes.fromhex("00" "01" "31" "aabbccddeeff")
        r = WifiStatusResponse.from_bytes(reply)
        assert r.status == 0
        assert r.net_status == 1
        assert r.aws_status == AwsStatus.OK
        assert r.aws_connected is True
        assert r.mac == bytes.fromhex("aabbccddeeff")
        assert r.mac_hex == "aa:bb:cc:dd:ee:ff"

    def test_roundtrip(self):
        mac = bytes.fromhex("001122334455")
        r = WifiStatusResponse(1, 2, AwsStatus.CONNECT_FAIL, mac)
        assert WifiStatusResponse.from_bytes(r.to_bytes()) == r
        assert r.aws_connected is False


class TestWifiIp:
    def test_dotted_quad(self):
        r = WifiIpResponse.from_bytes(bytes.fromhex("00" "c0a80164"))
        assert r.ip_str == "192.168.1.100"

    def test_roundtrip(self):
        r = WifiIpResponse(1, bytes.fromhex("0a000005"))
        assert WifiIpResponse.from_bytes(r.to_bytes()) == r


class TestAwsKey:
    def test_utf8_tail(self):
        r = AwsKeyResponse.from_bytes(b"\x01ABCD-SERIAL")
        assert r.key == "ABCD-SERIAL"

    def test_roundtrip(self):
        r = AwsKeyResponse(1, "deadbeef0001")
        assert AwsKeyResponse.from_bytes(r.to_bytes()) == r


class TestVersionAndBaseInfo:
    def test_wifi_version_reads_byte2(self):
        assert WifiVersionResponse.from_bytes(bytes.fromhex("01000a")).version == 10

    def test_base_info(self):
        # [1]=battery, [2]=BLE version.
        r = BaseInfoResponse.from_bytes(bytes.fromhex("01" "55" "0a"))
        assert r.battery == 85
        assert r.ble_version == 10

    def test_roundtrips(self):
        v = WifiVersionResponse(1, 7)
        assert WifiVersionResponse.from_bytes(v.to_bytes()) == v
        b = BaseInfoResponse(1, 90, 8)
        assert BaseInfoResponse.from_bytes(b.to_bytes()) == b
