"""Per-output audio-sense configuration."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from .const import (
    CONF_AUDIO_SENSE_OFF_DELAY,
    CONF_AUDIO_SENSE_OUTPUTS,
    CONF_AUDIO_SENSE_THRESHOLD,
    DEFAULT_AUDIO_SENSE_OFF_DELAY,
    DEFAULT_AUDIO_SENSE_THRESHOLD,
    DEVICE_MAX_VOLUME_DB,
    DEVICE_MIN_VOLUME_DB,
    MAX_AUDIO_SENSE_OFF_DELAY,
)


@dataclass(frozen=True, slots=True)
class AudioSenseConfig:
    """Configure activity detection for one MiniDSP output."""

    channel: int
    threshold_dbfs: float = DEFAULT_AUDIO_SENSE_THRESHOLD
    off_delay_minutes: int = DEFAULT_AUDIO_SENSE_OFF_DELAY

    def __post_init__(self) -> None:
        """Validate channel, threshold, and delay bounds."""
        if self.channel < 0:
            raise ValueError("Audio-sense channel must not be negative")
        if not math.isfinite(self.threshold_dbfs):
            raise ValueError("Audio-sense threshold must be finite")
        if not DEVICE_MIN_VOLUME_DB <= self.threshold_dbfs <= DEVICE_MAX_VOLUME_DB:
            raise ValueError("Audio-sense threshold is outside the dBFS range")
        if isinstance(self.off_delay_minutes, bool) or not isinstance(
            self.off_delay_minutes, int
        ):
            raise ValueError("Audio-sense off delay must be whole minutes")
        if not 0 <= self.off_delay_minutes <= MAX_AUDIO_SENSE_OFF_DELAY:
            raise ValueError("Audio-sense off delay is outside the supported range")

    @classmethod
    def from_dict(cls, channel: int, value: Mapping[str, Any]) -> AudioSenseConfig:
        """Build one output configuration from stored options."""
        return cls(
            channel=channel,
            threshold_dbfs=float(
                value.get(CONF_AUDIO_SENSE_THRESHOLD, DEFAULT_AUDIO_SENSE_THRESHOLD)
            ),
            off_delay_minutes=_whole_minutes(
                value.get(CONF_AUDIO_SENSE_OFF_DELAY, DEFAULT_AUDIO_SENSE_OFF_DELAY)
            ),
        )

    def as_dict(self) -> dict[str, float | int]:
        """Return a JSON-serializable options value."""
        return {
            CONF_AUDIO_SENSE_THRESHOLD: self.threshold_dbfs,
            CONF_AUDIO_SENSE_OFF_DELAY: self.off_delay_minutes,
        }


def _whole_minutes(value: Any) -> int:
    """Parse a whole-minute selector value without silent truncation."""
    if isinstance(value, bool):
        raise ValueError("Audio-sense off delay must be whole minutes")
    try:
        numeric = float(value)
    except (TypeError, ValueError) as err:
        raise ValueError("Audio-sense off delay must be numeric") from err
    if not math.isfinite(numeric) or not numeric.is_integer():
        raise ValueError("Audio-sense off delay must be whole minutes")
    return int(numeric)


def audio_sense_configs(options: Mapping[str, Any]) -> dict[int, AudioSenseConfig]:
    """Parse all configured output channels from config-entry options."""
    raw_outputs = options.get(CONF_AUDIO_SENSE_OUTPUTS, {})
    if not isinstance(raw_outputs, Mapping):
        raise ValueError("Audio-sense outputs must be an object")

    configs: dict[int, AudioSenseConfig] = {}
    for raw_channel, raw_config in raw_outputs.items():
        try:
            channel = int(raw_channel)
        except (TypeError, ValueError) as err:
            raise ValueError("Audio-sense output channel is invalid") from err
        if channel in configs:
            raise ValueError("Audio-sense output channel is duplicated")
        if not isinstance(raw_config, Mapping):
            raise ValueError("Audio-sense output configuration must be an object")
        configs[channel] = AudioSenseConfig.from_dict(channel, raw_config)
    return configs


def serialize_audio_sense_configs(
    configs: Mapping[int, AudioSenseConfig],
) -> dict[str, dict[str, float | int]]:
    """Serialize output configurations for config-entry options."""
    return {str(channel): configs[channel].as_dict() for channel in sorted(configs)}
