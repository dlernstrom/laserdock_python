"""Verify sample bounds and engraving configuration validation."""

from typing import cast

import pytest

from laserdock.models import BurnSettings, ImageSettings, Sample


@pytest.mark.parametrize(
    "field,value",
    [
        ("x", -1),
        ("x", 4096),
        ("y", 1.5),
        ("x", True),
        ("r", 256),
        ("b", -1),
        ("intensity", -0.1),
        ("intensity", 1.1),
        ("intensity", float("nan")),
        ("intensity", float("inf")),
    ],
)
def test_invalid_sample(field: str, value: int | float) -> None:
    """Reject out-of-range coordinates, colors, and intensities."""
    # Keep invalid runtime values intact while exercising the typed constructor boundary.
    arguments = {"x": 0, "y": 0, field: cast(int, value)}
    with pytest.raises(ValueError):
        Sample(**arguments)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"sample_rate": 0},
        {"sample_rate": 1.5},
        {"travel_samples": 0},
        {"minimum_seconds": -1},
        {"intensity_seconds": float("nan")},
        {"minimum_seconds": float("inf")},
        {"minimum_seconds": 0, "intensity_seconds": 0},
        {"minimum_seconds": 1e308},
    ],
)
def test_invalid_burn_settings(kwargs: dict[str, int | float]) -> None:
    """Reject invalid sample rates, travel counts, and dwell durations."""
    with pytest.raises(ValueError):
        BurnSettings(**cast(dict[str, int], kwargs))


def test_calibration_and_nonwhite_quantization() -> None:
    """Preserve calibrated dwell and allocate at least one sample to nonwhite points."""
    settings = BurnSettings()
    assert settings.repeats(Sample(0, 0, intensity=1)) == 70
    assert settings.repeats(Sample(0, 0, intensity=0.5)) == 45
    assert settings.repeats(Sample(0, 0, intensity=0)) == 0
    assert settings.repeats(Sample(0, 0, 0, 0, 0)) == 0
    assert BurnSettings(minimum_seconds=0).repeats(Sample(0, 0, intensity=1e-10)) == 1


@pytest.mark.parametrize("size", [0, -1, 4097, 1.5])
def test_invalid_image_dimensions(size: int | float) -> None:
    """Reject raster dimensions outside the supported integer range."""
    with pytest.raises(ValueError):
        ImageSettings(width=cast(int, size))
