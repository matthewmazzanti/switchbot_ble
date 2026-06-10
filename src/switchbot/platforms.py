import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .core import SwitchbotCoordinator

_LOGGER = logging.getLogger(__name__)

# The coordinator (per-device object) is stored on the config entry itself;
# no global registry needed.
type SwitchbotConfigEntry = ConfigEntry[SwitchbotCoordinator]


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
