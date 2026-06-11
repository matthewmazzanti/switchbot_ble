import dataclasses as dc
import typing as ty

from homeassistant.components import bluetooth
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.cover import (
    ATTR_TILT_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .. import generic_entity
from ..core import SwitchbotCoordinator, SwitchbotEntity
from ..proto.blind_tilt import (
    MODERN_FW,
    BlindTiltManufacturerData,
    BlindTiltServiceData,
    SetPosition,
    Stop,
)
from ..proto.core import MANUFACTURER_ID, SWITCHBOT_SERVICE


@dc.dataclass(frozen=True, slots=True)
class BlindTiltState:
    """Flattened device state combined from both advertisement fields. Only
    constructed once both fields have been seen, so nothing here is optional."""

    battery: int
    calibrated: bool
    moving: bool
    position: int
    stuck: bool
    direction: int
    direction_set: bool
    link_length: int
    connect_allow: bool

    @classmethod
    def combine(
        cls, mfr: BlindTiltManufacturerData, svc: BlindTiltServiceData
    ) -> BlindTiltState:
        return cls(
            battery=svc.battery,
            calibrated=mfr.calibrated,
            moving=mfr.moving,
            position=mfr.position,
            stuck=mfr.stuck,
            direction=mfr.direction,
            direction_set=mfr.direction_set,
            link_length=mfr.link_length,
            connect_allow=mfr.connect_allow,
        )


class BlindTiltCoordinator(SwitchbotCoordinator[BlindTiltState]):
    # Last-seen of each advertisement field; they arrive in separate frames.
    _last_mfr: BlindTiltManufacturerData | None
    _last_svc: BlindTiltServiceData | None

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        name: str,
        adv: bluetooth.BluetoothServiceInfoBleak | None,
    ) -> None:
        self._last_mfr = None
        self._last_svc = None
        super().__init__(
            hass=hass,
            address=address,
            device_name=name,
            device_type="blind_tilt",
            # Active scan to pick up scan-response data; connectable because we
            # issue position commands over GATT.
            mode=bluetooth.BluetoothScanningMode.ACTIVE,
            connectable=True,
            initial=self._parse(adv) if adv else None,
        )

    def _parse(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> BlindTiltState | None:
        """Parse whichever fields this frame carries, retain the last-seen of
        each, and return the combined state. None until both fields have each
        been seen at least once. Unparseable (short) fields are skipped; proto
        owns the length checks."""
        if (mfr := service_info.manufacturer_data.get(MANUFACTURER_ID)) is not None:
            try:
                self._last_mfr = BlindTiltManufacturerData.parse(mfr)
            except ValueError:
                pass
        if (svc := service_info.service_data.get(SWITCHBOT_SERVICE)) is not None:
            try:
                self._last_svc = BlindTiltServiceData.parse(svc)
            except ValueError:
                pass
        if self._last_mfr is None or self._last_svc is None:
            return None
        return BlindTiltState.combine(self._last_mfr, self._last_svc)

    # --- commands (connect/write/await exchange lives in core.async_command) ---

    async def async_set_position(self, position: int) -> None:
        # We don't read the device firmware, so assume modern. Reading the real
        # fw (e.g. a config-flow interview) is a deferred stretch goal.
        await self.async_send_command(
            SetPosition(position).to_bytes(fw_version=MODERN_FW)
        )

    async def async_stop(self) -> None:
        await self.async_send_command(Stop().to_bytes())

    async def async_close_down(self) -> None:
        await self.async_set_position(0)

    async def async_open(self) -> None:
        await self.async_set_position(50)

    async def async_close_up(self) -> None:
        await self.async_set_position(100)

    # --- device-major entity definition ---

    def create_platform_entities(self, platform: str) -> list[Entity]:
        match platform:
            case "binary_sensor":
                return [
                    generic_entity.BinarySensor(
                        coordinator=self,
                        is_on_cb=lambda data: data.calibrated,
                        unique_id=f"{self.address}:calibrated",
                        name=f"{self.device_name} Calibrated",
                        device_class=None,
                    ),
                    generic_entity.BinarySensor(
                        coordinator=self,
                        is_on_cb=lambda data: data.moving,
                        unique_id=f"{self.address}:moving",
                        name=f"{self.device_name} In Motion",
                        device_class=BinarySensorDeviceClass.MOVING,
                    ),
                    generic_entity.BinarySensor(
                        coordinator=self,
                        is_on_cb=lambda data: data.stuck,
                        unique_id=f"{self.address}:stuck",
                        name=f"{self.device_name} Stuck",
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
            case "cover":
                return [BlindTiltCover(self)]
            case _:
                return []


class BlindTiltCover(SwitchbotEntity[BlindTiltState], CoverEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Cover entity for a SwitchBot Blind Tilt; forwards commands to the device."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_TILT_POSITION
    )

    def __init__(self, coordinator: BlindTiltCoordinator) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.address}:cover"
        self._attr_name = f"{coordinator.device_name} Cover"

    @property
    def current_cover_tilt_position(self) -> int | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        data = self.data
        return data.position if data is not None else None

    @property
    def is_closed(self) -> bool | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        tilt = self.current_cover_tilt_position
        # "Closed" here means fully down at 0%.
        return tilt == 0 if tilt is not None else None

    async def async_open_cover(self, **kwargs: ty.Any) -> None:
        await self._coordinator.async_open()

    async def async_close_cover(self, **kwargs: ty.Any) -> None:
        await self._coordinator.async_close_down()

    async def async_stop_cover(self, **kwargs: ty.Any) -> None:
        await self._coordinator.async_stop()

    async def async_set_cover_tilt_position(self, **kwargs: ty.Any) -> None:
        pos = kwargs.get(ATTR_TILT_POSITION)
        if pos is None:
            return
        await self._coordinator.async_set_position(int(pos))
