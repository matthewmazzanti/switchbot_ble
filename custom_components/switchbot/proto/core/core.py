"""Generic SwitchBot BLE wire-format helpers."""

from dataclasses import dataclass
from typing import ClassVar, Self

MAGIC = 0x57
CMD_EXT = 0x0F
CMD_NOTIFY = 0x0E
CMD_TIMER_GET = 0x08
CMD_TIMER_SET = 0x09
EXT_SET = 0x45
EXT_GET = 0x46

# Device-type advertisement byte. Bit 7 is reserved; bit 5 (PAIRING_BIT) is set
# in normal operation and clear during pairing; the remaining bits identify the
# model. DEVICE_TYPE_MASK strips the reserved + pairing bits to that identity.
PAIRING_BIT = 0x20
DEVICE_TYPE_MASK = 0x5F


def device_type(type_byte: int) -> int:
    """Model identity from a device-type byte (reserved + pairing bits off)."""
    return type_byte & DEVICE_TYPE_MASK


def is_pairing(type_byte: int) -> bool:
    """True when the device is advertising in pairing mode (bit 5 clear)."""
    return not (type_byte & PAIRING_BIT)


# BLE transport identifiers — where to find SwitchBot data on the wire.
MANUFACTURER_ID = 2409  # manufacturer-data company id (0x0969)
SWITCHBOT_SERVICE = "0000fd3d-0000-1000-8000-00805f9b34fb"  # service-data UUID
WRITE_CHAR_UUID = "cba20002-224d-11e6-9fb8-0002a5d5c51b"  # GATT command-write char
NOTIFY_CHAR_UUID = "cba20003-224d-11e6-9fb8-0002a5d5c51b"  # GATT response-notify char

# Response status byte (reply[0]) on the notify char. The app treats both 0x01
# and 0x06 (bootloader) as success; 0x02 error, 0x03 busy, etc. are failures.
# See decomp BleMsgParser.java (WOCODE_RESP_STATUS_*).
RESP_STATUS_OK = 0x01
RESP_STATUS_BOOTLOADER = 0x06
RESP_STATUS_OK_SET = frozenset((RESP_STATUS_OK, RESP_STATUS_BOOTLOADER))


@dataclass(frozen=True, slots=True)
class CommandReply:
    """The generic command acknowledgement shared by every notify reply.

    Per decomp (BleMsgParser), every reply leads with a status byte; the rest is
    command-specific and decoded by per-device response types (e.g. curtain3's
    responses.py). This captures only the universal accept/reject signal, so it
    works for any command on any device without assuming a payload shape.

    NOTE (design tension): today the typed reply parsers (responses.py) are
    payload-only and assume an ok reply — the status gate lives in the transport
    (core.async_request, which checks `ok` and retries on a bad status), so a
    typed reply doesn't own its own status. The envisioned fix is a composable
    reply base: a per-reply-type subclass whose parse() validates the status byte
    and raises on a bad one, so the transport retry loop can call `reply.parse`
    directly (with CommandReply becoming just the command/ack case). Deferred —
    moving the check into proto parsers would couple them to retry/exception
    semantics they currently stay free of.
    """

    status: int

    @property
    def ok(self) -> bool:
        return self.status in RESP_STATUS_OK_SET

    def to_bytes(self) -> bytes:
        return bytes([self.status])

    @classmethod
    def parse(cls, data: bytes) -> Self:
        # `parse` (not `from_bytes`): the reply convention — commands roundtrip
        # via from_bytes/to_bytes, replies decode via parse (see responses.py).
        if not data:
            raise ValueError("empty command reply")
        return cls(status=data[0])


def build(*parts: int | bytes) -> bytes:
    """Assemble a byte sequence from ints and byte strings."""
    buf = bytearray()
    for p in parts:
        if isinstance(p, int):
            buf.append(p)
        else:
            buf.extend(p)
    return bytes(buf)


def tail(header: bytes, data: bytes) -> bytes:
    """Validate *header* prefix against *data* and return the payload tail."""
    n = len(header)
    if data[:n] != header:
        raise ValueError(f"Bad header: {data[:n].hex()}")
    return data[n:]


@dataclass(frozen=True, slots=True)
class FixedCommand:
    """Base class for parameterless fixed-wire commands."""

    _WIRE: ClassVar[bytes]

    def to_bytes(self) -> bytes:
        return bytes(self._WIRE)

    @classmethod
    def from_bytes(cls, data: bytes) -> Self:
        if data != cls._WIRE:
            raise ValueError(f"Expected {cls._WIRE.hex()}, got {data.hex()}")
        return cls()


# ---------------------------------------------------------------------------
# Header builders
# ---------------------------------------------------------------------------


def ext(*sub: int | bytes) -> bytes:
    """`57 0F <sub...>` — the extended-command space. `ext_set`/`ext_get` are the
    0x45/0x46 sub-commands; Wi-Fi provisioning uses its own sub-codes here."""
    return build(MAGIC, CMD_EXT, *sub)


def ext_get(*sub: int) -> bytes:
    return ext(EXT_GET, *sub)


def ext_set(*sub: int) -> bytes:
    return ext(EXT_SET, *sub)


def notify(*sub: int) -> bytes:
    return build(MAGIC, CMD_NOTIFY, *sub)


def timer_get(*sub: int) -> bytes:
    return build(MAGIC, CMD_TIMER_GET, *sub)


def timer_set(*sub: int) -> bytes:
    return build(MAGIC, CMD_TIMER_SET, *sub)
