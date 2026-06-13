"""Water Leak Detector BLE advertisement data parsing.

Per WoWaterDetectorParser: the device type / pairing flag lives in the service
data (UUID 0xFD3D, byte 0); every other field lives in the manufacturer data
(company id 0x0969 / 2409, MAC at bytes 0-5). Each BLE field is parsed
independently here; combining/retaining them is the consumer's job.

The Water Leak Detector is a passive sensor — it has no BLE commands and sends
no notifications, so there is no commands/responses module.

  Service data (UUID 0xFD3D) -> LeakServiceData:
    byte 0  device type; 0x26 normal / 0x06 pairing ("add") mode

  Manufacturer data (company id 0x0969 / 2409) -> LeakManufacturerData;
  bytes 0-5 are the MAC, fields start at byte 6:
    byte 6     sequence number
    byte 7     battery (bits 6:0)
    byte 8     alarm_mode (bit 7), current_state (bit 6), alarming (bit 5),
               alarm_volume (bits 4:3), beat_state (bit 2), alarm_num (bits 1:0)
    bytes 9-12  state_change_time (big-endian UTC, uint32)
    byte 13    alarm_duration
    byte 14    alarm_interval
    bytes 15-18 test_utc (big-endian UTC, uint32)
"""

import struct
from dataclasses import dataclass

from ..core import PAIRING_BIT, is_pairing
from ..device_type import DeviceType

# On the wire the type byte is 0x26 in normal operation and 0x06 in pairing mode.
DEVICE_TYPE = DeviceType.LEAK


@dataclass(frozen=True, slots=True)
class LeakServiceData:
    """Service-data broadcast (UUID 0xFD3D); only byte 0 is meaningful."""

    pair_mode: bool

    def to_bytes(self) -> bytes:
        # byte 0: device type; pairing bit set in normal operation
        return bytes([DEVICE_TYPE | (0 if self.pair_mode else PAIRING_BIT)])

    @classmethod
    def parse(cls, data: bytes) -> LeakServiceData:
        if len(data) < 1:
            raise ValueError(f"service data needs >= 1 byte, got {len(data)}")
        return cls(pair_mode=is_pairing(data[0]))


@dataclass(frozen=True, slots=True)
class LeakManufacturerData:
    """Manufacturer data (company id 0x0969); MAC at bytes 0-5, fields at 6+.

    The app's parser gates on ``length >= 14`` but reads through byte 18, so a
    full frame is >= 19 bytes; we require that to decode every modeled field.
    """

    sequence: int  # byte 6, rolling advertisement counter
    battery: int  # 0-100
    alarm_mode: int  # 0=dehydrate (dry alarm), 1=inundate (wet alarm)
    current_state: int  # 0=dry, 1=wet
    alarming: bool  # buzzer/alert currently active (index5608_wd_is_alarm)
    alarm_volume: int  # 0-3
    # index5604_wd_beat_state. The app parses this bit and only logs it: it is
    # not read by WoWaterDetectorDevice, not in refreshPros(), and absent from
    # MqttWaterDetectorStatus. Name suggests a periodic "heartbeat" chirp/alive
    # signal (distinct from the test-button activity tracked by test_utc), but
    # the decomp never acts on it, so the meaning is unconfirmed.
    beat_state: bool
    alarm_num: int  # 0-3 (index5611_wd_alarm_num)
    state_change_time: int  # 4-byte big-endian UTC (index5605)
    alarm_duration: int  # index5606_wd_alarm_time
    alarm_interval: int  # index5607_wd_alarm_interval_time
    test_utc: int  # 4-byte big-endian UTC (index5610_wd_test_UTC)

    @property
    def in_alert(self) -> bool:
        # Per WoWaterDetectorDevice.isInAlert: the device is in alert when the
        # current measured state matches the configured alarm mode (inundate +
        # wet, or dehydrate + dry).
        return self.alarm_mode == self.current_state

    def to_bytes(self) -> bytes:
        # fmt: off
        b8 = (
            ((self.alarm_mode & 0x01) << 7)
            | ((self.current_state & 0x01) << 6)
            | (self.alarming << 5)
            | ((self.alarm_volume & 0x03) << 3)
            | (self.beat_state << 2)
            | (self.alarm_num & 0x03)
        )
        return (
            bytes([
                0, 0, 0, 0, 0, 0,         # 0-5: MAC (not modeled)
                self.sequence & 0xFF,     # 6: sequence
                self.battery & 0x7F,      # 7: battery
                b8,                       # 8: status/alarm flags
            ])
            + struct.pack(">I", self.state_change_time)  # 9-12
            + bytes([
                self.alarm_duration & 0xFF,   # 13
                self.alarm_interval & 0xFF,   # 14
            ])
            + struct.pack(">I", self.test_utc)           # 15-18
        )
        # fmt: on

    @classmethod
    def parse(cls, data: bytes) -> LeakManufacturerData:
        if len(data) < 19:
            raise ValueError(f"manufacturer data needs >= 19 bytes, got {len(data)}")
        b8 = data[8]
        return cls(
            sequence=data[6],
            battery=data[7] & 0x7F,
            alarm_mode=(b8 & 0x80) >> 7,
            current_state=(b8 & 0x40) >> 6,
            alarming=bool(b8 & 0x20),
            alarm_volume=(b8 & 0x18) >> 3,
            beat_state=bool(b8 & 0x04),
            alarm_num=b8 & 0x03,
            state_change_time=struct.unpack(">I", data[9:13])[0],
            alarm_duration=data[13],
            alarm_interval=data[14],
            test_utc=struct.unpack(">I", data[15:19])[0],
        )
