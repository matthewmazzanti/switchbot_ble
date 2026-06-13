"""SwitchBot BLE Wi-Fi onboarding commands (app -> device).

This is the *generic* Wi-Fi provisioning handshake shared by every SwitchBot
Wi-Fi device (hubs, plugs, strip lights, the water leak detector, ...). It is
not device-specific; the leak detector re-exports it for convenience.

Decompiled sources:
  - command bytes:      device/protocol/CmdGenerator.java (the WOCODE_REQ_* sub
                        codes + getSsidPacket/getWifiPwd/netSetupOver/...)
  - canonical sequence: device/impl/common/setting/WifiDeviceTools.java
                        (setRegion -> SSID -> password -> netSetupOver -> poll
                        getWifiStatus until connected, 120s timeout)

Every frame is `57 0F <sub> ...` (the extended-command space, via `core.ext`),
except the two clock/info reads which live in the `57 00 <sub>` common space.
None of these carry a device BLE key, so there is no CRC32 password header (that
`newPack` path is only used by keyed devices like locks/bots).
"""

import struct
from dataclasses import dataclass
from typing import ClassVar

from ..core import MAGIC, FixedCommand, build, ext, tail

# WOCODE_REQ_* sub-codes (the byte after `57 0F`), from CmdGenerator.
SUB_SET_SSID = 0x01  # WOCODE_REQ_SET_NET_SSID
SUB_SET_PASSWORD = 0x02  # WOCODE_REQ_SET_NET_PW
SUB_NET_SETUP_OVER = 0x03  # WOCODE_REQ_SET_NET_OVER
SUB_WIFI_STATUS = 0x04  # getWifiStatusCmd (also WOCODE_REQ_OTA slot)
SUB_START_WIFI_OTA = 0x0A  # WOCODE_REQ_START_WIFI_OTA
SUB_SET_REGION = 0x0C  # WOCODE_REQ_SET_REGION
SUB_READ_CURRENT_SSID = 0x0F  # WOCODE_REQ_READ_CURRENT_SSID
SUB_READ_SCAN_SSID = 0x10  # WOCODE_REQ_READ_SCAN_SSID
SUB_READ_SCAN_SSID_INFO = 0x11  # WOCODE_REQ_READ_SCAN_SSID_INFOR
SUB_SSID_SIGNAL = 0x12  # newGetSsidSignalREQPacket
SUB_WIFI_IP = 0x13  # getWifiIp

# `57 00 <sub>` common-command space (no device key).
CMD_COMMON = 0x00
SUB_COMMON_SET_TIME = 0x05  # WOCODE_COMMON_SET_TIME_CODE
SUB_COMMON_DEVICE_INFO = 0x03  # getWifiDeviceInfo
TIME_SC_CURRENT_TIME = 0x01  # WOCODE_TIME_SC_CURRENT_TIME

# SSID / password are split into <=11-byte chunks (getSsidPacket / getWifiPwd).
CHUNK_SIZE = 11


# ---------------------------------------------------------------------------
# Chunked setters (SSID + Wi-Fi password)
# ---------------------------------------------------------------------------
#
# Each chunk: `57 0F <sub> <total_len> <chunk_index> <up to 11 payload bytes>`.
# total_len is the full SSID/password length (one byte); chunks are emitted in
# order starting at index 0.


def _to_chunks(sub: int, data: bytes) -> list[bytes]:
    total = len(data) & 0xFF
    chunks = []
    for index, start in enumerate(range(0, len(data), CHUNK_SIZE)):
        chunks.append(ext(sub, total, index & 0xFF) + data[start : start + CHUNK_SIZE])
    return chunks


def _from_chunks(sub: int, packets: list[bytes]) -> bytes:
    header = ext(sub)
    data = bytearray()
    total: int | None = None
    for i, packet in enumerate(packets):
        body = tail(header, packet)
        if len(body) < 2:
            raise ValueError(f"chunk {i} too short: {packet.hex()}")
        if total is None:
            total = body[0]
        elif body[0] != total:
            raise ValueError(f"chunk {i} total_len {body[0]} != {total}")
        if body[1] != i:
            raise ValueError(f"chunk index {body[1]} out of order at position {i}")
        data += body[2:]
    if total is not None and (len(data) & 0xFF) != total:
        raise ValueError(f"reassembled {len(data)} bytes, header says {total}")
    return bytes(data)


@dataclass(frozen=True, slots=True)
class SetSsid:  # 57 0F 01 <total> <idx> <chunk..>
    """Target Wi-Fi network name, chunked across one or more frames."""

    ssid: bytes

    def to_packets(self) -> list[bytes]:
        return _to_chunks(SUB_SET_SSID, self.ssid)

    @classmethod
    def from_packets(cls, packets: list[bytes]) -> SetSsid:
        return cls(_from_chunks(SUB_SET_SSID, packets))


# The app encodes an empty (open-network) password as this exact sentinel frame
# rather than a zero-length chunk (getWifiPwd, length == 0 branch).
_EMPTY_PASSWORD = ext(SUB_SET_PASSWORD, 0x01, 0x00, 0x00)


@dataclass(frozen=True, slots=True)
class SetWifiPassword:  # 57 0F 02 <total> <idx> <chunk..>
    """Target Wi-Fi password, chunked. Empty password -> open-network sentinel."""

    password: bytes

    def to_packets(self) -> list[bytes]:
        if not self.password:
            return [_EMPTY_PASSWORD]
        return _to_chunks(SUB_SET_PASSWORD, self.password)

    @classmethod
    def from_packets(cls, packets: list[bytes]) -> SetWifiPassword:
        if list(packets) == [_EMPTY_PASSWORD]:
            return cls(b"")
        return cls(_from_chunks(SUB_SET_PASSWORD, packets))


# ---------------------------------------------------------------------------
# Single-frame parameter commands
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SetRegion:  # 57 0F 0C <region>
    _HEADER: ClassVar[bytes] = ext(SUB_SET_REGION)
    region: int

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.region & 0xFF)

    @classmethod
    def from_bytes(cls, data: bytes) -> SetRegion:
        p = tail(cls._HEADER, data)
        return cls(region=p[0])


@dataclass(frozen=True, slots=True)
class ScanSsid:  # 57 0F 10 <payload_cmd>
    _HEADER: ClassVar[bytes] = ext(SUB_READ_SCAN_SSID)
    payload_cmd: int

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.payload_cmd & 0xFF)

    @classmethod
    def from_bytes(cls, data: bytes) -> ScanSsid:
        p = tail(cls._HEADER, data)
        return cls(payload_cmd=p[0])


@dataclass(frozen=True, slots=True)
class ReadScanSsidInfo:  # 57 0F 11 <index> <section>
    _HEADER: ClassVar[bytes] = ext(SUB_READ_SCAN_SSID_INFO)
    index: int
    section: int

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.index & 0xFF, self.section & 0xFF)

    @classmethod
    def from_bytes(cls, data: bytes) -> ReadScanSsidInfo:
        p = tail(cls._HEADER, data)
        return cls(index=p[0], section=p[1])


@dataclass(frozen=True, slots=True)
class ReadSsidSignal:  # 57 0F 12 <index>
    _HEADER: ClassVar[bytes] = ext(SUB_SSID_SIGNAL)
    index: int

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.index & 0xFF)

    @classmethod
    def from_bytes(cls, data: bytes) -> ReadSsidSignal:
        p = tail(cls._HEADER, data)
        return cls(index=p[0])


@dataclass(frozen=True, slots=True)
class ReadCurrentSsid:  # 57 0F 0F <seq>
    _HEADER: ClassVar[bytes] = ext(SUB_READ_CURRENT_SSID)
    seq: int

    def to_bytes(self) -> bytes:
        return build(self._HEADER, self.seq & 0xFF)

    @classmethod
    def from_bytes(cls, data: bytes) -> ReadCurrentSsid:
        p = tail(cls._HEADER, data)
        return cls(seq=p[0])


@dataclass(frozen=True, slots=True)
class UtcTime:  # 57 00 05 01 <8-byte big-endian unix seconds>
    """Sync the device clock (utcTime: ByteBuffer.putLong -> 8 bytes big-endian)."""

    _HEADER: ClassVar[bytes] = build(
        MAGIC, CMD_COMMON, SUB_COMMON_SET_TIME, TIME_SC_CURRENT_TIME
    )
    timestamp: int  # unix seconds

    def to_bytes(self) -> bytes:
        return build(self._HEADER, struct.pack(">Q", self.timestamp))

    @classmethod
    def from_bytes(cls, data: bytes) -> UtcTime:
        return cls(timestamp=struct.unpack(">Q", tail(cls._HEADER, data)[:8])[0])


# ---------------------------------------------------------------------------
# Fixed (parameterless) commands
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class NetSetupOver(FixedCommand):  # 57 0F 03
    _WIRE: ClassVar[bytes] = ext(SUB_NET_SETUP_OVER)


@dataclass(frozen=True, slots=True)
class GetWifiStatus(FixedCommand):  # 57 0F 04
    _WIRE: ClassVar[bytes] = ext(SUB_WIFI_STATUS)


@dataclass(frozen=True, slots=True)
class GetWifiIp(FixedCommand):  # 57 0F 13 02
    _WIRE: ClassVar[bytes] = ext(SUB_WIFI_IP, 0x02)


@dataclass(frozen=True, slots=True)
class GetDeviceInfo(FixedCommand):  # 57 00 03
    _WIRE: ClassVar[bytes] = build(MAGIC, CMD_COMMON, SUB_COMMON_DEVICE_INFO)
