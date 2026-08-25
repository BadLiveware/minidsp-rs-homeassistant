"""Tests for miniDSP-rs API models."""

import pytest

from custom_components.minidsp_rs.models import (
    MasterStatus,
    MiniDSPDevice,
    MiniDSPInvalidResponseError,
    MiniDSPVersion,
    StatusSummary,
    parse_devices,
)


def test_device_identity_and_label() -> None:
    """A reliable hardware serial is used as the stable identity."""
    device = MiniDSPDevice(
        url="usb:device",
        product_name="2x4HD",
        version=MiniDSPVersion(hw_id=10, dsp_version=100, serial=965535),
    )

    assert device.identity("http://daemon:5380") == "serial:965535"
    assert device.display_label() == "2x4HD (965535)"
    assert device.available_sources() == ("Analog", "Toslink", "Usb")


def test_unreliable_serial_falls_back_to_scoped_url() -> None:
    """A known invalid serial does not merge unrelated devices."""
    device = MiniDSPDevice(
        url="usb:device",
        product_name=None,
        version=MiniDSPVersion(hw_id=10, dsp_version=100, serial=65535),
    )

    assert device.serial is None
    assert device.identity("http://daemon:5380") == (
        "daemon:http://daemon:5380|device:usb:device"
    )


@pytest.mark.parametrize(
    ("hw_id", "dsp_version", "sources"),
    [
        (14, 100, ("Toslink", "Spdif", "Aesebu", "Rca", "Xlr", "Usb", "Lan")),
        (27, 100, ("Analog", "Toslink", "Spdif", "Usb", "Bluetooth")),
        (32, 100, ("Analog", "Toslink", "Spdif", "Usb", "Hdmi")),
        (99, 100, ()),
    ],
)
def test_source_mapping(
    hw_id: int,
    dsp_version: int,
    sources: tuple[str, ...],
) -> None:
    """Source choices match minidsp-rs hardware mappings."""
    device = MiniDSPDevice(
        url="mock:",
        product_name="Test",
        version=MiniDSPVersion(hw_id, dsp_version, 900001),
    )
    assert device.available_sources() == sources


def test_parse_status() -> None:
    """Status responses become immutable typed data."""
    status = StatusSummary.from_dict(
        {
            "master": {
                "preset": 1,
                "source": "Toslink",
                "volume": -32.5,
                "mute": False,
                "dirac": True,
            },
            "input_levels": [-50, -49.5],
            "output_levels": [-60, -61, -120, -120],
        }
    )

    assert status.master == MasterStatus(1, "Toslink", -32.5, False, True)
    assert status.input_levels == (-50.0, -49.5)


def test_invalid_devices_response() -> None:
    """Malformed API data fails at the client boundary."""
    with pytest.raises(MiniDSPInvalidResponseError):
        parse_devices({"url": "not-an-array"})
