import dataclasses as dc
import logging
import typing as ty

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_NAME

from .core import CONF_DEVICE_TYPE, DOMAIN
from .devices import REGISTRY
from .proto.core import SWITCHBOT_SERVICE, device_type

_LOGGER = logging.getLogger(__name__)


@dc.dataclass
class DeviceMetadata:
    device_type: str
    name: str

    @classmethod
    def from_svc(cls, svc: bytes) -> ty.Self | None:
        # Identify the model from the service-data type byte (reserved + pairing
        # bits masked off), via the device registry.
        entry = REGISTRY.get(device_type(svc[0]))
        if entry is None:
            return None
        return cls(device_type=entry.device_type, name=entry.name)


class SwitchbotConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, ty.Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, ty.Any] | None = None
    ) -> ConfigFlowResult:
        """Disable manual setup; require Bluetooth discovery."""
        return self.async_abort(reason="bluetooth_only")

    async def async_step_bluetooth(
        self,
        discovery_info: BluetoothServiceInfoBleak,
    ) -> ConfigFlowResult:
        # Ensure we have SwitchBot service data
        svc = discovery_info.service_data.get(SWITCHBOT_SERVICE)
        if not svc or len(svc) < 1:
            return self.async_abort(reason="not_switchbot")

        # De-dupe by MAC
        mac = discovery_info.address.upper()
        await self.async_set_unique_id(mac)
        self._abort_if_unique_id_configured()

        _LOGGER.debug(discovery_info)

        # Only allow supported models. Device id is lower 7 bits of first byte
        metadata = DeviceMetadata.from_svc(svc)
        if metadata is None:
            return self.async_abort(reason="unsupported_device")

        # Name in the "add device" card
        self.context["title_placeholders"] = {
            "name": f"SwitchBot {metadata.name}: {mac}",
        }

        # Stash discovered info for confirm step
        self._discovered = {
            CONF_ADDRESS: mac,
            CONF_DEVICE_TYPE: metadata.device_type,
        }

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, ty.Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovered device (optionally rename)."""
        if self._discovered is None:
            return self.async_abort(reason="no_discovery_info")

        # Show confirmation form
        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                data_schema=vol.Schema({CONF_NAME: str}),
                errors={},
            )

        # Process returned confirmation form data
        name = user_input[CONF_NAME].strip()
        return self.async_create_entry(
            title=name, data={**self._discovered, CONF_NAME: name}
        )
