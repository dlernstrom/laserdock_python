"""Provide deterministic clocks and in-memory USB transport doubles."""

from collections import deque
from dataclasses import dataclass, field

from laserdock.protocol import Command, DeviceError


@dataclass
class Clock:
    """Track elapsed simulated time without sleeping in real time."""

    now: float = 0.0
    sleeps: list[float] = field(default_factory=list)

    def __call__(self) -> float:
        """Return the current simulated monotonic time."""
        return self.now

    def sleep(self, duration: float) -> None:
        """Advance simulated time and record the requested delay."""
        assert duration >= 0
        self.sleeps.append(duration)
        self.now += duration


class FakeTransport:
    """Record transfers and simulate command responses or delivery failures."""

    def __init__(self) -> None:
        """Initialize a closed transport with valid default device capabilities."""
        self.requests: list[bytes] = []
        self.writes: list[bytes] = []
        self.opened = self.closed = False
        self.rate = 20
        self.free: deque[int] = deque()
        self.fail_command: Command | None = None
        self.fail_write = False
        self.values = {
            Command.GET_MAX_DAC_RATE: 100_000,
            Command.GET_BULK_PACKET_SAMPLE_COUNT: 64,
            Command.GET_RINGBUFFER_SAMPLE_COUNT: 256,
            Command.GET_RINGBUFFER_EMPTY_SAMPLE_COUNT: 256,
        }

    def open(self) -> None:
        """Record that the transport was opened."""
        self.opened = True

    def close(self) -> None:
        """Record that transport cleanup was attempted."""
        self.closed = True

    def exchange(self, request: bytes) -> bytes:
        """Return a valid command response or raise a configured command failure."""
        self.requests.append(request)
        command = Command(request[0])
        if command == self.fail_command:
            raise DeviceError("simulated command failure")
        if command == Command.SET_DAC_RATE:
            self.rate = int.from_bytes(request[1:], "little")
        if command == Command.GET_DAC_RATE:
            value = self.rate
        elif command == Command.GET_RINGBUFFER_EMPTY_SAMPLE_COUNT and self.free:
            value = self.free.popleft()
        else:
            value = self.values.get(command, 0)
        return bytes([command, 0]) + value.to_bytes(4, "little") + bytes(58)

    def write(self, data: bytes) -> None:
        """Record one packet and optionally simulate an uncertain write failure."""
        self.writes.append(data)
        if self.fail_write:
            raise DeviceError("simulated failed sample transfer")
