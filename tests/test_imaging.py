"""Verify image normalization, coordinate mapping, and calibration geometry."""

import io
from collections.abc import Callable, Sequence

import pytest
from PIL import Image

from laserdock.imaging import PixelGrid, decode_image, image_samples
from laserdock.models import ImageSettings, Sample
from laserdock.patterns import box, circle, gradient


def image_bytes(mode: str, values: Sequence[int | tuple[int, ...]], size: tuple[int, int] | None = None) -> bytes:
    """Encode a small pixel sequence as an in-memory PNG fixture."""
    image = Image.new(mode, size or (len(values), 1))
    image.putdata(values)
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


@pytest.mark.parametrize(
    "mode,values",
    [
        ("L", [0, 128, 255]),
        ("RGB", [(0, 0, 0), (128, 128, 128), (255, 255, 255)]),
        ("RGBA", [(0, 0, 0, 255), (128, 128, 128, 255), (255, 255, 255, 255)]),
    ],
)
def test_consistent_grayscale(mode: str, values: Sequence[int | tuple[int, ...]]) -> None:
    """Produce equivalent intensities for grayscale, RGB, and opaque RGBA pixels."""
    grid = decode_image(image_bytes(mode, values), ImageSettings(3, 1))
    assert grid.intensities == pytest.approx((1, 1 - 128 / 255, 0))


def test_transparent_pixels_are_white() -> None:
    """Treat fully transparent pixels as unburned white regions."""
    grid = decode_image(image_bytes("RGBA", [(0, 0, 0, 0), (0, 0, 0, 255)]), ImageSettings(2, 1))
    assert grid.intensities == (0, 1)


def test_palette_is_converted_to_rgb() -> None:
    """Resolve palette indices before computing engraving intensity."""
    image = Image.new("P", (2, 1))
    image.putpalette([0, 0, 0, 255, 255, 255] + [0] * 762)
    image.putdata([0, 1])
    output = io.BytesIO()
    image.save(output, format="PNG")
    assert decode_image(output.getvalue(), ImageSettings(2, 1)).intensities == (1, 0)


def test_exif_orientation_is_applied() -> None:
    """Honor image orientation metadata before resizing the raster."""
    image = Image.new("RGB", (2, 1))
    image.putdata([(0, 0, 0), (255, 255, 255)])
    exif = image.getexif()
    exif[274] = 6
    output = io.BytesIO()
    image.save(output, format="PNG", exif=exif)
    assert decode_image(output.getvalue(), ImageSettings(1, 2)).intensities == (1, 0)


@pytest.mark.parametrize("flip", [False, True])
def test_full_projector_range_and_flips(flip: bool) -> None:
    """Map image endpoints across the full projector range with optional flips."""
    settings = ImageSettings(2, 2, flip, flip)
    points = image_samples(PixelGrid(2, 2, (1, 0, 0, 0.5)), settings)
    actual = {(p.x, p.y, p.intensity) for p in points}
    expected = {(4095, 4095, 1), (0, 0, 0.5)} if flip else {(0, 0, 1), (4095, 4095, 0.5)}
    assert actual == expected


def test_single_pixel_and_white_border() -> None:
    """Center a single pixel and return an empty outline for a white image."""
    settings = ImageSettings(1, 1, False, False)
    (point,) = image_samples(PixelGrid(1, 1, (1,)), settings)
    assert (point.x, point.y) == (2047, 2047)
    assert image_samples(PixelGrid(1, 1, (0,)), settings, border=True) == ()


def test_seed_is_reproducible_without_mutating_global_random() -> None:
    """Keep seeded point ordering reproducible and global randomness unchanged."""
    import random

    state = random.getstate()
    settings = ImageSettings(10, 10)
    grid = PixelGrid(10, 10, (1,) * 100)
    assert image_samples(grid, settings, seed=42) == image_samples(grid, settings, seed=42)
    assert image_samples(grid, settings, seed=42) != image_samples(grid, settings, seed=43)
    assert random.getstate() == state


def test_border_follows_envelope_and_excludes_interior() -> None:
    """Trace the ordered silhouette envelope without interior points or duplicates."""
    points = image_samples(PixelGrid(3, 3, (1,) * 9), ImageSettings(3, 3, False, False), border=True)
    assert [(p.x, p.y) for p in points] == [
        (0, 0),
        (2048, 0),
        (4095, 0),
        (4095, 2048),
        (4095, 4095),
        (2048, 4095),
        (0, 4095),
        (0, 2048),
    ]


def test_sparse_border_is_ordered_by_coordinate() -> None:
    """Order sparse silhouette points by coordinate rather than discovery order."""
    points = image_samples(
        PixelGrid(3, 3, (0, 0, 1, 0, 0, 0, 1, 0, 0)),
        ImageSettings(3, 3, False, False),
        border=True,
    )
    assert [(p.x, p.y) for p in points] == [(0, 4095), (4095, 0)]


def test_dimension_mismatch_and_invalid_grid() -> None:
    """Reject inconsistent dimensions, incorrect pixel counts, and invalid intensities."""
    with pytest.raises(ValueError, match="dimensions"):
        image_samples(PixelGrid(1, 1, (1,)), ImageSettings(2, 2))
    with pytest.raises(ValueError, match="pixel count"):
        PixelGrid(2, 2, (1,))
    with pytest.raises(ValueError, match="intensities"):
        PixelGrid(1, 1, (float("nan"),))


def test_patterns_cover_expected_geometry() -> None:
    """Check alignment pattern extents and calibration gradient endpoints."""
    assert len(box(3)) == 8
    assert len(set(box(3))) == 8
    assert {(p.x, p.y) for p in circle(4)} == {(4095, 2048), (2048, 4095), (0, 2048), (2047, 0)}
    grid = gradient(3, 3)
    assert grid.intensities[0] == 0
    assert grid.intensities[-1] == 1
    assert grid.intensities[4] == 0.5


@pytest.mark.parametrize("factory,steps", [(box, 1), (circle, 2)])
def test_invalid_patterns(factory: Callable[[int], tuple[Sample, ...]], steps: int) -> None:
    """Reject pattern resolutions that cannot describe the requested geometry."""
    with pytest.raises(ValueError):
        factory(steps)
