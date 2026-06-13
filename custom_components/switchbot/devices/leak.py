"""SwitchBot Water Leak Detector — coordinator + entities.

A passive, advertisement-only sensor: no GATT commands, no scan-response. All
surfaced state lives in the manufacturer-data field (``LeakManufacturerData``),
so that proto dataclass is used directly as the coordinator state (cf.
curtain3.py). The service-data field only carries the device-type byte, which
config_flow uses for detection.

Scope (per add-hass): the alarm signals + battery. Deferred fields
(alarm mode/volume/interval, beat state, timestamps, sequence) stay in proto and
are cheap to surface later.
"""

from homeassistant.components import bluetooth
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .. import generic_entity
from ..core import SwitchbotCoordinator
from ..proto.core import MANUFACTURER_ID
from ..proto.leak import LeakManufacturerData


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

    # --- device-major entity definition ---

    def create_platform_entities(self, platform: str) -> list[Entity]:
        match platform:
            case "binary_sensor":
                return [
                    generic_entity.BinarySensor(
                        coordinator=self,
                        # current_state: 0 = dry, 1 = wet (water present).
                        is_on_cb=lambda data: data.current_state == 1,
                        unique_id=f"{self.address}:leak",
                        name=f"{self.device_name} Leak",
                        device_class=BinarySensorDeviceClass.MOISTURE,
                    ),
                    generic_entity.BinarySensor(
                        coordinator=self,
                        # alarming: the device is actively in alarm.
                        is_on_cb=lambda data: data.alarming,
                        unique_id=f"{self.address}:alarm",
                        name=f"{self.device_name} Alarm",
                        device_class=BinarySensorDeviceClass.PROBLEM,
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
                ]
            case _:
                return []
