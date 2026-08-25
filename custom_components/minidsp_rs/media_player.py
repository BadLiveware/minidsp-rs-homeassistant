"""Media player platform for miniDSP-rs."""

from __future__ import annotations

from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    DOMAIN,
    MAX_VOLUME_DB,
    MIN_VOLUME_DB,
    PRESET_NAMES,
    SOURCE_LABELS,
    VOLUME_STEP_DB,
)
from .data import MiniDSPConfigEntry
from .entity import MiniDSPEntity


class MiniDSPMediaPlayer(MiniDSPEntity, MediaPlayerEntity):
    """Master controls for a MiniDSP device."""

    _attr_icon = "mdi:audio-video"
    _attr_name = None
    _attr_state = MediaPlayerState.IDLE
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )
    _attr_volume_step = VOLUME_STEP_DB / (MAX_VOLUME_DB - MIN_VOLUME_DB)

    def __init__(self, entry: MiniDSPConfigEntry) -> None:
        """Initialize the media player."""
        super().__init__(entry.runtime_data.coordinator, "media_player")
        if self.coordinator.data.device.available_sources():
            self._attr_supported_features |= MediaPlayerEntityFeature.SELECT_SOURCE

    @property
    def volume_level(self) -> float | None:
        """Return master volume normalized to Home Assistant's 0..1 range."""
        volume = self.coordinator.data.status.master.volume
        if volume is None:
            return None
        return min(
            1.0,
            max(0.0, (volume - MIN_VOLUME_DB) / (MAX_VOLUME_DB - MIN_VOLUME_DB)),
        )

    @property
    def is_volume_muted(self) -> bool | None:
        """Return the master mute state."""
        return self.coordinator.data.status.master.mute

    @property
    def source(self) -> str | None:
        """Return the active input source."""
        source = self.coordinator.data.status.master.source
        if source is None:
            return None
        return SOURCE_LABELS.get(source, source)

    @property
    def source_list(self) -> list[str] | None:
        """Return input sources supported by this hardware revision."""
        sources = self.coordinator.data.device.available_sources()
        if not sources:
            return None
        return [SOURCE_LABELS.get(source, source) for source in sources]

    @property
    def sound_mode(self) -> str | None:
        """Return the active DSP configuration preset."""
        preset = self.coordinator.data.status.master.preset
        if preset is None or not 0 <= preset < len(PRESET_NAMES):
            return None
        return PRESET_NAMES[preset]

    @property
    def sound_mode_list(self) -> list[str]:
        """Return available DSP configuration presets."""
        return list(PRESET_NAMES)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set master volume from Home Assistant's normalized range."""
        clamped = min(1.0, max(0.0, volume))
        gain = MIN_VOLUME_DB + clamped * (MAX_VOLUME_DB - MIN_VOLUME_DB)
        await self.coordinator.async_set_master_status(volume=round(gain, 1))

    async def async_mute_volume(self, mute: bool) -> None:
        """Set master mute."""
        await self.coordinator.async_set_master_status(mute=mute)

    async def async_select_source(self, source: str) -> None:
        """Select an input source."""
        source_map = {
            SOURCE_LABELS.get(raw, raw): raw
            for raw in self.coordinator.data.device.available_sources()
        }
        if source not in source_map:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_source",
                translation_placeholders={"source": source},
            )
        await self.coordinator.async_set_master_status(source=source_map[source])

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select a DSP configuration preset."""
        try:
            preset = PRESET_NAMES.index(sound_mode)
        except ValueError as err:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_preset",
                translation_placeholders={"preset": sound_mode},
            ) from err
        await self.coordinator.async_set_master_status(preset=preset)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return MiniDSP-specific master state."""
        volume = self.coordinator.data.status.master.volume
        return {"volume_db": volume}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MiniDSPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the miniDSP-rs media player."""
    async_add_entities([MiniDSPMediaPlayer(entry)])
