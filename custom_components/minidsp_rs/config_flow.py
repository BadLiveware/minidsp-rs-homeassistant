"""Config flow for miniDSP-rs."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MiniDSPClient, MiniDSPError, normalize_base_url
from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_URL,
    CONF_PRODUCT_NAME,
    CONF_SERIAL,
    DOMAIN,
    LOGGER,
)
from .models import MiniDSPDevice


class MiniDSPConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle configuration for a miniDSP-rs device."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._base_url: str | None = None
        self._devices: tuple[MiniDSPDevice, ...] = ()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Collect the minidspd endpoint and discover devices."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                base_url = normalize_base_url(user_input[CONF_URL])
            except ValueError:
                errors["base"] = "invalid_url"
            else:
                try:
                    devices = await self._async_discover(base_url)
                except MiniDSPError as err:
                    LOGGER.debug("Unable to discover miniDSP devices: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    if not devices:
                        errors["base"] = "no_devices"
                    else:
                        self._base_url = base_url
                        self._devices = devices
                        if len(devices) == 1:
                            return await self._async_create_entry(devices[0])
                        return await self.async_step_device()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_URL,
                        default=(user_input or {}).get(CONF_URL, "http://minidsp:5380"),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_device(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Select one DSP when the daemon exposes multiple devices."""
        if self._base_url is None or not self._devices:
            return self.async_abort(reason="discovery_expired")

        devices_by_id = {
            device.identity(self._base_url): device for device in self._devices
        }
        errors: dict[str, str] = {}
        if user_input is not None:
            device = devices_by_id.get(user_input[CONF_DEVICE_ID])
            if device is None:
                errors["base"] = "device_not_found"
            else:
                return await self._async_create_entry(device)

        options = [
            selector.SelectOptionDict(value=identity, label=device.display_label())
            for identity, device in devices_by_id.items()
        ]
        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options)
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Update the minidspd endpoint while preserving device identity."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                base_url = normalize_base_url(user_input[CONF_URL])
            except ValueError:
                errors["base"] = "invalid_url"
            else:
                try:
                    devices = await self._async_discover(base_url)
                except MiniDSPError as err:
                    LOGGER.debug("Unable to reconfigure miniDSP endpoint: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    device = _find_configured_device(
                        devices,
                        serial=entry.data.get(CONF_SERIAL),
                        device_url=entry.data.get(CONF_DEVICE_URL),
                    )
                    if device is None:
                        errors["base"] = "device_not_found"
                    else:
                        return self.async_update_reload_and_abort(
                            entry,
                            data_updates=_entry_data(base_url, device),
                        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_URL,
                        default=(user_input or {}).get(
                            CONF_URL,
                            entry.data[CONF_URL],
                        ),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def _async_discover(self, base_url: str) -> tuple[MiniDSPDevice, ...]:
        """Discover devices using Home Assistant's shared HTTP session."""
        client = MiniDSPClient(base_url, async_get_clientsession(self.hass))
        return await client.async_get_devices()

    async def _async_create_entry(self, device: MiniDSPDevice) -> ConfigFlowResult:
        """Create an entry for a discovered DSP."""
        assert self._base_url is not None
        await self.async_set_unique_id(device.identity(self._base_url))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=device.display_label(),
            data=_entry_data(self._base_url, device),
        )


def _find_configured_device(
    devices: tuple[MiniDSPDevice, ...],
    *,
    serial: int | None,
    device_url: str | None,
) -> MiniDSPDevice | None:
    """Find a configured device in a fresh discovery result."""
    for device in devices:
        if serial is not None and device.serial == serial:
            return device
        if serial is None and device.url == device_url:
            return device
    return None


def _entry_data(base_url: str, device: MiniDSPDevice) -> dict[str, Any]:
    """Build persisted config-entry data."""
    return {
        CONF_URL: base_url,
        CONF_DEVICE_ID: device.identity(base_url),
        CONF_DEVICE_URL: device.url,
        CONF_PRODUCT_NAME: device.product_name,
        CONF_SERIAL: device.serial,
    }
