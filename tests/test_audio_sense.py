"""Tests for per-output audio-sense configuration."""

import pytest

from custom_components.minidsp_rs.audio_sense import (
    AudioSenseConfig,
    audio_sense_configs,
    serialize_audio_sense_configs,
)
from custom_components.minidsp_rs.const import (
    CONF_AUDIO_SENSE_OFF_DELAY,
    CONF_AUDIO_SENSE_OUTPUTS,
    CONF_AUDIO_SENSE_THRESHOLD,
)


def test_audio_sense_config_defaults() -> None:
    """A configured output matches the reference automation defaults."""
    config = AudioSenseConfig(channel=2)

    assert config.threshold_dbfs == -120.0
    assert config.off_delay_minutes == 15


def test_audio_sense_options_round_trip() -> None:
    """Per-output options serialize with stable string channel keys."""
    expected = {
        0: AudioSenseConfig(
            channel=0,
            threshold_dbfs=-115.0,
            off_delay_minutes=10,
        ),
        3: AudioSenseConfig(
            channel=3,
            threshold_dbfs=-100.0,
            off_delay_minutes=30,
        ),
    }

    serialized = serialize_audio_sense_configs(expected)

    assert serialized == {
        "0": {
            CONF_AUDIO_SENSE_THRESHOLD: -115.0,
            CONF_AUDIO_SENSE_OFF_DELAY: 10,
        },
        "3": {
            CONF_AUDIO_SENSE_THRESHOLD: -100.0,
            CONF_AUDIO_SENSE_OFF_DELAY: 30,
        },
    }
    assert audio_sense_configs({CONF_AUDIO_SENSE_OUTPUTS: serialized}) == expected


@pytest.mark.parametrize(
    "values",
    [
        {"channel": -1},
        {"channel": 0, "threshold_dbfs": 1},
        {"channel": 0, "threshold_dbfs": -128},
        {"channel": 0, "threshold_dbfs": float("nan")},
        {"channel": 0, "off_delay_minutes": -1},
        {"channel": 0, "off_delay_minutes": 15.5},
        {"channel": 0, "off_delay_minutes": 1441},
    ],
)
def test_invalid_audio_sense_config(values: dict[str, float | int]) -> None:
    """Invalid per-output settings are rejected."""
    with pytest.raises(ValueError):
        AudioSenseConfig(**values)


def test_invalid_audio_sense_options_shape() -> None:
    """Malformed persisted output mappings are rejected explicitly."""
    with pytest.raises(ValueError):
        audio_sense_configs({CONF_AUDIO_SENSE_OUTPUTS: []})
    with pytest.raises(ValueError):
        audio_sense_configs({CONF_AUDIO_SENSE_OUTPUTS: {"left": {}}})
    with pytest.raises(ValueError):
        audio_sense_configs({CONF_AUDIO_SENSE_OUTPUTS: {"0": []}})
    with pytest.raises(ValueError):
        audio_sense_configs(
            {CONF_AUDIO_SENSE_OUTPUTS: {"0": {CONF_AUDIO_SENSE_OFF_DELAY: 15.5}}}
        )
