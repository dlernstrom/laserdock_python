"""Configure hardware-free pytest fixtures for every test."""

from typing import Never

import pytest

from tests.fakes import Clock, FakeTransport


@pytest.fixture(autouse=True)
def block_real_usb(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject device discovery unless a test explicitly replaces it with a fake."""

    def forbidden(*args: object, **kwargs: object) -> Never:
        """Fail immediately if a test attempts to discover real hardware."""
        pytest.fail("Tests must not discover or open real USB devices")

    monkeypatch.setattr("usb.core.find", forbidden)


@pytest.fixture
def clock() -> Clock:
    """Return a fresh clock for deterministic packet timing checks."""
    return Clock()


@pytest.fixture
def transport() -> FakeTransport:
    """Return a fresh transport with configurable responses and failures."""
    return FakeTransport()
