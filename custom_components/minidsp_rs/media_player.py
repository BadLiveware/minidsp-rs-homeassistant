"""Media player platform for miniDSP-rs."""

from __future__ import annotations

import math
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_MUTE_WITH_VOLUME,
    DEFAULT_MUTE_WITH_VOLUME,
    DOMAIN,
    PRESET_NAMES,
    SOURCE_LABELS,
    VOLUME_STEP,
)
from .data import MiniDSPConfigEntry
from .entity import MiniDSPEntity
from .volume import VolumeProfile


class MiniDSPMediaPlayer(MiniDSPEntity, MediaPlayerEntity):
    """Master controls for a MiniDSP device."""

    _attr_icon = "mdi:audio-video"
    _attr_name = None
    # The DSP reports reachability, not playback state.
    _attr_state = MediaPlayerState.ON
    _attr_supported_features = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    )
    _attr_volume_step = VOLUME_STEP

    def __init__(self, entry: MiniDSPConfigEntry) -> None:
        """Initialize the media player."""
        super().__init__(entry.runtime_data.coordinator, "media_player")
        self._volume_profile = VolumeProfile.from_options(entry.options)
        self._mute_with_volume = bool(
            entry.options.get(CONF_MUTE_WITH_VOLUME, DEFAULT_MUTE_WITH_VOLUME)
        )
        self._soft_muted = False
        self._volume_before_soft_mute: float | None = None
        if self.coordinator.data.device.available_sources():
            self._attr_supported_features |= MediaPlayerEntityFeature.SELECT_SOURCE

    @property
    def volume_level(self) -> float | None:
        """Return master volume normalized to Home Assistant's 0..1 range."""
        volume = self.coordinator.data.status.master.volume
        if volume is None:
            return None
        return self._volume_profile.db_to_level(volume)

    @property
    def is_volume_muted(self) -> bool | None:
        """Return the master mute state."""
        return self._soft_muted or self.coordinator.data.status.master.mute

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
        """Set master volume using the configured useful dB range."""
        gain = self._volume_profile.level_to_db(volume)
        await self.coordinator.async_set_master_status(volume=gain)
        self._soft_muted = False
        self._volume_before_soft_mute = None
        self.async_write_ha_state()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute using hardware mute or the configured zero-volume behavior."""
        if not self._mute_with_volume:
            await self.coordinator.async_set_master_status(mute=mute)
            return

        master = self.coordinator.data.status.master
        if mute:
            if self.is_volume_muted:
                return
            if master.volume is not None and not math.isclose(
                master.volume,
                self._volume_profile.min_db,
                abs_tol=0.05,
            ):
                self._volume_before_soft_mute = master.volume
            await self.coordinator.async_set_master_status(
                volume=self._volume_profile.min_db
            )
            self._soft_muted = True
            self.async_write_ha_state()
            return

        if self._soft_muted:
            restore_volume = self._volume_before_soft_mute
            if restore_volume is not None:
                await self.coordinator.async_set_master_status(volume=restore_volume)
            self._soft_muted = False
            self._volume_before_soft_mute = None
            self.async_write_ha_state()
        elif master.mute:
            await self.coordinator.async_set_master_status(mute=False)

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

    @callback
    def _handle_coordinator_update(self) -> None:
        """Clear soft mute when another controller changes the volume."""
        volume = self.coordinator.data.status.master.volume
        if (
            self._soft_muted
            and volume is not None
            and not math.isclose(
                volume,
                self._volume_profile.min_db,
                abs_tol=0.05,
            )
        ):
            self._soft_muted = False
            self._volume_before_soft_mute = None
        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return MiniDSP-specific master and volume-profile state."""
        volume = self.coordinator.data.status.master.volume
        point_25, point_50, point_75 = self._volume_profile.points_db[1:-1]
        return {
            "volume_db": volume,
            "volume_min_db": self._volume_profile.min_db,
            "volume_max_db": self._volume_profile.max_db,
            "volume_curve_mode": self._volume_profile.mode,
            "volume_curve": self._volume_profile.curve,
            "volume_point_25_db": round(point_25, 1),
            "volume_point_50_db": round(point_50, 1),
            "volume_point_75_db": round(point_75, 1),
            "mute_with_volume": self._mute_with_volume,
        }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MiniDSPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the miniDSP-rs media player."""
    async_add_entities([MiniDSPMediaPlayer(entry)])
