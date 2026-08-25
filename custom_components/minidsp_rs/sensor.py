"""Diagnostic level sensors for miniDSP-rs."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .data import MiniDSPConfigEntry
from .entity import MiniDSPEntity


class MiniDSPLevelSensor(MiniDSPEntity, SensorEntity):
    """Represent one input or output signal level."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_native_unit_of_measurement = "dBFS"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        entry: MiniDSPConfigEntry,
        level_type: str,
        channel: int,
    ) -> None:
        """Initialize a signal-level sensor."""
        super().__init__(
            entry.runtime_data.coordinator,
            f"{level_type}_level_{channel + 1}",
        )
        self._level_type = level_type
        self._channel = channel
        self._attr_translation_key = f"{level_type}_level"
        self._attr_translation_placeholders = {"channel": str(channel + 1)}

    @property
    def native_value(self) -> float | None:
        """Return the latest channel level."""
        status = self.coordinator.data.status
        levels = (
            status.input_levels if self._level_type == "input" else status.output_levels
        )
        if self._channel >= len(levels):
            return None
        return round(levels[self._channel], 1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MiniDSPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up input and output signal-level sensors."""
    status = entry.runtime_data.coordinator.data.status
    entities = [
        MiniDSPLevelSensor(entry, "input", channel)
        for channel in range(len(status.input_levels))
    ]
    entities.extend(
        MiniDSPLevelSensor(entry, "output", channel)
        for channel in range(len(status.output_levels))
    )
    async_add_entities(entities)
