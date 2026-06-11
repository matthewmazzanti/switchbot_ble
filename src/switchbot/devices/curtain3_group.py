"""Coordinator for a SwitchBot Curtain 3 *dual group* (two curtains, one window).

One HA device represents the whole group, identified by the **primary** curtain
(the controllable node that advertises `is_primary && in_group`). The group:

- subscribes passively to BOTH MACs — each curtain advertises only its own
  position/battery, so the primary's advert feeds the primary slice and the
  secondary's advert feeds the secondary slice (no polling needed);
- routes every command through a single GATT connection to the primary, carrying
  a member index (1=primary, 2=secondary, 3=both); the primary relays to the
  secondary over the chain.

Availability and the connection target are keyed to the primary; the secondary's
advert drives state only. See PLAN-curtain3-group.md for the full design.
"""

import dataclasses as dc
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
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity import Entity

from .. import generic_entity
from ..core import ConnectableSwitchbotCoordinator, SwitchbotEntity, normalize_mac
from ..proto.curtain3 import Curtain3ServiceData, SetPercentage, Stop
from .curtain3 import parse_advertisement

# Command member bitmask (decomp: LEFT=1, RIGHT=2, both=3). The primary is
# member 0 (bit 0), the secondary member 1 (bit 1).
INDEX_PRIMARY = 1
INDEX_SECONDARY = 2
INDEX_BOTH = 3


@dc.dataclass(frozen=True, slots=True)
class Curtain3GroupState:
    """Combined group state, built only once BOTH members have advertised at
    least once (so nothing here is optional — a group with a missing half is not
    a coherent thing to publish). After that each slice is the last-seen advert
    of its member, retained independently."""

    primary: Curtain3ServiceData
    secondary: Curtain3ServiceData


class Curtain3GroupCoordinator(ConnectableSwitchbotCoordinator[Curtain3GroupState]):
    """Per-group object: dual passive subscription + the primary command path."""

    _last_primary: Curtain3ServiceData | None
    _last_secondary: Curtain3ServiceData | None

    def __init__(
        self,
        hass: HomeAssistant,
        primary: str,
        secondary: str,
        name: str,
        adv: bluetooth.BluetoothServiceInfoBleak | None,
    ) -> None:
        self._secondary_address = normalize_mac(secondary)
        self._last_primary = None
        # Pre-populate the secondary slice from its last-seen advert, if HA
        # already has one cached (so it isn't `unknown` until the next frame).
        sec_adv = bluetooth.async_last_service_info(hass, self._secondary_address)
        self._last_secondary = parse_advertisement(sec_adv) if sec_adv else None
        super().__init__(
            hass=hass,
            address=primary,
            device_name=name,
            device_type="curtain3_group",
            # Active scan + connectable: we issue position commands over GATT.
            mode=bluetooth.BluetoothScanningMode.ACTIVE,
            connectable=True,
            initial=self._parse(adv) if adv else None,
        )

    # --- advertisements: primary via the base path, secondary via extra cb ---

    @property
    def available(self) -> bool:
        """Available only once we have a complete picture (both members seen).

        State is sticky after that, so a secondary that later goes silent keeps
        its last-known slice and the group stays available — this gate only holds
        back the brief initial window before the secondary's first advert.
        """
        return super().available and self.data is not None

    def _combined(self) -> Curtain3GroupState | None:
        """Combined state, or None until BOTH members have advertised once."""
        if self._last_primary is None or self._last_secondary is None:
            return None
        return Curtain3GroupState(self._last_primary, self._last_secondary)

    def _parse(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> Curtain3GroupState | None:
        """Handle a *primary* advert: refresh the primary slice, recombine."""
        if (primary := parse_advertisement(service_info)) is not None:
            self._last_primary = primary
        return self._combined()

    @callback
    def _async_handle_secondary_event(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle a *secondary* advert: refresh the secondary slice and fan out.

        Deliberately does NOT touch `_available` (that stays keyed to the primary
        via the base path); only emits once both members have been seen.
        """
        if (secondary := parse_advertisement(service_info)) is None:
            return
        self._last_secondary = secondary
        if (combined := self._combined()) is not None:
            self.data = combined
            self.async_update_listeners()

    @callback
    def async_start(self) -> CALLBACK_TYPE:
        """Subscribe to both MACs; return a composed unsub.

        Public-API override: `super().async_start()` wires the primary (advert +
        availability); we add a passive secondary subscription alongside.
        """
        stop_primary = super().async_start()
        stop_secondary = bluetooth.async_register_callback(
            self.hass,
            self._async_handle_secondary_event,
            bluetooth.BluetoothCallbackMatcher(
                address=self._secondary_address, connectable=False
            ),
            self.mode,
        )

        @callback
        def _stop() -> None:
            stop_primary()
            stop_secondary()

        return _stop

    # --- commands (single GATT connection to the primary; index = member) ---

    async def async_set_position(self, index: int, position: int) -> None:
        """`position` is the SwitchBot value (0 = open, 100 = closed). For the
        `both` index the target is duplicated to each member."""
        position2 = position if index == INDEX_BOTH else 0
        cmd = SetPercentage(index=index, position=position, position2=position2)
        await self.async_send_command(cmd.to_bytes())

    async def async_stop(self, index: int) -> None:
        await self.async_send_command(Stop(index=index).to_bytes())

    # --- device-major entity definition ---

    def create_platform_entities(self, platform: str) -> list[Entity]:
        match platform:
            case "cover":
                return [
                    _Curtain3MemberCover(self, "primary"),
                    _Curtain3MemberCover(self, "secondary"),
                    _Curtain3BothCover(self),
                ]
            case "sensor":
                return [
                    generic_entity.Sensor(
                        coordinator=self,
                        native_value_cb=lambda d: d.primary.battery,
                        unique_id=f"{self.address}:battery:primary",
                        name=f"{self.device_name} Primary Battery",
                        device_class=SensorDeviceClass.BATTERY,
                        native_unit_of_measurement=PERCENTAGE,
                        state_class=SensorStateClass.MEASUREMENT,
                    ),
                    generic_entity.Sensor(
                        coordinator=self,
                        native_value_cb=lambda d: d.secondary.battery,
                        unique_id=f"{self.address}:battery:secondary",
                        name=f"{self.device_name} Secondary Battery",
                        device_class=SensorDeviceClass.BATTERY,
                        native_unit_of_measurement=PERCENTAGE,
                        state_class=SensorStateClass.MEASUREMENT,
                    ),
                ]
            case "binary_sensor":
                return [
                    generic_entity.BinarySensor(
                        coordinator=self,
                        is_on_cb=lambda d: d.primary.calibrated,
                        unique_id=f"{self.address}:calibrated:primary",
                        name=f"{self.device_name} Primary Calibrated",
                        device_class=None,
                    ),
                    generic_entity.BinarySensor(
                        coordinator=self,
                        is_on_cb=lambda d: d.secondary.calibrated,
                        unique_id=f"{self.address}:calibrated:secondary",
                        name=f"{self.device_name} Secondary Calibrated",
                        device_class=None,
                    ),
                ]
            case _:
                return []


class _Curtain3GroupCover(SwitchbotEntity[Curtain3GroupState], CoverEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Base for the group's covers: position inversion + command plumbing.

    SwitchBot position is 0=open..100=closed; HA covers are 0=closed..100=open,
    so we invert. Subclasses supply the member command `index` and the SwitchBot
    position to render (a single member's, or the group average).
    """

    _attr_device_class = CoverDeviceClass.CURTAIN
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(
        self,
        coordinator: Curtain3GroupCoordinator,
        index: int,
        suffix: str,
        label: str,
    ) -> None:
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._index = index
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.address}:cover:{suffix}"
        self._attr_name = f"{coordinator.device_name} {label}"

    def _switchbot_position(self, data: Curtain3GroupState) -> int:
        """SwitchBot position (0=open..100=closed) this cover renders."""
        raise NotImplementedError

    @property
    def current_cover_position(self) -> int | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        data = self.data
        return 100 - self._switchbot_position(data) if data is not None else None

    @property
    def is_closed(self) -> bool | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        pos = self.current_cover_position
        return pos == 0 if pos is not None else None

    async def async_open_cover(self, **kwargs: ty.Any) -> None:
        await self._coordinator.async_set_position(self._index, 0)

    async def async_close_cover(self, **kwargs: ty.Any) -> None:
        await self._coordinator.async_set_position(self._index, 100)

    async def async_stop_cover(self, **kwargs: ty.Any) -> None:
        await self._coordinator.async_stop(self._index)

    async def async_set_cover_position(self, **kwargs: ty.Any) -> None:
        ha_pos = kwargs.get(ATTR_POSITION)
        if ha_pos is None:
            return
        # invert HA position (0=closed) back to SwitchBot's 0=open convention
        await self._coordinator.async_set_position(self._index, 100 - int(ha_pos))


class _Curtain3MemberCover(_Curtain3GroupCover):
    """One physical curtain in the group (primary or secondary)."""

    def __init__(
        self,
        coordinator: Curtain3GroupCoordinator,
        member: ty.Literal["primary", "secondary"],
    ) -> None:
        index = INDEX_PRIMARY if member == "primary" else INDEX_SECONDARY
        super().__init__(coordinator, index, suffix=member, label=member.capitalize())
        self._member = member

    def _switchbot_position(self, data: Curtain3GroupState) -> int:
        member = data.primary if self._member == "primary" else data.secondary
        return member.position


class _Curtain3BothCover(_Curtain3GroupCover):
    """The whole group as one cover: averaged position, moves both (index 3).

    Average means `is_closed` is true only when both members are fully closed
    (and fully-open only when both are open), which is the coherent reading.
    """

    def __init__(self, coordinator: Curtain3GroupCoordinator) -> None:
        super().__init__(coordinator, INDEX_BOTH, suffix="both", label="Both")

    def _switchbot_position(self, data: Curtain3GroupState) -> int:
        return (data.primary.position + data.secondary.position) // 2
