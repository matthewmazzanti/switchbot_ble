"""A SwitchBot Curtain 3 *dual group* (two curtains, one window) as one HA device.

Decomposition: two idiomatic single-MAC `_Curtain3Member` coordinators (one per
curtain) own the per-member state + availability, exactly as the passive-bluetooth
coordinator is designed for. A thin `Curtain3Group` glue object — NOT a
coordinator, it subscribes to nothing — supplies the group-level concerns the
coordinators can't: the shared device identity (`device_info`), the unique-id
namespace, and the command path. Every command relays through the primary's GATT
connection with a member index (1=primary, 2=secondary, 3=both); the secondary is
a pure advert source (never connected to). See PLAN-curtain3-group.md.
"""

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
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import Entity

from ... import generic_entity
from ...core import DOMAIN, SwitchbotCoordinator, SwitchbotEntity, normalize_mac
from ...proto.curtain3 import Curtain3ServiceData, SetPercentage, Stop
from .single import parse_advertisement

# Command member bitmask (decomp: LEFT=1, RIGHT=2, both=3). Primary is member 0
# (bit 0), secondary member 1 (bit 1).
INDEX_PRIMARY = 1
INDEX_SECONDARY = 2
INDEX_BOTH = 3


class _Curtain3Member(SwitchbotCoordinator[Curtain3ServiceData]):
    """One curtain in a group: a pure per-MAC advert state source.

    Unlike the standalone `Curtain3Coordinator` it authors no entities and has no
    command methods — the group owns the device identity, the entities, and the
    command path (relayed through the primary). `connectable` is per-member: the
    primary is the connectable command target, the secondary is advert-only.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        name: str,
        adv: bluetooth.BluetoothServiceInfoBleak | None,
        *,
        connectable: bool,
    ) -> None:
        super().__init__(
            hass=hass,
            address=address,
            device_name=name,
            device_type="curtain3",
            mode=bluetooth.BluetoothScanningMode.ACTIVE,
            connectable=connectable,
            initial=parse_advertisement(adv) if adv else None,
        )

    def _parse(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> Curtain3ServiceData | None:
        return parse_advertisement(service_info)


class Curtain3Group:
    """Group glue: two per-member coordinators + the group-level identity/commands.

    Stored on `entry.runtime_data`; quacks like a coordinator for the platform
    forwarders (exposes `address` and `create_platform_entities`) and for setup
    (`async_start`), but owns no BLE subscription itself.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        primary: str,
        secondary: str,
        name: str,
        adv: bluetooth.BluetoothServiceInfoBleak | None,
    ) -> None:
        last = bluetooth.async_last_service_info
        self._name = name
        self.address = normalize_mac(primary)
        self._secondary_address = normalize_mac(secondary)
        # Primary is the connectable command target; secondary is advert-only.
        self._primary = _Curtain3Member(
            hass, primary, name, adv or last(hass, self.address), connectable=True
        )
        self._secondary = _Curtain3Member(
            hass,
            secondary,
            name,
            last(hass, self._secondary_address),
            connectable=False,
        )

    @property
    def name(self) -> str:
        return self._name

    @property
    def device_info(self) -> device_registry.DeviceInfo:
        # One device, identified by the primary, that owns both BT connections.
        return device_registry.DeviceInfo(
            identifiers={(DOMAIN, self.address)},
            connections={
                (device_registry.CONNECTION_BLUETOOTH, self.address),
                (device_registry.CONNECTION_BLUETOOTH, self._secondary_address),
            },
            name=self._name,
            manufacturer="SwitchBot",
        )

    @callback
    def async_start(self) -> CALLBACK_TYPE:
        """Start both coordinators; return a composed unsub."""
        stop_primary = self._primary.async_start()
        stop_secondary = self._secondary.async_start()

        @callback
        def _stop() -> None:
            stop_primary()
            stop_secondary()

        return _stop

    # --- commands: all relay through the primary's connection ---

    async def async_set_position(self, index: int, position: int) -> None:
        """`position` is the SwitchBot value (0 = open, 100 = closed). For the
        `both` index the target is duplicated to each member."""
        position2 = position if index == INDEX_BOTH else 0
        cmd = SetPercentage(index=index, position=position, position2=position2)
        await self._primary.async_send_command(cmd.to_bytes())

    async def async_stop(self, index: int) -> None:
        await self._primary.async_send_command(Stop(index=index).to_bytes())

    # --- device-major entity definition ---

    def create_platform_entities(self, platform: str) -> list[Entity]:
        match platform:
            case "cover":
                return [
                    _Curtain3MemberCover(
                        self, self._primary, INDEX_PRIMARY, "primary", "Primary"
                    ),
                    _Curtain3MemberCover(
                        self, self._secondary, INDEX_SECONDARY, "secondary", "Secondary"
                    ),
                    _Curtain3BothCover(self),
                ]
            case "sensor":
                return [
                    self._battery(self._primary, "primary", "Primary"),
                    self._battery(self._secondary, "secondary", "Secondary"),
                ]
            case "binary_sensor":
                return [
                    self._calibrated(self._primary, "primary", "Primary"),
                    self._calibrated(self._secondary, "secondary", "Secondary"),
                ]
            case _:
                return []

    def _battery(
        self, coordinator: _Curtain3Member, suffix: str, label: str
    ) -> Entity:
        return generic_entity.Sensor(
            coordinator=coordinator,
            native_value_cb=lambda d: d.battery,
            unique_id=f"{self.address}:battery:{suffix}",
            name=f"{self._name} {label} Battery",
            device_class=SensorDeviceClass.BATTERY,
            native_unit_of_measurement=PERCENTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            device_info=self.device_info,
        )

    def _calibrated(
        self, coordinator: _Curtain3Member, suffix: str, label: str
    ) -> Entity:
        return generic_entity.BinarySensor(
            coordinator=coordinator,
            is_on_cb=lambda d: d.calibrated,
            unique_id=f"{self.address}:calibrated:{suffix}",
            name=f"{self._name} {label} Calibrated",
            device_class=None,
            device_info=self.device_info,
        )


class _Curtain3GroupCover(SwitchbotEntity[Curtain3ServiceData], CoverEntity):  # pyright: ignore[reportIncompatibleVariableOverride]
    """Base for the group's covers: position inversion + command plumbing.

    SwitchBot position is 0=open..100=closed; HA covers are 0=closed..100=open,
    so we invert. Commands route through the group (→ the primary's connection)
    with a member index; the rendered position comes from `_switchbot_position`.
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
        group: Curtain3Group,
        coordinator: _Curtain3Member,
        index: int,
        suffix: str,
        label: str,
    ) -> None:
        super().__init__(coordinator)
        self._group = group
        self._index = index
        self._attr_device_info = group.device_info
        self._attr_unique_id = f"{group.address}:cover:{suffix}"
        self._attr_name = f"{group.name} {label}"

    def _switchbot_position(self) -> int | None:
        """SwitchBot position (0=open..100=closed) this cover renders, or None."""
        raise NotImplementedError

    @property
    def current_cover_position(self) -> int | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        sb = self._switchbot_position()
        return 100 - sb if sb is not None else None

    @property
    def is_closed(self) -> bool | None:  # pyright: ignore[reportIncompatibleVariableOverride]
        pos = self.current_cover_position
        return pos == 0 if pos is not None else None

    async def async_open_cover(self, **kwargs: ty.Any) -> None:
        await self._group.async_set_position(self._index, 0)

    async def async_close_cover(self, **kwargs: ty.Any) -> None:
        await self._group.async_set_position(self._index, 100)

    async def async_stop_cover(self, **kwargs: ty.Any) -> None:
        await self._group.async_stop(self._index)

    async def async_set_cover_position(self, **kwargs: ty.Any) -> None:
        ha_pos = kwargs.get(ATTR_POSITION)
        if ha_pos is None:
            return
        # invert HA position (0=closed) back to SwitchBot's 0=open convention
        await self._group.async_set_position(self._index, 100 - int(ha_pos))


class _Curtain3MemberCover(_Curtain3GroupCover):
    """One physical curtain (primary or secondary): renders its own position."""

    def _switchbot_position(self) -> int | None:
        data = self.data
        return data.position if data is not None else None


class _Curtain3BothCover(_Curtain3GroupCover):
    """The whole group as one cover: averaged position, moves both (index 3).

    Subscribes to BOTH coordinators (so it re-renders on either member's advert)
    and is available only when both are. Average means `is_closed` is true only
    when both members are fully closed.
    """

    def __init__(self, group: Curtain3Group) -> None:
        super().__init__(group, group._primary, INDEX_BOTH, "both", "Both")
        self._secondary = group._secondary

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()  # subscribes to the primary
        self.async_on_remove(
            self._secondary.async_add_listener(self._handle_coordinator_update)
        )

    @property
    def available(self) -> bool:
        return super().available and self._secondary.available

    def _switchbot_position(self) -> int | None:
        primary = self.coordinator.data
        secondary = self._secondary.data
        if primary is None or secondary is None:
            return None
        return (primary.position + secondary.position) // 2
