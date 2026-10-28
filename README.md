# LaserDock engraving

A Python application for engraving raster images and calibration patterns with an
original USB LaserDock / LaserCube (`1fc9:04d8`). Run commands from this checkout
with `python -m laserdock`.

## Setup

Use Python 3.14 or newer and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --locked
uv run python -m laserdock --help
```

`pyproject.toml` defines application dependencies and development tools; `uv.lock`
records exact versions. The application runs directly from the repository. For a
runtime-only environment, use `uv sync --locked --no-dev`.

Hardware access also requires a system libusb backend:

```sh
# macOS
brew install libusb

# Raspberry Pi OS / Debian
sudo apt-get install libusb-1.0-0
```

On Linux, give your account access to this device with an appropriate udev rule.
For example, create `/etc/udev/rules.d/70-laserdock.rules` with:

```text
SUBSYSTEM=="usb", ATTR{idVendor}=="1fc9", ATTR{idProduct}=="04d8", MODE="0660", GROUP="plugdev"
```

Ensure the `plugdev` group exists and your user belongs to it, reload udev rules,
then reconnect the device and log in again after any group membership change.
Run the application in its virtual environment as your normal user.

## Commands

Inspect a job without opening USB:

```sh
uv run python -m laserdock image img/power_armor.jpg --dry-run --seed 42
```

Engrave an image:

```sh
uv run python -m laserdock image img/power_armor.jpg
uv run python -m laserdock image img/halloween2019.png --min-seconds 0 --range-seconds 3
```

Trace an image's silhouette envelope, or draw an alignment pattern:

```sh
uv run python -m laserdock image img/power_armor.jpg --border --min-seconds 0 --range-seconds 0.05 --passes 10
uv run python -m laserdock box --steps 100 --min-seconds 0 --range-seconds 0.05
uv run python -m laserdock circle --steps 100 --min-seconds 0 --range-seconds 0.05
```

Generate a calibration gradient or reuse prepared image data:

```sh
uv run python -m laserdock gradient --width 20 --height 20 --dry-run
uv run python -m laserdock image img/power_armor.jpg --cache-dir .laserdock-cache --dry-run
```

Each subcommand supports `--help`. Commands access hardware unless `--dry-run` is
specified; an empty image finishes without opening a device. Ctrl-C aborts the job
and attempts to disable output and clear queued samples.

## Image and timing settings

- Images are resized to `--width 520 --height 416` by default. This stretches the
  image to the selected grid; prepare a matching aspect ratio when proportions matter.
- EXIF orientation is applied. Transparent regions are composited onto white.
  Grayscale and RGB pixels use the same intensity scale. White pixels are skipped.
- Image points span projector coordinates `0..4095`. Both axes are flipped by
  default; `--no-flip-x` and `--no-flip-y` control orientation. Box and circle
  patterns use projector coordinates directly.
- Raster points are shuffled to spread heating. `--seed` makes ordering
  reproducible. Each pass repeats the same order.
- `--border` follows the top, right, bottom, and left silhouette envelope of
  nonwhite pixels at full intensity. It does not trace holes or separate contours.
- Dwell is `minimum_seconds + intensity * range_seconds`. Defaults are 1 second
  minimum, 2.5 additional seconds at full intensity, and 20 DAC samples per second.
  Dwell is rounded down to whole DAC samples, with at least one sample for a
  nonwhite point. These values require calibration for the material and device.
- `--travel-samples` adds blank samples before each point and at job completion
  (default 1). Their duration is included in the estimate. Settling behavior on
  real hardware still needs qualification.
- `--passes` is a positive, finite count. Estimates include all passes and blank
  samples; USB overhead and device startup can add elapsed time.

The optional cache is keyed by image bytes, image settings, and processing schema.
Changing a source image or settings produces a different entry. Invalid entries
are rebuilt; writes replace entries atomically. Cache files can be deleted freely.

## Application structure

```text
laserdock/
  __main__.py    python -m laserdock entry point
  cli.py         arguments, planning, and execution
  models.py      validated samples and settings
  imaging.py     image normalization and coordinate mapping
  patterns.py    box, circle, and gradient point sources
  cache.py       optional prepared-image cache
  jobs.py        dwell expansion, blank travel, packets, and pacing
  protocol.py    command IDs and wire encoding/decoding
  device.py      device commands, flow control, and output lifecycle
  transport.py   PyUSB discovery, transfers, and resource ownership
tests/           hardware-free unit and integration tests
img/             example source images
```

Image preparation and job planning do not open USB. `LaserDock` takes an injected
transport; job execution takes a sample sink and injectable clock. A device context
opens with output disabled, validates buffer sizes and sample rate, and enables
output only when a job starts. Execution sends the final partial packet and waits
for the device buffer to drain before shutdown. Shutdown attempts output disable,
buffer clear, interface release, and restoration of detached kernel drivers.

Transfer failures abort visibly. There is no automatic retry or resume because a
failed transfer can have delivered some samples already. Shutdown failures are
reported and do not replace an existing job exception. A disconnected device may
not accept shutdown commands.

The USB implementation uses control endpoints `0x01/0x81` and bulk sample endpoint
`0x03` on interface 1, alternate setting 1, following the
[manufacturer's USB driver](https://github.com/Wickedlasers/laserdocklib/blob/master/lib/src/LaserdockDevice.cpp).
Responses contain a command byte, status byte, and little-endian values beginning
at byte 2. Device rates and buffer sizes use 32-bit values.

## Development and validation

```sh
uv sync --locked
uv run pytest --cov=laserdock
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

Tests live under `tests/` and block discovery of real USB devices. They cover image
formats, coordinate mapping, cache behavior, timing and packet boundaries,
protocol parsing, simulated transport failures, cleanup, and command-line execution.
CI runs the same checks on Python 3.14. The `.python-version` file selects Python
3.14 for local development. Ruff enforces PEP 8 style checks, PEP 257 docstrings,
function annotations, and a 120-character line limit across application and test
code. Mypy checks application and test code in strict mode; PyUSB's untyped API is isolated
behind typed transport protocols.

Hardware-free checks cannot establish USB timing, beam blanking, scanner settling,
firmware buffer behavior, or material calibration on an actual LaserDock. Validate
those on the target hardware before relying on engraving results.
