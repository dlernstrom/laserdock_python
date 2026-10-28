"""Verify dwell expansion, blank travel, packet boundaries, and pacing."""

from typing import Never, cast

import pytest

from laserdock.jobs import BurnPlan, run_job
from laserdock.models import BurnSettings, Sample
from tests.fakes import Clock


class Sink:
    """Record job execution events and packets without a device."""

    packet_size = 64
    sample_rate = 20

    def __init__(self) -> None:
        """Initialize empty event and packet records."""
        self.events: list[str] = []
        self.packets: list[tuple[Sample, ...]] = []

    def start(self) -> None:
        """Record the output enable operation."""
        self.events.append("start")

    def send_samples(self, samples: tuple[Sample, ...]) -> None:
        """Record the submitted packet without sending it to hardware."""
        self.events.append("write")
        self.packets.append(samples)

    def wait_until_idle(self) -> None:
        """Record the final output drain operation."""
        self.events.append("drain")


def test_partial_final_packet_and_travel_are_counted() -> None:
    """Include blank travel and completion samples in packet and duration totals."""
    settings = BurnSettings(minimum_seconds=0, intensity_seconds=0.05)
    plan = BurnPlan((Sample(1, 2), Sample(3, 4)), settings, passes=2)
    assert plan.point_count == 4
    assert plan.sample_count == 9
    assert plan.duration_seconds == 0.45
    packets = list(plan.packets(3))
    assert [len(packet) for packet in packets] == [3, 3, 3]
    samples = [sample for packet in packets for sample in packet]
    assert [(p.x, p.y, p.r) for p in samples[:4]] == [
        (1, 2, 0),
        (1, 2, 255),
        (3, 4, 0),
        (3, 4, 255),
    ]


def test_packet_pacing_and_final_drain(clock: Clock) -> None:
    """Pace consecutive packets and drain the final blanked packet."""
    # Each point uses 70 lit samples plus one blank sample.
    plan = BurnPlan((Sample(1, 2),), BurnSettings())
    sink = Sink()
    run_job(plan, sink, clock=clock, sleep=clock.sleep)
    assert [len(packet) for packet in sink.packets] == [64, 8]
    assert sink.packets[-1][-1].r == 0
    assert clock.sleeps == [3.2]
    assert sink.events == ["start", "write", "write", "drain"]


def test_empty_job_never_starts_output(clock: Clock) -> None:
    """Avoid enabling output when no points require engraving."""
    sink = Sink()
    run_job(BurnPlan((Sample(0, 0, intensity=0),), BurnSettings()), sink, clock=clock, sleep=clock.sleep)
    assert sink.events == []


def test_execution_failure_stops_sending(clock: Clock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Stop streaming immediately when packet delivery fails."""
    sink = Sink()

    def fail(samples: tuple[Sample, ...]) -> Never:
        """Simulate a delivery failure before any further job operations."""
        raise OSError("simulated failure")

    monkeypatch.setattr(sink, "send_samples", fail)
    with pytest.raises(OSError):
        run_job(BurnPlan((Sample(0, 0),), BurnSettings()), sink, clock=clock, sleep=clock.sleep)
    assert sink.events == ["start"]


def test_mismatched_rate_is_rejected_before_start() -> None:
    """Reject incompatible plan and device rates before enabling output."""
    sink = Sink()
    with pytest.raises(ValueError, match="sample rates differ"):
        run_job(BurnPlan((Sample(0, 0),), BurnSettings(sample_rate=10)), sink)
    assert not sink.events


@pytest.mark.parametrize("passes", [0, -1, 1.5])
def test_invalid_pass_count(passes: int | float) -> None:
    """Reject zero, negative, and fractional pass counts."""
    with pytest.raises(ValueError):
        BurnPlan((), BurnSettings(), cast(int, passes))
