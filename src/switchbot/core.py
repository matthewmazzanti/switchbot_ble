import abc
import asyncio
import contextlib
import logging

from bleak import BleakClient
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import establish_connection
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry

from .proto.core import NOTIFY_CHAR_UUID, WRITE_CHAR_UUID, CommandReply

_LOGGER = logging.getLogger(__name__)

DOMAIN = "switchbot"

CONF_DEVICE_TYPE = "device_type"

# Command path tuning. The device replies on the notify char after acting on a
# command; we await that reply (confirming delivery) and retry the whole
# connect+write+await exchange if it fails or times out.
COMMAND_TIMEOUT = 8.0  # seconds to wait for the device's notify reply
COMMAND_ATTEMPTS = 3  # total tries per command before giving up


class CommandError(Exception):
    """A SwitchBot GATT command failed: no reply, or a non-OK status byte."""


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
        # Serialize commands: never two overlapping connections to one device.
        # (Advert-only devices keep it unused; cheap, and keeps one base class.)
        self._ble_lock = asyncio.Lock()

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

    async def async_send_command(self, payload: bytes) -> bytes:
        """Send a GATT command (or read) and return the device's raw reply.

        Serializes on the per-device lock so we never open two overlapping
        connections to one device; the connect/write/await/retry exchange is the
        coordinator-free `async_command`."""
        async with self._ble_lock:
            return await async_command(
                self.hass, self.address, payload, name=self.device_name
            )


async def async_command(
    hass: HomeAssistant,
    address: str,
    payload: bytes,
    *,
    name: str | None = None,
) -> bytes:
    """Connect to `address`, write `payload`, await the device's reply, and return
    it (raw bytes, status byte already OK-checked) — retrying the whole exchange.

    Coordinator-free, so the config-flow/setup path can issue a read before any
    coordinator exists. Commands from a coordinator go through
    `SwitchbotCoordinator.async_send_command`, which wraps this in the per-device
    lock so two callers never open overlapping connections to one device.

    The await is what makes a command reliable: a write-without-response that's
    silently dropped (e.g. a busy ESPHome proxy) surfaces here as a timeout and
    gets retried, instead of vanishing.

    TODO (maybe): we connect + disconnect per command. A live trace showed the
    actual write->notify exchange is ~16ms; the seconds of latency are all
    connect + disconnect, and on a single local adapter those radio ops
    serialize, so commanding N devices at once queues them. Two possible
    optimizations:
      1. cached_services on establish_connection — skips GATT service discovery
         on reconnect (smaller connect cost, still connects every command).
      2. short-lived connection reuse — hold the client open for a few idle
         seconds and reuse it for back-to-back commands, moving the ~2s
         disconnect off the critical path. Bigger change: needs a disconnect
         callback to invalidate the cache, once-per-connection notify setup, an
         idle-disconnect timer that races the command lock, and clean teardown
         on unload.
    Still debating #2: with a single adapter, concurrent commands to several
    devices already serialize, and a slow/unreachable device blocks the others
    until its timeout + retries elapse — so the win depends on adapter/proxy
    topology (an ESPHome proxy per area would parallelize and matters more than
    reuse). Revisit if command latency becomes a real problem.
    """
    name = name or address
    last_err: Exception | None = None
    for attempt in range(1, COMMAND_ATTEMPTS + 1):
        try:
            return await _command_once(hass, address, payload, name)
        except (CommandError, BleakError, TimeoutError) as err:
            last_err = err
            _LOGGER.debug(
                "%s: command attempt %d/%d failed: %s",
                name,
                attempt,
                COMMAND_ATTEMPTS,
                err,
            )
    assert last_err is not None  # loop ran at least once
    raise last_err


async def _command_once(
    hass: HomeAssistant, address: str, payload: bytes, name: str
) -> bytes:
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address, connectable=True
    )
    if ble_device is None:
        raise CommandError(f"BLE device {address} not available")
    _LOGGER.debug(
        "%s: resolved BLE device %s via %s",
        name,
        ble_device.address,
        ble_device.details,
    )

    # Re-resolve the best device on each connect retry; fall back to the one
    # we already have if the lookup momentarily returns nothing.
    def fresh_ble_device() -> BLEDevice:
        return (
            bluetooth.async_ble_device_from_address(hass, address, connectable=True)
            or ble_device
        )

    _LOGGER.debug("%s: connecting", name)
    async with await establish_connection(
        BleakClient,
        ble_device,
        name=name,
        ble_device_callback=fresh_ble_device,
    ) as client:
        _LOGGER.debug("%s: connected", name)
        loop = asyncio.get_running_loop()
        reply: asyncio.Future[bytes] = loop.create_future()

        def _on_notify(_char: object, data: bytearray) -> None:
            _LOGGER.debug("%s: notify <- %s", name, bytes(data).hex(" "))
            if not reply.done():
                reply.set_result(bytes(data))

        await client.start_notify(NOTIFY_CHAR_UUID, _on_notify)
        try:
            # SwitchBot's command char is write-without-response by design;
            # the device acks asynchronously on the notify char.
            _LOGGER.debug("%s: write -> %s", name, payload.hex(" "))
            await client.write_gatt_char(WRITE_CHAR_UUID, payload, response=False)
            async with asyncio.timeout(COMMAND_TIMEOUT):
                raw = await reply
        finally:
            with contextlib.suppress(BleakError):
                await client.stop_notify(NOTIFY_CHAR_UUID)

    try:
        ack = CommandReply.from_bytes(raw)
    except ValueError as err:
        raise CommandError(f"{name}: empty reply") from err
    if not ack.ok:
        raise CommandError(f"{name}: command rejected (status={ack.status})")
    _LOGGER.debug("%s: command acknowledged (status=0x%02x)", name, ack.status)
    return raw


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
