import logging

from bleak.exc import BleakError
from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.service import async_extract_config_entry_ids
from homeassistant.helpers.typing import ConfigType

from .core import CONF_DEVICE_TYPE, DOMAIN, CommandError
from .devices import build_device
from .platforms import SupportsSyncTime, SwitchbotConfigEntry

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "button", "cover"]

SERVICE_SYNC_TIME = "sync_time"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register integration-wide actions (once per HA start, before any entry).

    `sync_time` is device-major: it routes a target (device/area/entity) to the
    `SwitchbotDevice` on each referenced config entry and calls its command
    method, so platform files stay thin forwarders."""

    async def _handle_sync_time(call: ServiceCall) -> None:
        entry_ids = await async_extract_config_entry_ids(call)
        devices: list[SupportsSyncTime] = []
        for entry_id in entry_ids:
            entry = hass.config_entries.async_get_entry(entry_id)
            if entry is None or entry.domain != DOMAIN:
                continue
            device = getattr(entry, "runtime_data", None)
            # Skips loaded-but-incapable devices (e.g. a curtain) and any entry
            # not yet set up (runtime_data is None).
            if isinstance(device, SupportsSyncTime):
                devices.append(device)
        if not devices:
            raise ServiceValidationError(
                "No SwitchBot device supporting time sync was targeted"
            )
        for device in devices:
            try:
                await device.async_sync_time()
            except (CommandError, BleakError, TimeoutError) as err:
                raise HomeAssistantError(
                    f"Failed to sync time on {device.address}: {err}"
                ) from err

    hass.services.async_register(DOMAIN, SERVICE_SYNC_TIME, _handle_sync_time)
    return True


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
