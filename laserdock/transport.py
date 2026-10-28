"""PyUSB adapter for the original USB LaserDock (VID 1fc9, PID 04d8)."""

from collections.abc import Iterable, Sequence
from typing import Protocol, cast

from laserdock.protocol import CONTROL_PACKET_BYTES, DeviceError


class Transport(Protocol):
    """Define connection, command exchange, sample delivery, and cleanup operations."""

    def open(self) -> None:
        """Acquire device resources or clean up a partially opened connection."""

    def exchange(self, request: bytes) -> bytes:
        """Write a command and return its response bytes."""

    def write(self, data: bytes) -> None:
        """Write a complete sample packet or raise on uncertain delivery."""

    def close(self) -> None:
        """Release owned resources, reporting cleanup failures."""


class _UsbEndpoint(Protocol):
    """Describe the PyUSB endpoint attributes used at the untyped library boundary."""

    bEndpointAddress: int
    bmAttributes: int

    def write(self, data: bytes, timeout: int) -> int:
        """Return the number of bytes accepted by the endpoint."""

    def read(self, size: int, timeout: int) -> Sequence[int]:
        """Return the response bytes received from the endpoint."""


class _UsbConfiguration(Protocol):
    """Describe lookup of an interface and alternate setting in a USB configuration."""

    def __getitem__(self, key: tuple[int, int]) -> Iterable[_UsbEndpoint]:
        """Return the endpoints of the selected interface and alternate setting."""


class _UsbDevice(Protocol):
    """Describe the PyUSB device operations owned by this adapter."""

    def is_kernel_driver_active(self, interface: int) -> bool:
        """Return whether a kernel driver currently owns the interface."""

    def detach_kernel_driver(self, interface: int) -> None:
        """Detach a kernel driver before claiming an interface."""

    def attach_kernel_driver(self, interface: int) -> None:
        """Restore a kernel driver detached by this adapter."""

    def set_configuration(self) -> None:
        """Activate the default device configuration."""

    def set_interface_altsetting(self, interface: int, alternate_setting: int) -> None:
        """Select the interface's requested transfer mode."""

    def get_active_configuration(self) -> _UsbConfiguration:
        """Return descriptors for the active USB configuration."""


class UsbTransport:
    """Own the original LaserDock's USB interfaces and bulk endpoints."""

    def __init__(self, timeout_ms: int = 1000) -> None:
        """Set a finite transfer timeout without discovering hardware."""
        if type(timeout_ms) is not int or timeout_ms <= 0:
            raise ValueError("USB timeout must be a positive integer in milliseconds")
        self.timeout_ms = timeout_ms
        self._device: _UsbDevice | None = None
        self._claimed: list[int] = []
        self._detached: list[int] = []
        self._control_out: _UsbEndpoint | None = None
        self._control_in: _UsbEndpoint | None = None
        self._data_out: _UsbEndpoint | None = None

    def open(self) -> None:
        """Discover the device, claim interfaces, and select the bulk alternate setting."""
        import usb.core
        import usb.util

        if self._device is not None:
            raise DeviceError("USB transport is already open")
        try:
            self._device = cast(_UsbDevice | None, usb.core.find(idVendor=0x1FC9, idProduct=0x04D8))
            if self._device is None:
                raise DeviceError("LaserDock not found; check USB connection and device permissions")
            dev = self._device
            for interface in (0, 1):
                try:
                    active = dev.is_kernel_driver_active(interface)
                except NotImplementedError:
                    active = False
                if active:
                    dev.detach_kernel_driver(interface)
                    self._detached.append(interface)
            dev.set_configuration()
            for interface in (0, 1):
                usb.util.claim_interface(dev, interface)
                self._claimed.append(interface)
            # Alternate setting 1 selects bulk data transfers, matching the vendor SDK.
            dev.set_interface_altsetting(interface=1, alternate_setting=1)
            config = dev.get_active_configuration()
            try:
                self._control_out = self._endpoint(config[(0, 0)], 0x01)
                self._control_in = self._endpoint(config[(0, 0)], 0x81)
                self._data_out = self._endpoint(config[(1, 1)], 0x03)
            except KeyError as error:
                raise DeviceError("required USB interface or alternate setting is missing") from error
        except BaseException as error:
            try:
                self.close()
            except Exception as cleanup_error:
                error.add_note(f"USB setup cleanup also failed: {cleanup_error}")
            if isinstance(error, usb.core.USBError):
                raise DeviceError(f"Cannot open LaserDock: {error}") from error
            raise

    @staticmethod
    def _endpoint(interface: Iterable[_UsbEndpoint], address: int) -> _UsbEndpoint:
        """Find the requested bulk endpoint or raise a protocol-specific error."""
        for endpoint in interface:
            if endpoint.bEndpointAddress == address and endpoint.bmAttributes & 3 == 2:
                return endpoint
        raise DeviceError(f"required bulk endpoint {address:#04x} is missing")

    def exchange(self, request: bytes) -> bytes:
        """Send a complete control request and read one response within the timeout."""
        import usb.core

        if self._control_out is None or self._control_in is None:
            raise DeviceError("USB transport is not open")
        try:
            written = self._control_out.write(request, timeout=self.timeout_ms)
            if written != len(request):
                raise DeviceError(f"short control write: {written}/{len(request)} bytes")
            return bytes(self._control_in.read(CONTROL_PACKET_BYTES, timeout=self.timeout_ms))
        except usb.core.USBError as error:
            raise DeviceError(f"USB control transfer failed: {error}") from error

    def write(self, data: bytes) -> None:
        """Send sample bytes once, raising on partial or failed delivery."""
        import usb.core

        if self._data_out is None:
            raise DeviceError("USB transport is not open")
        try:
            written = self._data_out.write(data, timeout=self.timeout_ms)
            if written != len(data):
                raise DeviceError(f"short sample write: {written}/{len(data)} bytes; job aborted")
        except usb.core.USBError as error:
            # A timeout may have accepted some bytes. Retrying could engrave them twice.
            raise DeviceError(f"USB sample transfer failed; job aborted: {error}") from error

    def close(self) -> None:
        """Release all interfaces and restore detached drivers despite individual failures."""
        import usb.util

        if self._device is None:
            return
        dev, self._device = self._device, None
        self._control_out = self._control_in = self._data_out = None
        errors: list[Exception] = []
        for interface in reversed(self._claimed):
            try:
                usb.util.release_interface(dev, interface)
            except Exception as error:
                errors.append(error)
        self._claimed.clear()
        for interface in reversed(self._detached):
            try:
                dev.attach_kernel_driver(interface)
            except Exception as error:
                errors.append(error)
        self._detached.clear()
        try:
            usb.util.dispose_resources(dev)
        except Exception as error:
            errors.append(error)
        if errors:
            raise DeviceError(f"USB resource cleanup failed: {errors}") from errors[0]
