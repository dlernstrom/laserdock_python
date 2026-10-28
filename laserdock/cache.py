"""Optional content-addressed cache of prepared image intensities."""

import hashlib
import json
import logging
import tempfile
from dataclasses import asdict
from pathlib import Path

from laserdock.imaging import PixelGrid, decode_image
from laserdock.models import ImageSettings

logger = logging.getLogger(__name__)
CACHE_VERSION = 1


def load_image(path: Path, settings: ImageSettings, cache_dir: Path | None = None) -> PixelGrid:
    """Prepare an image, optionally reusing an entry keyed by content and settings."""
    data = path.read_bytes()
    if cache_dir is None:
        return decode_image(data, settings)
    metadata = {"version": CACHE_VERSION, "settings": asdict(settings)}
    key = hashlib.sha256(json.dumps(metadata, sort_keys=True).encode() + b"\0" + data).hexdigest()
    cached = cache_dir / f"{key}.json"
    if cached.exists():
        try:
            payload = json.loads(cached.read_text())
            if payload["metadata"] != metadata:
                raise ValueError("cache metadata does not match")
            return PixelGrid(settings.width, settings.height, tuple(payload["intensities"]))
        except ValueError, TypeError, KeyError:
            logger.warning("Rebuilding invalid image cache: %s", cached)
    grid = decode_image(data, settings)
    cache_dir.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=cache_dir, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump({"metadata": metadata, "intensities": grid.intensities}, handle)
        temporary.replace(cached)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return grid
