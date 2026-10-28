"""Verify argument handling, dry runs, and command-line execution cleanup."""

from pathlib import Path
from typing import Never

import pytest
from PIL import Image

from laserdock.cli import main
from tests.fakes import FakeTransport


def test_image_dry_run_does_not_open_hardware(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Describe an image job without discovering USB hardware."""
    path = tmp_path / "sample.png"
    Image.new("L", (2, 1), 128).save(path)
    assert main(["image", str(path), "--width", "2", "--height", "1", "--dry-run"]) == 0
    output = capsys.readouterr().out
    assert "2 points" in output
    assert "USB was not opened" in output


@pytest.mark.parametrize("command", ["box", "circle", "gradient"])
def test_pattern_dry_run(command: str, capsys: pytest.CaptureFixture[str]) -> None:
    """Prepare each synthetic pattern without opening a device."""
    assert main([command, "--dry-run"]) == 0
    assert "DAC samples" in capsys.readouterr().out


@pytest.mark.parametrize(
    "arguments",
    [
        ["image", "missing.png"],
        ["box", "--sample-rate", "0"],
        ["box", "--min-seconds", "nan"],
        ["box", "--range-seconds", "inf"],
        ["box", "--passes", "0"],
        ["box", "--usb-timeout-ms", "0"],
        ["gradient", "--width", "0"],
        ["box", "--steps", "1"],
    ],
)
def test_invalid_inputs_fail_before_usb(arguments: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    """Reject invalid arguments before acquiring hardware resources."""
    with pytest.raises(SystemExit) as error:
        main(arguments)
    assert error.value.code == 1
    assert "Error:" in capsys.readouterr().err


def test_empty_image_does_not_open_hardware(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Finish an empty silhouette job without opening a device."""
    path = tmp_path / "white.png"
    Image.new("RGB", (1, 1), "white").save(path)
    assert main(["image", str(path), "--border", "--width", "1", "--height", "1"]) == 0
    assert "No points" in capsys.readouterr().out


def test_cli_real_execution_path_uses_injected_transport(
    transport: FakeTransport, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Execute a complete command using a fake transport and verify cleanup."""
    monkeypatch.setattr("laserdock.transport.UsbTransport", lambda *a: transport)
    assert main(["box", "--steps", "2", "--min-seconds", "0", "--range-seconds", "0.05"]) == 0
    assert len(transport.writes) == 1
    assert transport.closed
    assert "output disabled" in capsys.readouterr().out


def test_cli_handles_keyboard_interrupt(transport: FakeTransport, monkeypatch: pytest.MonkeyPatch) -> None:
    """Translate an interruption into exit status 130 after device cleanup."""
    monkeypatch.setattr("laserdock.transport.UsbTransport", lambda *a: transport)

    def interrupt(*a: object) -> Never:
        """Simulate a user interruption during job execution."""
        raise KeyboardInterrupt()

    monkeypatch.setattr("laserdock.cli.run_job", interrupt)
    assert main(["box", "--steps", "2"]) == 130
    assert transport.closed


def test_bundled_images_prepare_successfully() -> None:
    """Prepare every bundled image through the public command-line interface."""
    for path in Path("img").iterdir():
        assert main(["image", str(path), "--width", "8", "--height", "8", "--dry-run"]) == 0
