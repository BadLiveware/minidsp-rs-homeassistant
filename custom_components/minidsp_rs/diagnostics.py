"""Diagnostics support for miniDSP-rs."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant

from .const import CONF_DEVICE_ID, CONF_DEVICE_URL, CONF_SERIAL
from .data import MiniDSPConfigEntry

ENTRY_KEYS_TO_REDACT = {
    CONF_URL,
    CONF_DEVICE_ID,
    CONF_DEVICE_URL,
    CONF_SERIAL,
}
DEVICE_KEYS_TO_REDACT = {"serial", "url"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: MiniDSPConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a configured DSP."""
    return {
        "entry": async_redact_data(dict(entry.data), ENTRY_KEYS_TO_REDACT),
        "device": async_redact_data(
            asdict(entry.runtime_data.coordinator.data.device),
            DEVICE_KEYS_TO_REDACT,
        ),
        "status": asdict(entry.runtime_data.coordinator.data.status),
        "last_update_success": entry.runtime_data.coordinator.last_update_success,
    }
