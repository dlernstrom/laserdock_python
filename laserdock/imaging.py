"""Image-to-point conversion, independent of USB and burn timing."""

import io
import random
from dataclasses import dataclass
from typing import cast

from PIL import Image, ImageOps

from laserdock.models import MAX_COORDINATE, ImageSettings, Sample


@dataclass(frozen=True)
class PixelGrid:
    """Store normalized engraving intensities in row-major order."""

    width: int
    height: int
    intensities: tuple[float, ...]

    def __post_init__(self) -> None:
        """Validate dimensions, pixel count, and intensity ranges."""
        ImageSettings(self.width, self.height)
        if len(self.intensities) != self.width * self.height:
            raise ValueError("pixel count does not match image dimensions")
        if any(not 0 <= value <= 1 for value in self.intensities):
            raise ValueError("pixel intensities must be between 0 and 1")


def decode_image(data: bytes, settings: ImageSettings) -> PixelGrid:
    """Normalize image orientation, transparency, size, and RGB intensity."""
    with Image.open(io.BytesIO(data)) as source:
        rgba = ImageOps.exif_transpose(source).convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        image = Image.alpha_composite(background, rgba).convert("RGB")
        image = image.resize((settings.width, settings.height), Image.Resampling.LANCZOS)
        # Equal RGB weights preserve the original engraving calibration for color images.
        pixels = cast(tuple[tuple[int, int, int], ...], image.get_flattened_data())
        values = tuple(1 - (r + g + b) / 765 for r, g, b in pixels)
    return PixelGrid(settings.width, settings.height, values)


def _coordinate(position: int, size: int, flip: bool) -> int:
    """Map a raster position onto a possibly flipped projector axis."""
    value = round(position * MAX_COORDINATE / (size - 1)) if size > 1 else MAX_COORDINATE // 2
    return MAX_COORDINATE - value if flip else value


def _border_indices(grid: PixelGrid) -> list[int]:
    """Trace the silhouette envelope: top, right, bottom, left, without duplicates."""
    top: dict[int, int] = {}
    bottom: dict[int, int] = {}
    left: dict[int, int] = {}
    right: dict[int, int] = {}
    for index, intensity in enumerate(grid.intensities):
        if intensity <= 0:
            continue
        x, y = index % grid.width, index // grid.width
        top.setdefault(x, index)
        bottom[x] = index
        left.setdefault(y, index)
        right[y] = index
    outline = [top[x] for x in sorted(top)]
    outline.extend(right[y] for y in sorted(right))
    outline.extend(bottom[x] for x in sorted(bottom, reverse=True))
    outline.extend(left[y] for y in sorted(left, reverse=True))
    return list(dict.fromkeys(outline))


def image_samples(
    grid: PixelGrid, settings: ImageSettings, *, border: bool = False, seed: int | None = None
) -> tuple[Sample, ...]:
    """Create shuffled raster points or an ordered silhouette envelope."""
    if (grid.width, grid.height) != (settings.width, settings.height):
        raise ValueError("grid dimensions do not match image settings")
    if border:
        indices = _border_indices(grid)
    else:
        indices = [i for i, value in enumerate(grid.intensities) if value > 0]
        random.Random(seed).shuffle(indices)
    return tuple(
        Sample(
            x=_coordinate(i % grid.width, grid.width, settings.flip_x),
            y=_coordinate(i // grid.width, grid.height, settings.flip_y),
            intensity=1.0 if border else grid.intensities[i],
        )
        for i in indices
    )
