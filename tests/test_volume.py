"""Tests for configurable MiniDSP volume scaling."""

from itertools import pairwise

import pytest

from custom_components.minidsp_rs.const import (
    CONF_VOLUME_CURVE,
    CONF_VOLUME_CURVE_MODE,
    CONF_VOLUME_MAX_DB,
    CONF_VOLUME_MIN_DB,
    CONF_VOLUME_POINT_25_DB,
    CONF_VOLUME_POINT_50_DB,
    CONF_VOLUME_POINT_75_DB,
    VOLUME_CURVE_MODE_FIVE_POINT,
)
from custom_components.minidsp_rs.volume import VolumeProfile


def test_default_profile_matches_existing_automation() -> None:
    """The default profile matches the supplied nonlinear REST template."""
    profile = VolumeProfile()

    assert profile.level_to_db(0.0) == -90.0
    assert profile.level_to_db(0.25) == -45.0
    assert profile.level_to_db(0.5) == -30.0
    assert profile.level_to_db(1.0) == -10.0


@pytest.mark.parametrize("level", [0.0, 0.1, 0.25, 0.5, 0.75, 1.0])
def test_profile_round_trip(level: float) -> None:
    """Reported volume approximately inverts the command mapping."""
    profile = VolumeProfile()
    assert profile.db_to_level(profile.level_to_db(level)) == pytest.approx(
        level,
        abs=0.002,
    )


def test_five_point_profile_uses_smooth_monotonic_curve() -> None:
    """Five-point curves pass through every anchor without reversing direction."""
    profile = VolumeProfile(
        min_db=-90.0,
        max_db=-10.0,
        mode=VOLUME_CURVE_MODE_FIVE_POINT,
        control_points_db=(-60.0, -38.0, -21.0),
    )

    assert [profile.level_to_db(level) for level in (0, 0.25, 0.5, 0.75, 1)] == [
        -90.0,
        -60.0,
        -38.0,
        -21.0,
        -10.0,
    ]
    gains = [profile._level_to_db_unrounded(index / 1000) for index in range(1001)]
    assert all(left < right for left, right in pairwise(gains))


@pytest.mark.parametrize("level", [0.0, 0.1, 0.25, 0.4, 0.5, 0.68, 0.75, 0.9, 1.0])
def test_five_point_profile_round_trip(level: float) -> None:
    """Five-point inverse mapping follows its smooth forward mapping."""
    profile = VolumeProfile.from_options(
        {
            CONF_VOLUME_MIN_DB: -90.0,
            CONF_VOLUME_MAX_DB: -10.0,
            CONF_VOLUME_CURVE_MODE: VOLUME_CURVE_MODE_FIVE_POINT,
            CONF_VOLUME_POINT_25_DB: -60.0,
            CONF_VOLUME_POINT_50_DB: -38.0,
            CONF_VOLUME_POINT_75_DB: -21.0,
        }
    )

    assert profile.db_to_level(profile._level_to_db_unrounded(level)) == pytest.approx(
        level,
        abs=1e-12,
    )


def test_custom_profile_and_clamping() -> None:
    """Custom linear profiles clamp both Home Assistant and device values."""
    profile = VolumeProfile.from_options(
        {
            CONF_VOLUME_MIN_DB: -80.0,
            CONF_VOLUME_MAX_DB: -20.0,
            CONF_VOLUME_CURVE: 1.0,
        }
    )

    assert profile.level_to_db(-1.0) == -80.0
    assert profile.level_to_db(0.5) == -50.0
    assert profile.level_to_db(2.0) == -20.0
    assert profile.db_to_level(-100.0) == 0.0
    assert profile.db_to_level(0.0) == 1.0


@pytest.mark.parametrize(
    "profile",
    [
        {"min_db": -10.0, "max_db": -20.0, "curve": 1.0},
        {"min_db": -130.0, "max_db": -10.0, "curve": 1.0},
        {"min_db": -90.0, "max_db": 1.0, "curve": 1.0},
        {"min_db": -90.0, "max_db": -10.0, "curve": 0.0},
        {
            "min_db": -90.0,
            "max_db": -10.0,
            "mode": VOLUME_CURVE_MODE_FIVE_POINT,
            "control_points_db": (-50.0, -55.0, -20.0),
        },
    ],
)
def test_invalid_profiles_are_rejected(profile: dict[str, float]) -> None:
    """Invalid persisted profiles cannot produce unsafe volume commands."""
    with pytest.raises(ValueError):
        VolumeProfile(**profile)
