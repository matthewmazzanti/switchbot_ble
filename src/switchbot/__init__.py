import logging

from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant

from .core import CONF_DEVICE_TYPE
from .devices import build_coordinator
from .platforms import SwitchbotConfigEntry

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "cover"]


async def async_setup_entry(hass: HomeAssistant, entry: SwitchbotConfigEntry) -> bool:
    address = str(entry.data[CONF_ADDRESS])
    name = str(entry.data[CONF_NAME])
    device_type = str(entry.data[CONF_DEVICE_TYPE])

    coordinator = build_coordinator(
        hass=hass,
        device_type=device_type,
        address=address,
        name=name,
        adv=bluetooth.async_last_service_info(hass, address),
    )
    entry.runtime_data = coordinator
    # Begin advertisement tracking; unsub on unload.
    entry.async_on_unload(coordinator.async_start())

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Loaded entry %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SwitchbotConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        _LOGGER.debug("Unloaded entry %s", entry.entry_id)
    return ok
