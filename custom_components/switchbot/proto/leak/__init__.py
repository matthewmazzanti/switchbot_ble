"""SwitchBot Water Leak Detector BLE protocol.

Status is advertisement-only (no runtime commands/notifications). The device is
Wi-Fi-connected, so onboarding uses the shared BLE Wi-Fi provisioning handshake;
that lives in `proto.wifi_setup` and is re-exported here for convenience.

Control surface verified ABSENT — there is no device-specific BLE command for
this model (no alarm mode/volume/invert setter, etc.). The device-specific
settings (alarm_mode, alarm_volume, alarm_duration/interval) are cloud/MQTT
properties, not BLE-writable. Triple-checked (app v9.11.15.13 + pySwitchbot):
  - decomp: `WoWaterDetectorDevice.getActions()` returns emptyList(); no
    `WaterDetectorCmd.java`; alarm fields are only ever *read* (parser + the
    `MqttWaterDetectorStatus` cloud model), never encoded; `CmdGenerator`'s
    generic SET_SETTING/GET_SETTING opcodes are dead (no builder emits them).
  - pySwitchbot: `adv_parsers/leak.py` is parse-only and there is NO
    `devices/leak.py` command class (contrast `devices/meter.py`, which exists
    because the meter *does* have a GATT surface).
The only BLE writes this device accepts are the shared Wi-Fi/maintenance
commands (clock sync, onboarding) in `proto.wifi_setup`. Don't re-derive a
control command here without new evidence (e.g. a live BLE capture) — guessing a
frame is exactly what `proto/CLAUDE.md` forbids.
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
