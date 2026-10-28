"""Command-line application. Hardware is opened only after a complete plan is ready."""

import argparse
import logging
from pathlib import Path

from PIL import UnidentifiedImageError

from laserdock import patterns
from laserdock.cache import load_image
from laserdock.imaging import image_samples
from laserdock.jobs import BurnPlan, run_job
from laserdock.models import BurnSettings, ImageSettings
from laserdock.protocol import DeviceError


def argument_parser() -> argparse.ArgumentParser:
    """Build the image and calibration command parsers."""
    parser = argparse.ArgumentParser(description="Engrave images and patterns using a USB LaserDock")
    commands = parser.add_subparsers(dest="command", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--sample-rate", type=int, default=20, help="DAC samples per second (default: 20)")
    common.add_argument("--min-seconds", type=float, default=1.0, help="minimum dwell per nonwhite point")
    common.add_argument("--range-seconds", type=float, default=2.5, help="additional dwell at full intensity")
    common.add_argument("--travel-samples", type=int, default=1, help="blank samples before each point")
    common.add_argument("--passes", type=int, default=1, help="number of complete passes")
    common.add_argument("--dry-run", action="store_true", help="describe the plan without opening USB")
    common.add_argument("--usb-timeout-ms", type=int, default=1000)
    image_common = argparse.ArgumentParser(add_help=False)
    image_common.add_argument("--width", type=int, default=520, help="horizontal point count")
    image_common.add_argument("--height", type=int, default=416, help="vertical point count")
    image_common.add_argument("--no-flip-x", action="store_true")
    image_common.add_argument("--no-flip-y", action="store_true")
    image_common.add_argument("--seed", type=int, help="seed for reproducible pixel ordering")
    image = commands.add_parser("image", parents=[common, image_common], help="engrave an image")
    image.add_argument("path", type=Path)
    image.add_argument("--border", action="store_true", help="trace the image's silhouette envelope")
    image.add_argument("--cache-dir", type=Path, help="optional prepared-image cache directory")
    commands.add_parser("gradient", parents=[common, image_common], help="burn a calibration gradient")
    for name in ("box", "circle"):
        pattern = commands.add_parser(name, parents=[common], help=f"draw an alignment {name}")
        pattern.add_argument("--steps", type=int, default=100, help="points per edge or revolution")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Prepare and execute a requested job, returning its process exit status."""
    parser = argument_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    try:
        settings = BurnSettings(args.sample_rate, args.min_seconds, args.range_seconds, args.travel_samples)
        if args.usb_timeout_ms <= 0:
            raise ValueError("USB timeout must be positive")
        if args.command in ("image", "gradient"):
            image_settings = ImageSettings(args.width, args.height, not args.no_flip_x, not args.no_flip_y)
            if args.command == "image":
                grid = load_image(args.path, image_settings, args.cache_dir)
            else:
                grid = patterns.gradient(args.width, args.height)
            points = image_samples(grid, image_settings, border=getattr(args, "border", False), seed=args.seed)
        else:
            pattern = patterns.box if args.command == "box" else patterns.circle
            points = pattern(args.steps)
        plan = BurnPlan(points, settings, args.passes)
        print(
            f"{plan.point_count:,} points; {plan.sample_count:,} DAC samples; "
            f"estimated output time {plan.duration_seconds:.2f} seconds",
            flush=True,
        )
        if args.dry_run:
            print("Dry run: USB was not opened.")
            return 0
        if not plan.sample_count:
            print("No points to engrave.")
            return 0
        from laserdock.device import LaserDock
        from laserdock.transport import UsbTransport

        with LaserDock(UsbTransport(args.usb_timeout_ms), settings.sample_rate) as dock:
            run_job(plan, dock)
        print("Job complete; output disabled.")
        return 0
    except KeyboardInterrupt:
        print("Job interrupted; device shutdown attempted.")
        return 130
    except (DeviceError, OSError, ValueError, UnidentifiedImageError) as error:
        parser.exit(1, f"Error: {error}\n")
