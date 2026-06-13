"""SwitchBot Water Leak Detector — coordinator + entities.

Status is advertisement-only: the device reports via manufacturer data
(``LeakManufacturerData``), with no status GATT and no scan-response, so that
proto dataclass is used directly as the coordinator state (cf. curtain3.py). The
service-data field only carries the device-type byte, which config_flow uses for
detection.

It has no device-specific BLE controls (``proto.leak`` documents that
verified-absent surface), but being Wi-Fi-connected it does accept the shared
clock-sync command over GATT — exposed here as the Sync Time button / the
``switchbot.sync_time`` action via ``async_sync_time``.

Entities: the primary signals — Leak (absolute wet/dry reading), Alert (the
device's problem state: reading matches the wet/dry mode's expectation), and
battery; a diagnostic group covering the rest (Audible — the buzzer, which can
be silenced so it's not a trustworthy problem signal; alarm mode/volume; the
rolling sequence; the alarm timing config; and the last-alert / last-test
timestamps); and the Sync Time button. Two modeled fields are deliberately *not*
surfaced:
``beat_state`` (the app parses the bit but never acts on it — meaning
unconfirmed) and ``alarm_num`` (raw 0-3 with no documented meaning). Both stay
in proto if we ever pin them down.
"""

from datetime import datetime, timezone

from homeassistant.components import bluetooth
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.util import dt as dt_util

from .. import generic_entity
from ..core import SwitchbotCoordinator
from ..proto.core import MANUFACTURER_ID
from ..proto.leak import LeakManufacturerData, UtcTime


def parse_advertisement(
    service_info: bluetooth.BluetoothServiceInfoBleak,
) -> LeakManufacturerData | None:
    """Parse the leak detector's manufacturer-data field, or None if absent or
    unparseable. Proto owns the length check."""
    mfr = service_info.manufacturer_data.get(MANUFACTURER_ID)
    if mfr is None:
        return None
    try:
        return LeakManufacturerData.parse(mfr)
    except ValueError:
        return None


def _as_utc(epoch: int) -> datetime | None:
    """A 4-byte UTC field as a tz-aware datetime, or None when unset (0 = the
    epoch, which the device sends before the event has ever happened)."""
    if epoch == 0:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


class LeakCoordinator(SwitchbotCoordinator[LeakManufacturerData]):
    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        name: str,
        adv: bluetooth.BluetoothServiceInfoBleak | None,
    ) -> None:
        super().__init__(
            hass=hass,
            address=address,
            device_name=name,
            device_type="leak",
            # Passive + non-connectable: status is advertisement-only, no GATT.
            mode=bluetooth.BluetoothScanningMode.PASSIVE,
            connectable=False,
            initial=parse_advertisement(adv) if adv else None,
        )

    def _parse(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> LeakManufacturerData | None:
        return parse_advertisement(service_info)

    # --- commands (SupportsSyncTime) ---

    async def async_sync_time(self) -> None:
        """Push HA's current UTC to the device clock.

        Backs the `switchbot.sync_time` action. A GATT write (the shared
        Wi-Fi-device clock-sync frame), so it connects despite this coordinator
        being advertisement-only/non-connectable — `async_send_command` resolves
        a connectable path itself.

        The payload is a thunk so its timestamp is taken at the write, not here:
        connecting can take seconds (plus retries), which would otherwise skew
        the clock we're trying to set."""
        await self.async_send_command(
            lambda: UtcTime(timestamp=int(dt_util.utcnow().timestamp())).to_bytes()
        )

    # --- device-major entity definition ---

    def create_platform_entities(self, platform: str) -> list[Entity]:
        match platform:
            case "button":
                return [
                    generic_entity.Button(
                        coordinator=self,
                        press_cb=self.async_sync_time,
                        unique_id=f"{self.address}:sync_time",
                        name=f"{self.device_name} Sync Time",
                        # A control the user operates → Configuration section.
                        entity_category=EntityCategory.CONFIG,
                    ),
                ]
            case "binary_sensor":
                return [
                    generic_entity.BinarySensor(
                        coordinator=self,
                        # The device's "there's a problem" signal: the reading
                        # matches the configured wet/dry mode's expectation. This
                        # cross-field condition lives here, not in proto (proto
                        # models single wire fields; combining them is our job).
                        # The primary problem indicator, distinct from `audible`
                        # (the buzzer) and `wet` (the raw reading).
                        is_on_cb=lambda data: data.wet == data.alarm_on_wet,
                        unique_id=f"{self.address}:alert",
                        name=f"{self.device_name} Alert",
                        device_class=BinarySensorDeviceClass.PROBLEM,
                    ),
                    generic_entity.BinarySensor(
                        coordinator=self,
                        # wet: the absolute moisture reading, independent of the
                        # wet/dry mode (cf. Alert, which factors the mode in).
                        is_on_cb=lambda data: data.wet,
                        unique_id=f"{self.address}:leak",
                        name=f"{self.device_name} Leak",
                        device_class=BinarySensorDeviceClass.MOISTURE,
                    ),
                    generic_entity.BinarySensor(
                        coordinator=self,
                        # audible: the buzzer is actively sounding. Diagnostic,
                        # not a primary alert: it depends on the volume setting,
                        # so a silenced device can be flooding with this off —
                        # Alert is the signal to trust for "there's a problem".
                        is_on_cb=lambda data: data.audible,
                        unique_id=f"{self.address}:audible",
                        name=f"{self.device_name} Audible",
                        device_class=BinarySensorDeviceClass.SOUND,
                        entity_category=EntityCategory.DIAGNOSTIC,
                    ),
                ]
            case "sensor":
                return [
                    generic_entity.Sensor(
                        coordinator=self,
                        native_value_cb=lambda data: data.battery,
                        unique_id=f"{self.address}:battery",
                        name=f"{self.device_name} Battery",
                        device_class=SensorDeviceClass.BATTERY,
                        native_unit_of_measurement=PERCENTAGE,
                        state_class=SensorStateClass.MEASUREMENT,
                    ),
                    generic_entity.Sensor(
                        coordinator=self,
                        # alarm_on_wet: True = inundate (alarm when wet), False
                        # = dehydrate (alarm when dry). Sets the Alert expectation.
                        native_value_cb=(
                            lambda data: "Wet" if data.alarm_on_wet else "Dry"
                        ),
                        unique_id=f"{self.address}:alarm_mode",
                        name=f"{self.device_name} Alarm Mode",
                        device_class=SensorDeviceClass.ENUM,
                        native_unit_of_measurement=None,
                        state_class=None,
                        options=["Wet", "Dry"],
                        entity_category=EntityCategory.DIAGNOSTIC,
                    ),
                    generic_entity.Sensor(
                        coordinator=self,
                        native_value_cb=lambda data: data.alarm_volume,
                        unique_id=f"{self.address}:alarm_volume",
                        name=f"{self.device_name} Alarm Volume",
                        # Raw 0-3 level; the app exposes no unit/scale.
                        device_class=None,
                        native_unit_of_measurement=None,
                        state_class=SensorStateClass.MEASUREMENT,
                        entity_category=EntityCategory.DIAGNOSTIC,
                    ),
                    generic_entity.Sensor(
                        coordinator=self,
                        native_value_cb=lambda data: data.alarm_duration,
                        unique_id=f"{self.address}:alarm_duration",
                        name=f"{self.device_name} Alarm Duration",
                        # Raw byte; the wire carries no unit (the app only logs
                        # it as `alarmLong`), so we don't assert seconds/minutes.
                        device_class=None,
                        native_unit_of_measurement=None,
                        state_class=None,
                        entity_category=EntityCategory.DIAGNOSTIC,
                    ),
                    generic_entity.Sensor(
                        coordinator=self,
                        native_value_cb=lambda data: data.alarm_interval,
                        unique_id=f"{self.address}:alarm_interval",
                        name=f"{self.device_name} Alarm Interval",
                        # Raw byte; unit unconfirmed (logged as `alarmInteval`).
                        device_class=None,
                        native_unit_of_measurement=None,
                        state_class=None,
                        entity_category=EntityCategory.DIAGNOSTIC,
                    ),
                    generic_entity.Sensor(
                        coordinator=self,
                        native_value_cb=lambda data: data.sequence,
                        unique_id=f"{self.address}:sequence",
                        name=f"{self.device_name} Advertisement Sequence",
                        # Rolling counter; no state_class (not a measurement).
                        device_class=None,
                        native_unit_of_measurement=None,
                        state_class=None,
                        entity_category=EntityCategory.DIAGNOSTIC,
                    ),
                    generic_entity.Sensor(
                        coordinator=self,
                        # state_change_time = when the wet/dry reading last
                        # flipped. The app reads this exact field as
                        # getLastAlertUTC() and uses it as the alarm message's
                        # `alarmTime` (WoWaterDetectorDevice / WoWaterDetectorParser),
                        # so "Last Alert" reflects its intent. unique_id stays
                        # `state_change_time` to keep the existing entity.
                        native_value_cb=lambda data: _as_utc(data.state_change_time),
                        unique_id=f"{self.address}:state_change_time",
                        name=f"{self.device_name} Last Alert",
                        device_class=SensorDeviceClass.TIMESTAMP,
                        native_unit_of_measurement=None,
                        state_class=None,
                        entity_category=EntityCategory.DIAGNOSTIC,
                    ),
                    generic_entity.Sensor(
                        coordinator=self,
                        native_value_cb=lambda data: _as_utc(data.test_utc),
                        unique_id=f"{self.address}:test_utc",
                        name=f"{self.device_name} Last Test",
                        device_class=SensorDeviceClass.TIMESTAMP,
                        native_unit_of_measurement=None,
                        state_class=None,
                        entity_category=EntityCategory.DIAGNOSTIC,
                    ),
                ]
            case _:
                return []
