"""Verify device setup, output lifecycle, flow control, and failure handling."""

import pytest

from laserdock.device import LaserDock
from laserdock.jobs import BurnPlan, run_job
from laserdock.models import BurnSettings, Sample
from laserdock.protocol import Command, DeviceError
from tests.fakes import Clock, FakeTransport


def test_construction_has_no_device_side_effects(transport: FakeTransport) -> None:
    """Keep device discovery and commands out of object construction."""
    LaserDock(transport)
    assert not transport.opened
    assert not transport.requests


def test_output_requires_explicit_start_and_context_always_stops(transport: FakeTransport) -> None:
    """Require explicit output enable and disable output when the context closes."""
    with LaserDock(transport) as dock:
        assert bytes([Command.SET_OUTPUT, 1]) not in transport.requests
        with pytest.raises(DeviceError, match="running"):
            dock.send_samples((Sample(0, 0),))
        dock.start()
        dock.send_samples((Sample(0, 0),))
    assert transport.closed
    assert transport.requests[-2:] == [
        bytes([Command.SET_OUTPUT, 0]),
        bytes([Command.CLEAR_RINGBUFFER, 0]),
    ]
    dock.close()  # Idempotent; transport is not reopened by cleanup.


def test_complete_job_transmits_final_partial_packet_and_drains(transport: FakeTransport, clock: Clock) -> None:
    """Transmit the partial final packet and wait for queued samples to drain."""
    transport.free.extend([256, 256, 200, 256])
    with LaserDock(transport, clock=clock, sleep=clock.sleep) as dock:
        run_job(BurnPlan((Sample(1, 2),), BurnSettings()), dock, clock=clock, sleep=clock.sleep)
    assert [len(data) for data in transport.writes] == [512, 64]
    assert clock.now == pytest.approx(3.25)
    assert transport.closed


@pytest.mark.parametrize("failure", [RuntimeError("job failure"), KeyboardInterrupt()])
def test_interruption_and_exception_close_output(transport: FakeTransport, failure: BaseException) -> None:
    """Disable output and release resources after exceptions or interruptions."""
    with pytest.raises(type(failure)), LaserDock(transport) as dock:
        dock.start()
        raise failure
    assert transport.closed
    assert transport.requests[-2] == bytes([Command.SET_OUTPUT, 0])


def test_write_failure_aborts_without_retry_or_resuming(transport: FakeTransport) -> None:
    """Reject further writes after uncertain delivery without retrying the packet."""
    transport.fail_write = True
    with pytest.raises(DeviceError, match="simulated failed"), LaserDock(transport) as dock:
        dock.start()
        with pytest.raises(DeviceError, match="simulated failed"):
            dock.send_samples((Sample(0, 0),))
        with pytest.raises(DeviceError, match="failed"):
            dock.send_samples((Sample(0, 0),))
        with pytest.raises(DeviceError, match="failed"):
            dock.start()
        raise DeviceError("simulated failed")
    assert len(transport.writes) == 1
    assert transport.closed


def test_setup_failure_closes_transport_and_disables_output(transport: FakeTransport) -> None:
    """Clean up a partially configured device before propagating setup failure."""
    transport.fail_command = Command.GET_MAX_DAC_RATE
    with pytest.raises(DeviceError, match="command failure"), LaserDock(transport):
        pytest.fail("setup should fail")
    assert transport.closed
    assert transport.requests[-2] == bytes([Command.SET_OUTPUT, 0])


def test_shutdown_failure_does_not_mask_original_error(transport: FakeTransport) -> None:
    """Preserve the job exception while attaching a secondary cleanup failure."""
    original = ValueError("original job failure")
    with pytest.raises(ValueError, match="original job failure"), LaserDock(transport):
        transport.fail_command = Command.SET_OUTPUT
        raise original
    assert "shutdown also failed" in original.__notes__[0]
    assert transport.closed
    assert transport.requests[-1] == bytes([Command.CLEAR_RINGBUFFER, 0])


def test_shutdown_failure_is_reported_without_original_error(transport: FakeTransport) -> None:
    """Report cleanup failure when no earlier job exception exists."""
    with pytest.raises(DeviceError, match="shutdown failed"), LaserDock(transport):
        transport.fail_command = Command.SET_OUTPUT
    assert transport.closed


@pytest.mark.parametrize(
    "command,value",
    [
        (Command.GET_MAX_DAC_RATE, 0),
        (Command.GET_BULK_PACKET_SAMPLE_COUNT, 0),
        (Command.GET_RINGBUFFER_SAMPLE_COUNT, 1),
    ],
)
def test_invalid_capabilities_fail_before_enabling(transport: FakeTransport, command: Command, value: int) -> None:
    """Reject invalid rate and buffer capabilities before enabling output."""
    transport.values[command] = value
    with pytest.raises(DeviceError), LaserDock(transport):
        pytest.fail("invalid capabilities should fail")
    assert bytes([Command.SET_OUTPUT, 1]) not in transport.requests
    assert transport.closed


def test_full_width_rate_set_and_get(transport: FakeTransport) -> None:
    """Preserve all 32 bits of the configured sample rate."""
    with LaserDock(transport, sample_rate=100_000):
        assert transport.rate == 100_000


def test_device_packet_limit_is_respected(transport: FakeTransport) -> None:
    """Reject packets larger than the device-reported transfer limit."""
    transport.values[Command.GET_BULK_PACKET_SAMPLE_COUNT] = 16
    with LaserDock(transport) as dock:
        assert dock.packet_size == 16
        dock.start()
        with pytest.raises(ValueError):
            dock.send_samples((Sample(0, 0),) * 17)


def test_wait_for_space_has_bounded_timeout(transport: FakeTransport, clock: Clock) -> None:
    """Abort when the device buffer remains full past the deadline."""
    transport.values[Command.GET_RINGBUFFER_EMPTY_SAMPLE_COUNT] = 0
    with (
        pytest.raises(DeviceError, match="timed out"),
        LaserDock(transport, clock=clock, sleep=clock.sleep) as dock,
    ):
        dock.start()
        dock.send_samples((Sample(0, 0),))
    assert clock.now == pytest.approx(8.2)
    assert not transport.writes
    assert transport.closed


def test_invalid_buffer_count_fails(transport: FakeTransport) -> None:
    """Reject free-buffer reports that exceed the advertised capacity."""
    transport.values[Command.GET_RINGBUFFER_EMPTY_SAMPLE_COUNT] = 257
    with pytest.raises(DeviceError, match="invalid free buffer"), LaserDock(transport) as dock:
        dock.start()
        dock.send_samples((Sample(0, 0),))
    assert transport.closed


def test_uncertain_enable_cannot_be_retried(transport: FakeTransport) -> None:
    """Require a new device context after output enable fails ambiguously."""
    with LaserDock(transport) as dock:
        transport.fail_command = Command.SET_OUTPUT
        with pytest.raises(DeviceError, match="command failure"):
            dock.start()
        transport.fail_command = None
        with pytest.raises(DeviceError, match="job failed"):
            dock.start()
    assert transport.closed


def test_drain_timeout_prevents_continued_sending(transport: FakeTransport, clock: Clock) -> None:
    """Prevent further output after the final drain times out."""
    with LaserDock(transport, clock=clock, sleep=clock.sleep) as dock:
        dock.start()
        dock.send_samples((Sample(0, 0),))
        transport.values[Command.GET_RINGBUFFER_EMPTY_SAMPLE_COUNT] = 0
        with pytest.raises(DeviceError, match="timed out"):
            dock.wait_until_idle()
        with pytest.raises(DeviceError, match="failed"):
            dock.send_samples((Sample(0, 0),))
    assert len(transport.writes) == 1
    assert transport.closed
