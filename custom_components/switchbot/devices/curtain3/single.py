import typing as ty

from homeassistant.components import bluetooth
from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from ... import generic_entity
from ...core import SwitchbotCoordinator, SwitchbotEntity
from ...proto.core import SWITCHBOT_SERVICE
from ...proto.curtain3 import Curtain3ServiceData, CurtainIndex, SetPercentage, Stop


def parse_advertisement(
    service_info: bluetooth.BluetoothServiceInfoBleak,
) -> Curtain3ServiceData | None:
    """Parse the Curtain 3 service-data broadcast, or None if absent/unparseable.

    Only the service-data core is surfaced; the manufacturer-data extras
    (Curtain3ManufacturerData) are modeled in proto but not used here. Proto
    owns the length check.
    """
    svc = service_info.service_data.get(SWITCHBOT_SERVICE)
    if svc is None:
        return None
    try:
        return Curtain3ServiceData.parse(svc)
    except ValueError:
        return None


class Curtain3Coordinator(SwitchbotCoordinator[Curtain3ServiceData]):
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
            device_type="curtain3",
            # Active scan + connectable: we issue position commands over GATT.
            mode=bluetooth.BluetoothScanningMode.ACTIVE,
            connectable=True,
            initial=parse_advertisement(adv) if adv else None,
        )

    def _parse(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> Curtain3ServiceData | None:
        return parse_advertisement(service_info)

    # --- commands (connect/write/await exchange lives in core.async_request) ---

    async def async_set_curtain_position(self, position: int) -> None:
        """`position` is the SwitchBot position (0 = open, 100 = closed)."""
        await self.async_send_command(
            SetPercentage(index=CurtainIndex.PRIMARY, position=position).to_bytes()
        )

    async def async_open(self) -> None:
        await self.async_set_curtain_position(0)

    async def async_close(self) -> None:
        await self.async_set_curtain_position(100)

    async def async_stop(self) -> None:
        await self.async_send_command(Stop().to_bytes())

    # --- device-major entity definition ---

    def create_platform_entities(self, platform: str) -> list[Entity]:
        match platform:
            case "cover":
                return [Curtain3Cover(self)]
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
            case "binary_sensor":
                return [
                    generic_entity.BinarySensor(
                        coordinator=self,
                        is_on_cb=lambda data: data.calibrated,
                        unique_id=f"{self.address}:calibrated",
                        name=f"{self.device_name} Calibrated",
                        device_class=None,
                    ),
                ]
            case _:
                return []


class Curtain3Cover(SwitchbotEntity[Curtain3ServiceData], CoverEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Cover for a SwitchBot Curtain 3.

    SwitchBot uses position 0 = open .. 100 = closed (the app's open button sends
    0, close sends 100); Home Assistant covers use 0 = closed .. 100 = open, so
    we invert. The official HA switchbot integration matches (it inverts inside
    PySwitchbot and uses the value directly).
    """

    _attr_device_class = CoverDeviceClass.CURTAIN
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, coordinator: Curtain3Coordinator) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.address}:cover"
        self._attr_name = f"{coordinator.device_name} Cover"

    @property
    def current_cover_position(self) -> int | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        data = self.data
        return 100 - data.position if data is not None else None

    @property
    def is_closed(self) -> bool | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        pos = self.current_cover_position
        return pos == 0 if pos is not None else None

    async def async_open_cover(self, **kwargs: ty.Any) -> None:
        await self._coordinator.async_open()

    async def async_close_cover(self, **kwargs: ty.Any) -> None:
        await self._coordinator.async_close()

    async def async_stop_cover(self, **kwargs: ty.Any) -> None:
        await self._coordinator.async_stop()

    async def async_set_cover_position(self, **kwargs: ty.Any) -> None:
        ha_pos = kwargs.get(ATTR_POSITION)
        if ha_pos is None:
            return
        # invert HA position (0=closed) back to SwitchBot's 0=open convention
        await self._coordinator.async_set_curtain_position(100 - int(ha_pos))
