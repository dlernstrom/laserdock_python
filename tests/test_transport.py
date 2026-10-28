"""Verify USB endpoint selection, transfer failures, and resource cleanup."""

from types import SimpleNamespace
from typing import Never

import pytest
import usb.core

from laserdock.protocol import DeviceError
from laserdock.transport import UsbTransport


class Endpoint:
    """Record endpoint transfers and simulate short writes or USB errors."""

    bmAttributes = 2

    def __init__(self, address: int) -> None:
        """Initialize endpoint identity and configurable delivery outcomes."""
        self.bEndpointAddress = address
        self.writes: list[tuple[bytes, int]] = []
        self.result: int | None = None
        self.error: Exception | None = None

    def write(self, data: bytes, timeout: int) -> int:
        """Record one write and return a configured byte count or error."""
        self.writes.append((data, timeout))
        if self.error:
            raise self.error
        return len(data) if self.result is None else self.result

    def read(self, size: int, timeout: int) -> bytes:
        """Return a zero-filled response of the requested length."""
        return bytes(size)


type UsbFixture = tuple[
    SimpleNamespace,
    list[Endpoint],
    list[tuple[object, ...]],
    dict[tuple[int, int], list[Endpoint]],
]


@pytest.fixture
def usb_device(monkeypatch: pytest.MonkeyPatch) -> UsbFixture:
    """Provide fake endpoints, descriptors, and a record of USB ownership operations."""
    events: list[tuple[object, ...]] = []
    endpoints = [Endpoint(0x01), Endpoint(0x81), Endpoint(0x03)]
    config = {(0, 0): endpoints[:2], (1, 1): endpoints[2:]}

    def kernel_status(interface: int) -> bool:
        """Simulate unsupported driver queries for one interface and an active driver for another."""
        if interface == 0:
            raise NotImplementedError()
        return True

    device = SimpleNamespace(
        is_kernel_driver_active=kernel_status,
        detach_kernel_driver=lambda i: events.append(("detach", i)),
        attach_kernel_driver=lambda i: events.append(("attach", i)),
        set_configuration=lambda: events.append(("configure",)),
        set_interface_altsetting=lambda **kw: events.append(("alt", kw)),
        get_active_configuration=lambda: config,
    )
    monkeypatch.setattr("usb.core.find", lambda **kw: device)
    monkeypatch.setattr("usb.util.claim_interface", lambda d, i: events.append(("claim", i)))
    monkeypatch.setattr("usb.util.release_interface", lambda d, i: events.append(("release", i)))
    monkeypatch.setattr("usb.util.dispose_resources", lambda d: events.append(("dispose",)))
    return device, endpoints, events, config


def test_bulk_alternate_setting_endpoints_timeout_and_resource_cleanup(usb_device: UsbFixture) -> None:
    """Use bulk endpoints with finite timeouts and restore owned resources."""
    _, endpoints, events, _ = usb_device
    transport = UsbTransport(timeout_ms=250)
    transport.open()
    assert ("alt", {"interface": 1, "alternate_setting": 1}) in events
    assert transport.exchange(b"\x81") == bytes(64)
    transport.write(b"12345678")
    assert endpoints[0].writes == [(b"\x81", 250)]
    assert endpoints[2].writes == [(b"12345678", 250)]
    transport.close()
    assert events[-4:] == [("release", 1), ("release", 0), ("attach", 1), ("dispose",)]
    transport.close()


def test_missing_device_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """Report device absence without attempting transfers."""
    monkeypatch.setattr("usb.core.find", lambda **kw: None)
    with pytest.raises(DeviceError, match="not found"):
        UsbTransport().open()


def test_wrong_endpoint_type_is_rejected_and_setup_is_cleaned_up(usb_device: UsbFixture) -> None:
    """Reject an isochronous endpoint and release partially acquired resources."""
    _, endpoints, events, _ = usb_device
    endpoints[2].bmAttributes = 1
    with pytest.raises(DeviceError, match="bulk endpoint"):
        UsbTransport().open()
    assert events[-1] == ("dispose",)
    assert ("attach", 1) in events


@pytest.mark.parametrize("operation,endpoint", [("exchange", 0), ("write", 2)])
def test_short_writes_are_errors(usb_device: UsbFixture, operation: str, endpoint: int) -> None:
    """Report partial command and sample writes as transfer failures."""
    _, endpoints, _, _ = usb_device
    transport = UsbTransport()
    transport.open()
    endpoints[endpoint].result = 1
    with pytest.raises(DeviceError, match="short"):
        getattr(transport, operation)(b"12345678")
    transport.close()


def test_usb_failure_is_not_retried(usb_device: UsbFixture) -> None:
    """Surface a USB write error after exactly one delivery attempt."""
    _, endpoints, _, _ = usb_device
    transport = UsbTransport()
    transport.open()
    endpoints[2].error = usb.core.USBError("timeout")
    with pytest.raises(DeviceError, match="job aborted"):
        transport.write(b"12345678")
    assert len(endpoints[2].writes) == 1
    transport.close()


def test_cleanup_continues_after_release_failure(usb_device: UsbFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Restore detached drivers and dispose resources even when release fails."""
    _, _, events, _ = usb_device
    transport = UsbTransport()
    transport.open()

    def fail(device: object, interface: int) -> Never:
        """Simulate interface release failure during transport cleanup."""
        raise usb.core.USBError("release failed")

    monkeypatch.setattr("usb.util.release_interface", fail)
    with pytest.raises(DeviceError, match="cleanup failed"):
        transport.close()
    assert events[-2:] == [("attach", 1), ("dispose",)]


def test_closed_transport_rejects_io() -> None:
    """Reject command and sample transfers before the transport is opened."""
    transport = UsbTransport()
    with pytest.raises(DeviceError, match="not open"):
        transport.write(b"test")
    with pytest.raises(DeviceError, match="not open"):
        transport.exchange(b"test")


def test_missing_interface_is_reported_and_releases_resources(usb_device: UsbFixture) -> None:
    """Report missing interface descriptors and release claimed resources."""
    _, _, events, config = usb_device
    del config[(1, 1)]
    with pytest.raises(DeviceError, match="interface or alternate setting"):
        UsbTransport().open()
    assert events[-1] == ("dispose",)
