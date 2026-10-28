"""Device commands and lifecycle, independent of images and job generation."""

import logging
import struct
import time
from collections.abc import Callable, Sequence
from types import TracebackType
from typing import Self

from laserdock.models import Sample, bounded_integer
from laserdock.protocol import (
    SAMPLES_PER_PACKET,
    Command,
    DeviceError,
    encode_samples,
    response_value,
)
from laserdock.transport import Transport

logger = logging.getLogger(__name__)


class LaserDock:
    """Manage a connected device through explicit output and cleanup stages."""

    def __init__(
        self,
        transport: Transport,
        sample_rate: int = 20,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Store the transport and timing dependencies without opening hardware."""
        bounded_integer("sample_rate", sample_rate, 1, 0xFFFFFFFF)
        self.transport = transport
        self.sample_rate = sample_rate
        self.packet_size = SAMPLES_PER_PACKET
        self.capacity = 0
        self._clock, self._sleep = clock, sleep
        self._connected = self._running = self._failed = False

    def _command(self, command: Command, payload: bytes = b"", width: int = 0) -> int:
        """Exchange and validate one command on an open transport."""
        if not self._connected:
            raise DeviceError("device is not connected")
        response = self.transport.exchange(bytes([command]) + payload)
        return response_value(command, response, width)

    def __enter__(self) -> Self:
        """Open and configure the device with output disabled."""
        if self._connected:
            raise DeviceError("device is already connected")
        self.transport.open()
        self._connected = True
        self._failed = False
        try:
            self._command(Command.SET_OUTPUT, b"\x00")
            self._command(Command.CLEAR_RINGBUFFER, b"\x00")
            maximum = self._command(Command.GET_MAX_DAC_RATE, width=4)
            if not 0 < self.sample_rate <= maximum:
                raise DeviceError(f"sample rate must be between 1 and device maximum {maximum}")
            self.packet_size = min(SAMPLES_PER_PACKET, self._command(Command.GET_BULK_PACKET_SAMPLE_COUNT, width=4))
            self.capacity = self._command(Command.GET_RINGBUFFER_SAMPLE_COUNT, width=4)
            if self.packet_size < 1 or self.capacity < self.packet_size:
                raise DeviceError("device reported invalid sample buffer sizes")
            self._command(Command.SET_DAC_RATE, struct.pack("<I", self.sample_rate))
            actual_rate = self._command(Command.GET_DAC_RATE, width=4)
            if actual_rate != self.sample_rate:
                raise DeviceError(f"device accepted sample rate {actual_rate}, expected {self.sample_rate}")
        except BaseException as error:
            self._cleanup(error)
            raise
        return self

    def start(self) -> None:
        """Enable output once, rejecting failed jobs until the context is reopened."""
        if self._failed:
            raise DeviceError("job failed; close and reopen the device before starting again")
        if self._running:
            raise DeviceError("output is already running")
        try:
            self._command(Command.SET_OUTPUT, b"\x01")
        except BaseException:
            self._failed = True
            raise
        self._running = True

    def _wait_for_space(self, count: int, timeout: float) -> None:
        """Poll available device buffer space until enough is free or the deadline expires."""
        deadline = self._clock() + timeout
        while True:
            free = self._command(Command.GET_RINGBUFFER_EMPTY_SAMPLE_COUNT, width=4)
            if not 0 <= free <= self.capacity:
                raise DeviceError(f"device reported invalid free buffer size {free}")
            if free >= count:
                return
            if self._clock() >= deadline:
                raise DeviceError("timed out waiting for device sample buffer")
            self._sleep(min(0.05, max(0, deadline - self._clock())))

    def send_samples(self, samples: Sequence[Sample]) -> None:
        """Submit one bounded packet, marking uncertain delivery as a failed job."""
        if not self._running or self._failed:
            raise DeviceError("output must be running and the job must not have failed")
        if not 1 <= len(samples) <= self.packet_size:
            raise ValueError(f"a packet must contain 1 to {self.packet_size} samples")
        try:
            self._wait_for_space(len(samples), self.packet_size / self.sample_rate + 5)
            self.transport.write(encode_samples(samples))
        except BaseException:
            self._failed = True
            raise

    def wait_until_idle(self) -> None:
        """Wait for the complete device buffer to become free before shutdown."""
        if not self._running or self._failed:
            raise DeviceError("cannot drain a stopped or failed job")
        try:
            self._wait_for_space(self.capacity, self.packet_size / self.sample_rate + 5)
        except BaseException:
            self._failed = True
            raise

    def close(self) -> None:
        """Disable output, clear queued samples, and release transport resources."""
        if not self._connected:
            return
        errors: list[Exception] = []
        try:
            for command, payload in (
                (Command.SET_OUTPUT, b"\x00"),
                (Command.CLEAR_RINGBUFFER, b"\x00"),
            ):
                try:
                    self._command(command, payload)
                except Exception as error:
                    errors.append(error)
        finally:
            self._connected = self._running = False
            try:
                self.transport.close()
            except Exception as error:
                errors.append(error)
        if errors:
            raise DeviceError(f"device shutdown failed: {errors}") from errors[0]

    def _cleanup(self, original_error: BaseException | None) -> None:
        """Report shutdown errors without masking an active job exception."""
        try:
            self.close()
        except Exception as error:
            if original_error is None:
                raise
            original_error.add_note(f"Device shutdown also failed: {error}")
            logger.error("Device shutdown also failed: %s", error)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the device after success, failure, or interruption."""
        self._cleanup(exc_value)
