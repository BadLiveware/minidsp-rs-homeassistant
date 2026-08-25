"""Data models for the minidsp-rs HTTP API."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from .const import DEFAULT_NAME

# Some devices temporarily report this value when their real serial is unavailable.
UNRELIABLE_SERIALS = {0, 65535}


class MiniDSPInvalidResponseError(ValueError):
    """Raised when minidspd returns an unexpected response."""


@dataclass(frozen=True, slots=True)
class MiniDSPVersion:
    """Hardware information reported by minidspd."""

    hw_id: int
    dsp_version: int
    serial: int

    @classmethod
    def from_dict(cls, value: object) -> MiniDSPVersion | None:
        """Create hardware information from an API value."""
        if value is None:
            return None
        if not isinstance(value, dict):
            raise MiniDSPInvalidResponseError("Device version is not an object")
        try:
            return cls(
                hw_id=int(value["hw_id"]),
                dsp_version=int(value["dsp_version"]),
                serial=int(value["serial"]),
            )
        except (KeyError, TypeError, ValueError) as err:
            raise MiniDSPInvalidResponseError(
                "Device version is missing required fields"
            ) from err

    @property
    def has_reliable_serial(self) -> bool:
        """Return whether the serial can safely identify the device."""
        return self.serial not in UNRELIABLE_SERIALS


@dataclass(frozen=True, slots=True)
class MiniDSPDevice:
    """A device discovered by minidspd."""

    url: str
    product_name: str | None
    version: MiniDSPVersion | None

    @classmethod
    def from_dict(cls, value: object) -> MiniDSPDevice:
        """Create a device from an API value."""
        if not isinstance(value, dict):
            raise MiniDSPInvalidResponseError("Device is not an object")
        url = value.get("url")
        if not isinstance(url, str) or not url:
            raise MiniDSPInvalidResponseError("Device URL is missing")
        product_name = value.get("product_name")
        if product_name is not None and not isinstance(product_name, str):
            raise MiniDSPInvalidResponseError("Product name is not a string")
        return cls(
            url=url,
            product_name=product_name,
            version=MiniDSPVersion.from_dict(value.get("version")),
        )

    @property
    def name(self) -> str:
        """Return the device display name."""
        return self.product_name or DEFAULT_NAME

    @property
    def serial(self) -> int | None:
        """Return a reliable serial number when available."""
        if self.version is None or not self.version.has_reliable_serial:
            return None
        return self.version.serial

    def identity(self, base_url: str) -> str:
        """Return a stable config-entry identity for this device."""
        if self.serial is not None:
            return f"serial:{self.serial}"
        return f"daemon:{base_url}|device:{self.url}"

    def display_label(self) -> str:
        """Return a human-readable config-flow label."""
        if self.serial is not None:
            return f"{self.name} ({self.serial})"
        return f"{self.name} ({self.url})"

    def available_sources(self) -> tuple[str, ...]:
        """Return the input sources supported by this hardware revision.

        The mapping follows minidsp-rs' protocol source mapping. Keeping it local
        prevents users from selecting sources that the daemon would silently map
        to the first input.
        """
        if self.version is None:
            return ()
        hw_id = self.version.hw_id
        dsp_version = self.version.dsp_version
        if hw_id in (2, 11):
            return ("Toslink", "Spdif")
        if hw_id in (1, 4, 5):
            return ("Spdif", "Toslink", "Aesebu")
        if hw_id == 10:
            first = "Analog" if dsp_version in (100, 101) else "I2S"
            return (first, "Toslink", "Usb")
        if hw_id == 14:
            return ("Toslink", "Spdif", "Aesebu", "Rca", "Xlr", "Usb", "Lan")
        if hw_id in (17, 18):
            return ("Toslink", "Spdif", "Aesebu", "Usb", "Lan")
        if hw_id == 27:
            return ("Analog", "Toslink", "Spdif", "Usb", "Bluetooth")
        if hw_id == 32:
            return ("Analog", "Toslink", "Spdif", "Usb", "Hdmi")
        return ()


@dataclass(frozen=True, slots=True)
class MasterStatus:
    """Master controls reported by minidspd."""

    preset: int | None = None
    source: str | None = None
    volume: float | None = None
    mute: bool | None = None
    dirac: bool | None = None

    @classmethod
    def from_dict(cls, value: object) -> MasterStatus:
        """Create master status from an API value."""
        if not isinstance(value, dict):
            raise MiniDSPInvalidResponseError("Master status is not an object")
        return cls(
            preset=_optional_int(value.get("preset")),
            source=_optional_str(value.get("source")),
            volume=_optional_float(value.get("volume")),
            mute=_optional_bool(value.get("mute")),
            dirac=_optional_bool(value.get("dirac")),
        )


@dataclass(frozen=True, slots=True)
class StatusSummary:
    """Status and level data returned for a MiniDSP device."""

    master: MasterStatus
    input_levels: tuple[float, ...]
    output_levels: tuple[float, ...]

    @classmethod
    def from_dict(cls, value: object) -> StatusSummary:
        """Create a status summary from an API value."""
        if not isinstance(value, dict):
            raise MiniDSPInvalidResponseError("Status response is not an object")
        return cls(
            master=MasterStatus.from_dict(value.get("master")),
            input_levels=_float_tuple(value.get("input_levels"), "input_levels"),
            output_levels=_float_tuple(value.get("output_levels"), "output_levels"),
        )

    def with_master(self, master: MasterStatus) -> StatusSummary:
        """Return a copy with updated master controls."""
        return replace(self, master=master)


@dataclass(frozen=True, slots=True)
class MiniDSPData:
    """Coordinator data for one resolved DSP."""

    device: MiniDSPDevice
    status: StatusSummary


def parse_devices(value: object) -> tuple[MiniDSPDevice, ...]:
    """Parse a device-list response."""
    if not isinstance(value, list):
        raise MiniDSPInvalidResponseError("Device list is not an array")
    return tuple(MiniDSPDevice.from_dict(item) for item in value)


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise MiniDSPInvalidResponseError("Expected a boolean value")
    return value


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MiniDSPInvalidResponseError("Expected a numeric value")
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise MiniDSPInvalidResponseError("Expected an integer value")
    return value


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise MiniDSPInvalidResponseError("Expected a string value")
    return value


def _float_tuple(value: object, field: str) -> tuple[float, ...]:
    if not isinstance(value, list):
        raise MiniDSPInvalidResponseError(f"{field} is not an array")
    try:
        if any(isinstance(item, bool) for item in value):
            raise TypeError
        return tuple(float(item) for item in value)
    except (TypeError, ValueError) as err:
        raise MiniDSPInvalidResponseError(f"{field} contains a non-number") from err
