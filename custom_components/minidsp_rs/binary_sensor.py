"""Per-output audio activity sensors for miniDSP-rs."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .audio_sense import AudioSenseConfig, audio_sense_configs
from .data import MiniDSPConfigEntry
from .entity import MiniDSPEntity


class MiniDSPAudioSenseBinarySensor(MiniDSPEntity, BinarySensorEntity):
    """Detect recent audio activity on one MiniDSP output."""

    _attr_device_class = BinarySensorDeviceClass.SOUND

    def __init__(
        self,
        entry: MiniDSPConfigEntry,
        config: AudioSenseConfig,
    ) -> None:
        """Initialize an output audio-sense sensor."""
        super().__init__(
            entry.runtime_data.coordinator,
            f"audio_sense_output_{config.channel + 1}",
        )
        self._config = config
        self._attr_translation_key = "audio_sense_output"
        self._attr_translation_placeholders = {"output": str(config.channel + 1)}
        self._attr_is_on = False
        self._cancel_pending_off: CALLBACK_TYPE | None = None

    @property
    def available(self) -> bool:
        """Remain available so prolonged missing data can produce an off hook."""
        return True

    async def async_added_to_hass(self) -> None:
        """Evaluate the initial level after registering coordinator updates."""
        await super().async_added_to_hass()
        self._evaluate_audio()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel an owned inactivity timer before removal."""
        self._cancel_off_timer()
        await super().async_will_remove_from_hass()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update activity and pending-off state from the latest level."""
        self._evaluate_audio()
        super()._handle_coordinator_update()

    @callback
    def _evaluate_audio(self) -> None:
        """Apply immediate-on and delayed-off behavior."""
        level = self._observed_level()
        if level is not None and level > self._config.threshold_dbfs:
            self._cancel_off_timer()
            self._attr_is_on = True
            return

        if self._attr_is_on and self._cancel_pending_off is None:
            if self._config.off_delay_minutes == 0:
                self._attr_is_on = False
                return
            self._cancel_pending_off = async_call_later(
                self.hass,
                timedelta(minutes=self._config.off_delay_minutes),
                self._finish_inactivity,
            )

    @callback
    def _finish_inactivity(self, _now: datetime) -> None:
        """Turn off after the full delay unless audio has returned."""
        self._cancel_pending_off = None
        level = self._observed_level()
        if level is not None and level > self._config.threshold_dbfs:
            return
        if self._attr_is_on:
            self._attr_is_on = False
            self.async_write_ha_state()

    @callback
    def _cancel_off_timer(self) -> None:
        """Cancel and release the pending inactivity timer."""
        if self._cancel_pending_off is None:
            return
        self._cancel_pending_off()
        self._cancel_pending_off = None

    def _observed_level(self) -> float | None:
        """Return a level only while coordinator data is current and complete."""
        if not self.coordinator.last_update_success:
            return None
        levels = self.coordinator.data.status.output_levels
        if self._config.channel >= len(levels):
            return None
        return levels[self._config.channel]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Describe the active threshold, delay, and source status."""
        level = self._observed_level()
        return {
            "output": self._config.channel + 1,
            "level_dbfs": None if level is None else round(level, 1),
            "threshold_dbfs": self._config.threshold_dbfs,
            "off_delay_minutes": self._config.off_delay_minutes,
            "inactivity_pending": self._cancel_pending_off is not None,
            "level_available": level is not None,
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MiniDSPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up configured per-output audio activity sensors."""
    output_count = len(entry.runtime_data.coordinator.data.status.output_levels)
    configs = audio_sense_configs(entry.options)
    async_add_entities(
        MiniDSPAudioSenseBinarySensor(entry, config)
        for channel, config in configs.items()
        if channel < output_count
    )
