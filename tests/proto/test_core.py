"""Tests for shared proto/core wire helpers."""

import pytest

from switchbot.proto.core import (
    RESP_STATUS_BOOTLOADER,
    RESP_STATUS_OK,
    CommandReply,
)


class TestCommandReply:
    def test_roundtrip(self):
        reply = CommandReply(status=RESP_STATUS_OK)
        assert CommandReply.from_bytes(reply.to_bytes()) == reply

    def test_from_bytes_takes_first_byte(self):
        # Only the leading status byte matters; trailing payload is ignored.
        assert CommandReply.from_bytes(bytes([0x01, 0x00, 0x32])).status == 0x01

    def test_ok_status(self):
        assert CommandReply.from_bytes(bytes([RESP_STATUS_OK])).ok

    def test_bootloader_is_ok(self):
        assert CommandReply.from_bytes(bytes([RESP_STATUS_BOOTLOADER])).ok

    @pytest.mark.parametrize("status", [0x00, 0x02, 0x03, 0x05, 0x09])
    def test_non_ok_status(self, status):
        assert not CommandReply.from_bytes(bytes([status])).ok

    def test_empty_reply_raises(self):
        with pytest.raises(ValueError):
            CommandReply.from_bytes(b"")
