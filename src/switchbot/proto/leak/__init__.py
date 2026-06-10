"""SwitchBot Water Leak Detector BLE protocol.

Status is advertisement-only (no runtime commands/notifications). The device is
Wi-Fi-connected, so onboarding uses the shared BLE Wi-Fi provisioning handshake;
that lives in `proto.wifi_setup` and is re-exported here for convenience.
"""

from .. import wifi_setup
from ..wifi_setup import (
    AwsKeyResponse,
    AwsStatus,
    BaseInfoResponse,
    GetDeviceInfo,
    GetWifiIp,
    GetWifiStatus,
    NetSetupOver,
    ReadCurrentSsid,
    ReadScanSsidInfo,
    ReadSsidSignal,
    ReplyStatus,
    ScanSsid,
    SetRegion,
    SetSsid,
    SetWifiPassword,
    StatusResponse,
    UtcTime,
    WifiIpResponse,
    WifiStatusResponse,
    WifiVersionResponse,
    is_success,
)
from .advertisement import DEVICE_TYPE, LeakManufacturerData, LeakServiceData

__all__ = [
    "DEVICE_TYPE",
    "LeakManufacturerData",
    "LeakServiceData",
    # Shared Wi-Fi onboarding (re-exported from proto.wifi_setup)
    "wifi_setup",
    "AwsKeyResponse",
    "AwsStatus",
    "BaseInfoResponse",
    "GetDeviceInfo",
    "GetWifiIp",
    "GetWifiStatus",
    "NetSetupOver",
    "ReadCurrentSsid",
    "ReadScanSsidInfo",
    "ReadSsidSignal",
    "ReplyStatus",
    "ScanSsid",
    "SetRegion",
    "SetSsid",
    "SetWifiPassword",
    "StatusResponse",
    "UtcTime",
    "WifiIpResponse",
    "WifiStatusResponse",
    "WifiVersionResponse",
    "is_success",
]
