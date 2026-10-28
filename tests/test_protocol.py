"""Verify binary sample layout and command response validation."""

import struct

import pytest

from laserdock.models import Sample
from laserdock.protocol import Command, DeviceError, encode_samples, response_value


def test_wire_sample_layout() -> None:
    """Encode color padding and coordinates in the specified byte order."""
    assert encode_samples([Sample(4095, 2048, 1, 2, 3)]) == b"\x01\x02\x03\x00\xff\x0f\x00\x08"


def test_32_bit_response_is_not_truncated() -> None:
    """Decode a response payload larger than the 16-bit range."""
    reply = bytes([Command.GET_DAC_RATE, 0]) + struct.pack("<I", 100_000) + bytes(58)
    assert response_value(Command.GET_DAC_RATE, reply, 4) == 100_000


@pytest.mark.parametrize(
    "reply",
    [
        bytes([Command.GET_DAC_RATE, 0]),
        bytes([Command.GET_MAX_DAC_RATE, 0]) + bytes(62),
        bytes([Command.GET_DAC_RATE, 1]) + bytes(62),
    ],
)
def test_invalid_responses_are_visible(reply: bytes) -> None:
    """Reject truncated responses, wrong command echoes, and nonzero status bytes."""
    with pytest.raises(DeviceError):
        response_value(Command.GET_DAC_RATE, reply, 4)
