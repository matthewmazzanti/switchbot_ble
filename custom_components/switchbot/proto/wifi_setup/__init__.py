"""SwitchBot BLE Wi-Fi onboarding protocol.

The generic provisioning handshake (set region -> SSID -> password ->
netSetupOver -> poll status) shared by all SwitchBot Wi-Fi devices. Pure wire
encoding only; sequencing + GATT I/O belong to the coordinator.
"""

from .commands import (
    CHUNK_SIZE,
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
from .responses import (
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

__all__ = [
    "CHUNK_SIZE",
    "GetDeviceInfo",
    "GetWifiIp",
    "GetWifiStatus",
    "NetSetupOver",
    "ReadCurrentSsid",
    "ReadScanSsidInfo",
    "ReadSsidSignal",
    "ScanSsid",
    "SetRegion",
    "SetSsid",
    "SetWifiPassword",
    "UtcTime",
    "AwsKeyResponse",
    "AwsStatus",
    "BaseInfoResponse",
    "ReplyStatus",
    "StatusResponse",
    "WifiIpResponse",
    "WifiStatusResponse",
    "WifiVersionResponse",
    "is_success",
]
