"""SwitchBot BLE Wi-Fi onboarding responses (device -> app).

Parsed from notify/read replies; `reply[0]` is the status byte. Layouts from
device/protocol/ble/BleMsgParser.java (parseWifiStatus / parseWifiIP /
parseAwsKey / parseWifiVersion / parseBaseInfo) and its WOCODE_RESP_* constants.
"""

from dataclasses import dataclass
from enum import IntEnum


class ReplyStatus(IntEnum):
    """`reply[0]` status code (WOCODE_RESP_STATUS_*)."""

    NULL = 0
    OK = 1
    ERROR = 2
    BUSY = 3
    UNSUPPORT = 5
    BTL = 6  # bootloader; checkReplySuccess treats this as success too
    ENCRYPTED = 7
    UNENCRYPT = 8
    PASSWORD_INVALID = 9


class AwsStatus(IntEnum):
    """IoT/AWS connection status (byte 2 of the Wi-Fi status reply)."""

    IDLE = 48
    OK = 49
    CONNECT_FAIL = 50
    PSUB_FAIL = 51
    SEND_FAIL = 52


def is_success(status: int) -> bool:
    """Per BleMsgParser.checkReplySuccess: OK (1) or BTL (6)."""
    return status in (ReplyStatus.OK, ReplyStatus.BTL)


@dataclass(frozen=True, slots=True)
class StatusResponse:
    """1-byte generic ack (e.g. set-region / set-SSID / netSetupOver)."""

    status: int

    @property
    def ok(self) -> bool:
        return is_success(self.status)

    def to_bytes(self) -> bytes:
        return bytes([self.status])

    @classmethod
    def from_bytes(cls, data: bytes) -> StatusResponse:
        if len(data) < 1:
            raise ValueError("Need at least 1 byte")
        return cls(status=data[0])


@dataclass(frozen=True, slots=True)
class WifiStatusResponse:
    """getWifiStatus reply: net status (byte 1), IoT status (byte 2), MAC (3-8)."""

    status: int
    net_status: int  # WO_NET_STATUS (reply[1])
    aws_status: int  # WO_HUB_MINI_AWS_CONNECT_STATUS (reply[2])
    mac: bytes  # 6-byte Wi-Fi MAC (reply[3:9])

    @property
    def aws_connected(self) -> bool:
        return self.aws_status == AwsStatus.OK

    @property
    def mac_hex(self) -> str:
        return ":".join(f"{b:02x}" for b in self.mac)

    def to_bytes(self) -> bytes:
        return bytes([self.status, self.net_status, self.aws_status]) + self.mac

    @classmethod
    def from_bytes(cls, data: bytes) -> WifiStatusResponse:
        if len(data) < 9:
            raise ValueError(f"Need 9 bytes, got {len(data)}")
        return cls(
            status=data[0],
            net_status=data[1],
            aws_status=data[2],
            mac=bytes(data[3:9]),
        )


@dataclass(frozen=True, slots=True)
class WifiIpResponse:
    """getWifiIp reply: 4-byte IPv4 at reply[1:5]."""

    status: int
    ip: bytes  # 4 bytes

    @property
    def ip_str(self) -> str:
        return ".".join(str(b) for b in self.ip)

    def to_bytes(self) -> bytes:
        return bytes([self.status]) + self.ip

    @classmethod
    def from_bytes(cls, data: bytes) -> WifiIpResponse:
        if len(data) < 5:
            raise ValueError(f"Need 5 bytes, got {len(data)}")
        return cls(status=data[0], ip=bytes(data[1:5]))


@dataclass(frozen=True, slots=True)
class AwsKeyResponse:
    """getAwsKey reply: UTF-8 key string at reply[1:] (the device serial)."""

    status: int
    key: str

    def to_bytes(self) -> bytes:
        return bytes([self.status]) + self.key.encode("utf-8")

    @classmethod
    def from_bytes(cls, data: bytes) -> AwsKeyResponse:
        if len(data) < 1:
            raise ValueError("Need at least 1 byte")
        return cls(status=data[0], key=bytes(data[1:]).decode("utf-8"))


@dataclass(frozen=True, slots=True)
class WifiVersionResponse:
    """parseWifiVersion: BLE/Wi-Fi firmware version at reply[2]."""

    status: int
    version: int

    def to_bytes(self) -> bytes:
        # byte 1 is unused by the parser; pad with 0.
        return bytes([self.status, 0, self.version])

    @classmethod
    def from_bytes(cls, data: bytes) -> WifiVersionResponse:
        if len(data) < 3:
            raise ValueError(f"Need 3 bytes, got {len(data)}")
        return cls(status=data[0], version=data[2])


@dataclass(frozen=True, slots=True)
class BaseInfoResponse:
    """parseBaseInfo (non-hub path): battery (reply[1]) + BLE version (reply[2]).

    Hub-class devices carry extra bytes (Wi-Fi version at 11, region at 12); the
    leak detector and other leaf devices only populate these two.
    """

    status: int
    battery: int
    ble_version: int

    def to_bytes(self) -> bytes:
        return bytes([self.status, self.battery, self.ble_version])

    @classmethod
    def from_bytes(cls, data: bytes) -> BaseInfoResponse:
        if len(data) < 3:
            raise ValueError(f"Need 3 bytes, got {len(data)}")
        return cls(status=data[0], battery=data[1], ble_version=data[2])
