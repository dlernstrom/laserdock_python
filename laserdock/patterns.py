"""Synthetic point sources for alignment and calibration."""

import math

from laserdock.imaging import PixelGrid
from laserdock.models import MAX_COORDINATE, Sample, bounded_integer


def box(steps: int = 100) -> tuple[Sample, ...]:
    """Return an ordered rectangle spanning the projector coordinate range."""
    bounded_integer("steps", steps, 2, 4096)
    edge = [round(i * MAX_COORDINATE / (steps - 1)) for i in range(steps)]
    points = [(x, 0) for x in edge]
    points.extend((MAX_COORDINATE, y) for y in edge[1:])
    points.extend((x, MAX_COORDINATE) for x in reversed(edge[:-1]))
    points.extend((0, y) for y in reversed(edge[1:-1]))
    return tuple(Sample(x, y) for x, y in points)


def circle(steps: int = 100) -> tuple[Sample, ...]:
    """Return evenly spaced points around an inscribed alignment circle."""
    bounded_integer("steps", steps, 3, 65535)
    return tuple(
        Sample(
            round(MAX_COORDINATE * (1 + math.cos(2 * math.pi * i / steps)) / 2),
            round(MAX_COORDINATE * (1 + math.sin(2 * math.pi * i / steps)) / 2),
        )
        for i in range(steps)
    )


def gradient(width: int, height: int) -> PixelGrid:
    """Return a diagonal white-to-black grid for dwell calibration."""
    denominator = max(1, width + height - 2)
    return PixelGrid(
        width,
        height,
        tuple((x + y) / denominator for y in range(height) for x in range(width)),
    )
