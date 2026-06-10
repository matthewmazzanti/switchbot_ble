import typing as ty

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

from .core import SwitchbotCoordinator, SwitchbotEntity


class BinarySensor[T](SwitchbotEntity[T], BinarySensorEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    def __init__(
        self,
        coordinator: SwitchbotCoordinator[T],
        unique_id: str,
        name: str,
        is_on_cb: ty.Callable[[T], bool],
        device_class: BinarySensorDeviceClass | None,
    ) -> None:
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_device_class = device_class
        self._is_on_cb = is_on_cb

    @property
    def is_on(self) -> bool | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        if (data := self.data) is not None:
            return self._is_on_cb(data)
        return None


class Sensor[T, V](SwitchbotEntity[T], SensorEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    def __init__(
        self,
        coordinator: SwitchbotCoordinator[T],
        unique_id: str,
        name: str,
        native_value_cb: ty.Callable[[T], V | None],
        device_class: SensorDeviceClass | None,
        native_unit_of_measurement: str | None,
        state_class: SensorStateClass | None,
        suggested_display_precision: int | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = native_unit_of_measurement
        self._attr_state_class = state_class
        self._attr_suggested_display_precision = suggested_display_precision
        self._native_value_cb = native_value_cb

    @property
    def native_value(self) -> V | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        if (data := self.data) is None:
            return None
        return self._native_value_cb(data)
