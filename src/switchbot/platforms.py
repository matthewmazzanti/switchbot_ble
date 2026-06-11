import logging
from typing import Protocol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


class SwitchbotDevice(Protocol):
    """The per-config-entry runtime object stored on `entry.runtime_data` — a
    standalone device coordinator or a multi-device group. It owns the entry's
    BLE subscription lifecycle and authors its entities. Decoupled from
    `SwitchbotCoordinator` so a group (which is not a coordinator) and a member
    coordinator (which authors no entities) each fit only the role they play.
    """

    address: str

    def async_start(self) -> CALLBACK_TYPE: ...

    def create_platform_entities(self, platform: str) -> list[Entity]: ...


# The device object is stored on the config entry itself; no global registry.
type SwitchbotConfigEntry = ConfigEntry[SwitchbotDevice]


def platform_setup_entry_factory(platform: str):
    async def _async_setup_entry(
        hass: HomeAssistant,
        entry: SwitchbotConfigEntry,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        coordinator = entry.runtime_data
        async_add_entities(coordinator.create_platform_entities(platform))
        _LOGGER.debug("Loaded %s entities for %s", platform, coordinator.address)

    return _async_setup_entry
