"""Dwell planning, blank travel, bounded packet streaming, and job execution."""

import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from itertools import islice, repeat
from typing import Protocol

from laserdock.models import BurnSettings, Sample, bounded_integer


class SampleSink(Protocol):
    """Define the device operations needed to stream a prepared job."""

    packet_size: int
    sample_rate: int

    def start(self) -> None:
        """Enable output for the prepared stream."""

    def send_samples(self, samples: tuple[Sample, ...]) -> None:
        """Submit one packet or raise when delivery is uncertain."""

    def wait_until_idle(self) -> None:
        """Wait for queued samples to finish or raise on a bounded timeout."""


@dataclass(frozen=True)
class BurnPlan:
    """Describe a finite point sequence and its dwell-expanded output stream."""

    points: tuple[Sample, ...]
    settings: BurnSettings
    passes: int = 1

    def __post_init__(self) -> None:
        """Require a positive, bounded number of passes."""
        bounded_integer("passes", self.passes, 1, 65535)

    @property
    def point_count(self) -> int:
        """Return the number of nonblank points across all passes."""
        return sum(self.settings.repeats(point) > 0 for point in self.points) * self.passes

    @property
    def sample_count(self) -> int:
        """Return the total lit and blank sample count, including final blanking."""
        count = (
            sum(
                repeats + self.settings.travel_samples
                for point in self.points
                if (repeats := self.settings.repeats(point)) > 0
            )
            * self.passes
        )
        return count + self.settings.travel_samples if count else 0

    @property
    def duration_seconds(self) -> float:
        """Return the nominal device output duration at the configured sample rate."""
        return self.sample_count / self.settings.sample_rate

    def samples(self) -> Iterator[Sample]:
        """Yield blank travel and lit dwell samples without materializing repeats."""
        last = None
        for _ in range(self.passes):
            for point in self.points:
                repeats = self.settings.repeats(point)
                if not repeats:
                    continue
                yield from repeat(Sample(point.x, point.y, 0, 0, 0, 0), self.settings.travel_samples)
                yield from repeat(point, repeats)
                last = point
        if last is not None:
            yield from repeat(Sample(last.x, last.y, 0, 0, 0, 0), self.settings.travel_samples)

    def packets(self, size: int) -> Iterator[tuple[Sample, ...]]:
        """Yield bounded packets, including a final partial packet when needed."""
        bounded_integer("packet size", size, 1, 64)
        samples = self.samples()
        while packet := tuple(islice(samples, size)):
            yield packet


def run_job(
    plan: BurnPlan,
    sink: SampleSink,
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Stream a plan inside a device context, pacing packets and draining the final output."""
    if sink.sample_rate != plan.settings.sample_rate:
        raise ValueError("plan and device sample rates differ")
    packets = plan.packets(sink.packet_size)
    first = next(packets, None)
    if first is None:
        return
    sink.start()
    sink.send_samples(first)
    deadline = clock() + len(first) / sink.sample_rate
    for packet in packets:
        while (remaining := deadline - clock()) > 0:
            sleep(remaining)
        sink.send_samples(packet)
        deadline = clock() + len(packet) / sink.sample_rate
    sink.wait_until_idle()
