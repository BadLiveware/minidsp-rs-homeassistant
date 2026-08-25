"""Tests for the miniDSP-rs HTTP client."""

from typing import cast
from unittest.mock import AsyncMock

import aiohttp
import pytest

from custom_components.minidsp_rs.api import (
    MiniDSPClient,
    MiniDSPResponseError,
    normalize_base_url,
)
from custom_components.minidsp_rs.models import MasterStatus

DEVICES = [
    {
        "url": "usb:first",
        "product_name": "2x4HD",
        "version": {"hw_id": 10, "dsp_version": 100, "serial": 900001},
    },
    {
        "url": "usb:second",
        "product_name": "Flex",
        "version": {"hw_id": 27, "dsp_version": 100, "serial": 900002},
    },
]
STATUS = {
    "master": {
        "preset": 0,
        "source": "Toslink",
        "volume": -20.0,
        "mute": False,
        "dirac": None,
    },
    "input_levels": [-40.0, -41.0],
    "output_levels": [-50.0, -51.0, -120.0, -120.0],
}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("minidsp.local", "http://minidsp.local:5380"),
        ("http://10.0.0.2:1234/", "http://10.0.0.2:1234"),
        ("https://[::1]/api/", "https://[::1]:5380/api"),
    ],
)
def test_normalize_base_url(value: str, expected: str) -> None:
    """Daemon addresses are normalized consistently."""
    assert normalize_base_url(value) == expected


@pytest.mark.parametrize(
    "value",
    ["ftp://host", "http://user:pass@host", "http://host?query=yes", ""],
)
def test_normalize_base_url_rejects_invalid_values(value: str) -> None:
    """Unsafe or unsupported endpoint forms are rejected."""
    with pytest.raises(ValueError, match="Invalid URL"):
        normalize_base_url(value)


async def test_resolves_current_index_by_serial() -> None:
    """Each update resolves daemon ordering before reading a device."""
    client = MiniDSPClient(
        "http://daemon",
        cast(aiohttp.ClientSession, object()),
        serial=900002,
        device_url="usb:second",
    )
    request = AsyncMock(side_effect=[DEVICES, STATUS])
    client._request_json = request  # type: ignore[method-assign]

    data = await client.async_get_data()

    assert data.device.product_name == "Flex"
    assert data.status.master.volume == -20.0
    assert request.await_args_list[1].args == ("GET", "/devices/1")


async def test_invalid_device_list_is_converted_to_client_error() -> None:
    """Malformed discovery data is exposed as a typed client failure."""
    client = MiniDSPClient(
        "http://daemon",
        cast("aiohttp.ClientSession", object()),
    )
    client._request_json = AsyncMock(  # type: ignore[method-assign]
        return_value={"not": "a list"}
    )

    with pytest.raises(MiniDSPResponseError, match="Device list is not an array"):
        await client.async_get_devices()


async def test_set_master_status_posts_to_resolved_device() -> None:
    """Commands target the freshly resolved device index."""
    client = MiniDSPClient(
        "http://daemon",
        cast(aiohttp.ClientSession, object()),
        serial=900001,
    )
    request = AsyncMock(
        side_effect=[
            DEVICES,
            {
                "preset": 0,
                "source": "Toslink",
                "volume": -25.0,
                "mute": True,
                "dirac": None,
            },
        ]
    )
    client._request_json = request  # type: ignore[method-assign]

    master = await client.async_set_master_status(mute=True)

    assert master == MasterStatus(0, "Toslink", -25.0, True, None)
    assert request.await_args_list[1].args == ("POST", "/devices/0")
    assert request.await_args_list[1].kwargs == {"payload": {"mute": True}}
