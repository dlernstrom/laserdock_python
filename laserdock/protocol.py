"""USB wire format; no device access or timing."""

import struct
from collections.abc import Iterable
from enum import IntEnum

from laserdock.models import Sample

SAMPLE_FORMAT = struct.Struct("<BBBBHH")
CONTROL_PACKET_BYTES = 64
SAMPLES_PER_PACKET = 64


class DeviceError(RuntimeError):
    """Device access, protocol, or transfer failure."""


class Command(IntEnum):
    """Identify USB commands supported by the original LaserDock firmware."""

    SET_OUTPUT = 0x80
    GET_OUTPUT = 0x81
    SET_DAC_RATE = 0x82
    GET_DAC_RATE = 0x83
    GET_MAX_DAC_RATE = 0x84
    GET_SAMPLE_ELEMENT_COUNT = 0x85
    GET_ISO_PACKET_SAMPLE_COUNT = 0x86
    GET_MIN_DAC_VALUE = 0x87
    GET_MAX_DAC_VALUE = 0x88
    GET_RINGBUFFER_SAMPLE_COUNT = 0x89
    GET_RINGBUFFER_EMPTY_SAMPLE_COUNT = 0x8A
    GET_VERSION_MAJOR = 0x8B
    GET_VERSION_MINOR = 0x8C
    CLEAR_RINGBUFFER = 0x8D
    GET_BULK_PACKET_SAMPLE_COUNT = 0x8E


def encode_samples(samples: Iterable[Sample]) -> bytes:
    """Encode validated samples as eight-byte little-endian wire records."""
    return b"".join(SAMPLE_FORMAT.pack(s.r, s.g, s.b, 0, s.x, s.y) for s in samples)


def response_value(command: Command, response: bytes, width: int = 0) -> int:
    """Validate a command response and decode its unsigned payload value."""
    if len(response) != CONTROL_PACKET_BYTES:
        raise DeviceError(f"command {command.name}: expected a 64-byte response, got {len(response)}")
    if response[0] != command:
        raise DeviceError(f"command {command.name}: unexpected response command {response[0]:#x}")
    if response[1] != 0:
        raise DeviceError(f"command {command.name}: device status {response[1]}")
    return int.from_bytes(response[2 : 2 + width], "little")
