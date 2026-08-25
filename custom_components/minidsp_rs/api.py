"""Async client for the minidsp-rs HTTP API."""

from __future__ import annotations

import asyncio
import json
import socket
from http import HTTPStatus
from typing import Any
from urllib.parse import SplitResult, urlsplit, urlunsplit

import aiohttp

from .const import DEFAULT_PORT
from .models import (
    MasterStatus,
    MiniDSPData,
    MiniDSPDevice,
    MiniDSPInvalidResponseError,
    StatusSummary,
    parse_devices,
)

REQUEST_TIMEOUT = 10


class MiniDSPError(Exception):
    """Base exception for miniDSP-rs client errors."""


class MiniDSPConnectionError(MiniDSPError):
    """Raised when minidspd cannot be reached."""


class MiniDSPDeviceNotFoundError(MiniDSPError):
    """Raised when a configured DSP is no longer listed by minidspd."""


class MiniDSPResponseError(MiniDSPError):
    """Raised when minidspd returns an invalid response."""


def normalize_base_url(value: str) -> str:
    """Normalize and validate a minidspd base URL."""
    candidate = value.strip()
    if "://" not in candidate:
        candidate = f"http://{candidate}"
    try:
        parsed = urlsplit(candidate)
        port = parsed.port or DEFAULT_PORT
    except ValueError as err:
        raise ValueError("Invalid URL") from err
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Invalid URL")

    host = parsed.hostname
    if ":" in host:
        host = f"[{host}]"
    path = parsed.path.rstrip("/")
    return urlunsplit(SplitResult(parsed.scheme, f"{host}:{port}", path, "", ""))


class MiniDSPClient:
    """Client for one DSP exposed by a minidspd instance."""

    def __init__(
        self,
        base_url: str,
        session: aiohttp.ClientSession,
        *,
        serial: int | None = None,
        device_url: str | None = None,
    ) -> None:
        """Initialize the client."""
        self.base_url = normalize_base_url(base_url)
        self._session = session
        self._serial = serial
        self._device_url = device_url

    async def async_get_devices(self) -> tuple[MiniDSPDevice, ...]:
        """Return all devices currently listed by minidspd."""
        try:
            return parse_devices(await self._request_json("GET", "/devices"))
        except MiniDSPInvalidResponseError as err:
            raise MiniDSPResponseError(str(err)) from err

    async def async_get_data(self) -> MiniDSPData:
        """Resolve the configured device and fetch its status."""
        index, device = await self._async_resolve_device()
        value = await self._request_json("GET", f"/devices/{index}")
        try:
            status = StatusSummary.from_dict(value)
        except MiniDSPInvalidResponseError as err:
            raise MiniDSPResponseError(str(err)) from err
        return MiniDSPData(device=device, status=status)

    async def async_set_master_status(self, **changes: object) -> MasterStatus:
        """Apply master-control changes and return the resulting status."""
        index, _device = await self._async_resolve_device()
        value = await self._request_json(
            "POST",
            f"/devices/{index}",
            payload=changes,
        )
        try:
            return MasterStatus.from_dict(value)
        except MiniDSPInvalidResponseError as err:
            raise MiniDSPResponseError(str(err)) from err

    async def _async_resolve_device(self) -> tuple[int, MiniDSPDevice]:
        """Resolve the current daemon index without trusting stale ordering."""
        devices = await self.async_get_devices()
        for index, device in enumerate(devices):
            if self._serial is not None and device.serial == self._serial:
                return index, device
            if self._serial is None and self._device_url == device.url:
                return index, device
        raise MiniDSPDeviceNotFoundError("Configured DSP was not found")

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        payload: dict[str, object] | None = None,
    ) -> Any:
        """Make an API request and decode its JSON response."""
        url = f"{self.base_url}{path}"
        try:
            async with asyncio.timeout(REQUEST_TIMEOUT):
                async with self._session.request(method, url, json=payload) as response:
                    if response.status != HTTPStatus.OK:
                        await response.read()
                        raise MiniDSPConnectionError(
                            f"minidspd returned HTTP {response.status}"
                        )
                    try:
                        return await response.json()
                    except (aiohttp.ContentTypeError, json.JSONDecodeError) as err:
                        raise MiniDSPResponseError(
                            "minidspd returned invalid JSON"
                        ) from err
        except MiniDSPError:
            raise
        except TimeoutError as err:
            raise MiniDSPConnectionError(
                "Timed out communicating with minidspd"
            ) from err
        except (aiohttp.ClientError, socket.gaierror) as err:
            raise MiniDSPConnectionError("Unable to communicate with minidspd") from err
