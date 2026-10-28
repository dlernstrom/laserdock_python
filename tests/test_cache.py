"""Verify content-addressed image caching and corruption recovery."""

import io
import json
from pathlib import Path

import pytest
from PIL import Image

from laserdock.cache import load_image
from laserdock.models import ImageSettings


def write_image(path: Path, color: int) -> None:
    """Write a small grayscale fixture with the requested uniform intensity."""
    output = io.BytesIO()
    Image.new("L", (2, 1), color).save(output, format="PNG")
    path.write_bytes(output.getvalue())


def test_cache_hit_uses_prepared_grid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reuse a valid cache entry without decoding the image again."""
    path = tmp_path / "image.png"
    write_image(path, 128)
    directory = tmp_path / "cache"
    first = load_image(path, ImageSettings(2, 1), directory)
    monkeypatch.setattr("laserdock.cache.decode_image", lambda *a: (_ for _ in ()).throw(AssertionError()))
    assert load_image(path, ImageSettings(2, 1), directory) == first


def test_cache_invalidated_by_content_and_settings(tmp_path: Path) -> None:
    """Create distinct entries when image bytes or processing dimensions change."""
    path = tmp_path / "image.png"
    directory = tmp_path / "cache"
    write_image(path, 0)
    assert load_image(path, ImageSettings(2, 1), directory).intensities == (1, 1)
    write_image(path, 255)
    assert load_image(path, ImageSettings(2, 1), directory).intensities == (0, 0)
    assert load_image(path, ImageSettings(1, 1), directory).intensities == (0,)
    assert len(list(directory.glob("*.json"))) == 3


def test_corrupt_cache_is_rebuilt(tmp_path: Path) -> None:
    """Rebuild malformed entries and leave no temporary cache files."""
    path = tmp_path / "image.png"
    directory = tmp_path / "cache"
    write_image(path, 0)
    grid = load_image(path, ImageSettings(2, 1), directory)
    (cached,) = directory.glob("*.json")
    for invalid in ("not JSON", "[]", '{"metadata":{}}'):
        cached.write_text(invalid)
        assert load_image(path, ImageSettings(2, 1), directory) == grid
        assert len(json.loads(cached.read_text())["intensities"]) == 2
    assert len(list(directory.iterdir())) == 1


def test_cache_is_optional(tmp_path: Path) -> None:
    """Prepare an image without creating cache files when caching is disabled."""
    path = tmp_path / "image.png"
    write_image(path, 0)
    assert load_image(path, ImageSettings(2, 1)).intensities == (1, 1)
    assert list(tmp_path.iterdir()) == [path]
