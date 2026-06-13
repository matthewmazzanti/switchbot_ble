import logging

from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant

from .core import CONF_DEVICE_TYPE
from .devices import build_device
from .platforms import SwitchbotConfigEntry

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "cover"]


async def async_setup_entry(hass: HomeAssistant, entry: SwitchbotConfigEntry) -> bool:
    address = str(entry.data[CONF_ADDRESS])
    # build_device dispatches on DeviceType: Curtain 3 interviews the chain
    # (raising ConfigEntryNotReady on BLE failure → HA retries); others construct
    # directly.
    device = await build_device(
        hass,
        device_type=int(entry.data[CONF_DEVICE_TYPE]),
        address=address,
        name=str(entry.data[CONF_NAME]),
        adv=bluetooth.async_last_service_info(hass, address),
    )

    entry.runtime_data = device
    # Begin advertisement tracking; unsub on unload.
    entry.async_on_unload(device.async_start())

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Loaded entry %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SwitchbotConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        _LOGGER.debug("Unloaded entry %s", entry.entry_id)
    return ok
