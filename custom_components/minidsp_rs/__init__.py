"""Home Assistant integration for miniDSP-rs."""

from __future__ import annotations

from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MiniDSPClient
from .const import CONF_DEVICE_URL, CONF_SERIAL
from .coordinator import MiniDSPCoordinator
from .data import MiniDSPConfigEntry, MiniDSPRuntimeData

PLATFORMS = (Platform.MEDIA_PLAYER, Platform.SENSOR, Platform.SWITCH)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MiniDSPConfigEntry,
) -> bool:
    """Set up miniDSP-rs from a config entry."""
    client = MiniDSPClient(
        entry.data[CONF_URL],
        async_get_clientsession(hass),
        serial=entry.data.get(CONF_SERIAL),
        device_url=entry.data.get(CONF_DEVICE_URL),
    )
    coordinator = MiniDSPCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = MiniDSPRuntimeData(client=client, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: MiniDSPConfigEntry,
) -> bool:
    """Unload a miniDSP-rs config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
