import abc
import logging

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DOMAIN = "switchbot"

CONF_DEVICE_TYPE = "device_type"


def normalize_mac(mac: str) -> str:
    return mac.strip().upper()


class SwitchbotCoordinator[T](PassiveBluetoothDataUpdateCoordinator, abc.ABC):
    """Per-device object: owns the BLE subscription, parsed state, and the
    device's command/connection path.

    This is the single runtime representation of one physical device. HA's
    light passive-bluetooth coordinator gives it advertisement subscription,
    availability tracking, and listener fan-out; subclasses add the parse, the
    commands, and the device-major entity definition.
    """

    data: T | None

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        device_name: str,
        device_type: str,
        mode: bluetooth.BluetoothScanningMode,
        connectable: bool,
        initial: T | None,
    ) -> None:
        super().__init__(hass, _LOGGER, normalize_mac(address), mode, connectable)
        self.device_name = device_name
        self.device_type = device_type
        self.data = initial

    @property
    def device_info(self) -> device_registry.DeviceInfo:
        # Entities attach to this; HA creates the device registry entry.
        return device_registry.DeviceInfo(
            identifiers={(DOMAIN, self.address)},
            connections={(device_registry.CONNECTION_BLUETOOTH, self.address)},
            name=self.device_name,
            manufacturer="SwitchBot",
        )

    @abc.abstractmethod
    def _parse(self, service_info: bluetooth.BluetoothServiceInfoBleak) -> T | None:
        """Parse an advertisement into device state (or None to ignore it)."""
        raise NotImplementedError

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        data = self._parse(service_info)
        if data is not None:
            self.data = data
        # super() flips _available True and fans out to entity listeners.
        super()._async_handle_bluetooth_event(service_info, change)

    @abc.abstractmethod
    def create_platform_entities(self, platform: str) -> list[Entity]:
        """Device-major entity definition: the one place that says what this
        device exposes, per platform. Thin platform files forward here."""
        raise NotImplementedError


class SwitchbotEntity[T](PassiveBluetoothCoordinatorEntity[SwitchbotCoordinator[T]]):
    """Base entity: a thin view over the coordinator's typed state.

    Subscription and availability are handled by the framework
    (PassiveBluetoothCoordinatorEntity); we only re-render on update.
    """

    _attr_should_poll = False

    @property
    def data(self) -> T | None:
        return self.coordinator.data

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()
