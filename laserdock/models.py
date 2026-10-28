"""Validated values shared by image preparation, planning, and device code."""

import math
from dataclasses import dataclass

MAX_COORDINATE = 4095


def bounded_integer(name: str, value: int, lower: int, upper: int) -> None:
    """Reject nonintegers and values outside the inclusive bounds."""
    if type(value) is not int or not lower <= value <= upper:
        raise ValueError(f"{name} must be an integer between {lower} and {upper}")


def nonnegative_seconds(name: str, value: float) -> None:
    """Reject negative or nonfinite durations."""
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite, nonnegative number")


@dataclass(frozen=True, slots=True)
class Sample:
    """Describe a projector position, RGB color, and normalized engraving intensity."""

    x: int
    y: int
    r: int = 255
    g: int = 255
    b: int = 255
    intensity: float = 1.0

    def __post_init__(self) -> None:
        """Validate coordinate, color, and intensity ranges."""
        for name in ("x", "y"):
            bounded_integer(name, getattr(self, name), 0, MAX_COORDINATE)
        for name in ("r", "g", "b"):
            bounded_integer(name, getattr(self, name), 0, 255)
        if not math.isfinite(self.intensity) or not 0 <= self.intensity <= 1:
            raise ValueError("intensity must be finite and between 0 and 1")


@dataclass(frozen=True, slots=True)
class ImageSettings:
    """Configure raster dimensions and projector axis orientation."""

    width: int = 520
    height: int = 416
    flip_x: bool = True
    flip_y: bool = True

    def __post_init__(self) -> None:
        """Validate the raster dimensions against the projector resolution."""
        bounded_integer("width", self.width, 1, MAX_COORDINATE + 1)
        bounded_integer("height", self.height, 1, MAX_COORDINATE + 1)


@dataclass(frozen=True, slots=True)
class BurnSettings:
    """Configure sample frequency, dwell calibration, and blank travel duration."""

    sample_rate: int = 20
    minimum_seconds: float = 1.0
    intensity_seconds: float = 2.5
    travel_samples: int = 1

    def __post_init__(self) -> None:
        """Validate sampling and dwell values before planning a job."""
        bounded_integer("sample_rate", self.sample_rate, 1, 0xFFFFFFFF)
        bounded_integer("travel_samples", self.travel_samples, 1, 65535)
        nonnegative_seconds("minimum_seconds", self.minimum_seconds)
        nonnegative_seconds("intensity_seconds", self.intensity_seconds)
        if self.minimum_seconds + self.intensity_seconds == 0:
            raise ValueError("at least one dwell time must be positive")
        if not math.isfinite((self.minimum_seconds + self.intensity_seconds) * self.sample_rate):
            raise ValueError("dwell time multiplied by sample rate must be finite")

    def repeats(self, sample: Sample) -> int:
        """Return the lit sample count, skipping blank or zero-intensity points."""
        if sample.intensity == 0 or not (sample.r or sample.g or sample.b):
            return 0
        seconds = self.minimum_seconds + sample.intensity * self.intensity_seconds
        return max(1, int(seconds * self.sample_rate))
