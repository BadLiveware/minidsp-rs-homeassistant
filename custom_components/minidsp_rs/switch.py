"""Switch platform for miniDSP-rs."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .data import MiniDSPConfigEntry
from .entity import MiniDSPEntity


class MiniDSPDiracSwitch(MiniDSPEntity, SwitchEntity):
    """Control Dirac Live processing."""

    _attr_icon = "mdi:tune-vertical"
    _attr_translation_key = "dirac_live"

    def __init__(self, entry: MiniDSPConfigEntry) -> None:
        """Initialize the Dirac Live switch."""
        super().__init__(entry.runtime_data.coordinator, "dirac_live")

    @property
    def is_on(self) -> bool | None:
        """Return whether Dirac Live is enabled."""
        return self.coordinator.data.status.master.dirac

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable Dirac Live."""
        await self.coordinator.async_set_master_status(dirac=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable Dirac Live."""
        await self.coordinator.async_set_master_status(dirac=False)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MiniDSPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Dirac Live when the device reports support."""
    if entry.runtime_data.coordinator.data.status.master.dirac is not None:
        async_add_entities([MiniDSPDiracSwitch(entry)])
