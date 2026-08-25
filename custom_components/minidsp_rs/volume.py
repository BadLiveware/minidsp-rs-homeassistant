"""Configurable volume scaling for MiniDSP media players."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from .const import (
    CONF_VOLUME_CURVE,
    CONF_VOLUME_CURVE_MODE,
    CONF_VOLUME_MAX_DB,
    CONF_VOLUME_MIN_DB,
    CONF_VOLUME_POINT_25_DB,
    CONF_VOLUME_POINT_50_DB,
    CONF_VOLUME_POINT_75_DB,
    DEFAULT_VOLUME_CURVE,
    DEFAULT_VOLUME_CURVE_MODE,
    DEFAULT_VOLUME_MAX_DB,
    DEFAULT_VOLUME_MIN_DB,
    DEVICE_MAX_VOLUME_DB,
    DEVICE_MIN_VOLUME_DB,
    VOLUME_CURVE_MODE_EXPONENT,
    VOLUME_CURVE_MODE_FIVE_POINT,
)

_LEVELS = (0.0, 0.25, 0.5, 0.75, 1.0)


@dataclass(frozen=True, slots=True)
class VolumeProfile:
    """Map Home Assistant's 0..1 volume to a useful MiniDSP dB range."""

    min_db: float = DEFAULT_VOLUME_MIN_DB
    max_db: float = DEFAULT_VOLUME_MAX_DB
    curve: float = DEFAULT_VOLUME_CURVE
    mode: str = DEFAULT_VOLUME_CURVE_MODE
    control_points_db: tuple[float, float, float] | None = None

    def __post_init__(self) -> None:
        """Validate profile bounds and curve controls."""
        values = (self.min_db, self.max_db, self.curve)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Volume profile values must be finite")
        if not DEVICE_MIN_VOLUME_DB <= self.min_db < self.max_db:
            raise ValueError("Minimum volume must be below maximum volume")
        if self.max_db > DEVICE_MAX_VOLUME_DB:
            raise ValueError("Maximum volume exceeds the MiniDSP limit")
        if self.curve <= 0:
            raise ValueError("Volume curve must be greater than zero")
        if self.mode not in {
            VOLUME_CURVE_MODE_EXPONENT,
            VOLUME_CURVE_MODE_FIVE_POINT,
        }:
            raise ValueError("Unsupported volume curve mode")

        if self.control_points_db is None:
            object.__setattr__(
                self,
                "control_points_db",
                self._exponent_control_points(),
            )
        points = self.points_db
        if not all(math.isfinite(value) for value in points):
            raise ValueError("Volume control points must be finite")
        if any(left >= right for left, right in pairwise(points)):
            raise ValueError("Volume control points must increase")

    @classmethod
    def from_options(cls, options: Mapping[str, Any]) -> VolumeProfile:
        """Build a profile from config-entry options."""
        min_db = float(options.get(CONF_VOLUME_MIN_DB, DEFAULT_VOLUME_MIN_DB))
        max_db = float(options.get(CONF_VOLUME_MAX_DB, DEFAULT_VOLUME_MAX_DB))
        curve = float(options.get(CONF_VOLUME_CURVE, DEFAULT_VOLUME_CURVE))
        mode = str(options.get(CONF_VOLUME_CURVE_MODE, DEFAULT_VOLUME_CURVE_MODE))
        control_points_db = None
        if mode == VOLUME_CURVE_MODE_FIVE_POINT:
            defaults = _exponent_points(min_db, max_db, curve)
            control_points_db = (
                float(options.get(CONF_VOLUME_POINT_25_DB, defaults[0])),
                float(options.get(CONF_VOLUME_POINT_50_DB, defaults[1])),
                float(options.get(CONF_VOLUME_POINT_75_DB, defaults[2])),
            )
        return cls(
            min_db=min_db,
            max_db=max_db,
            curve=curve,
            mode=mode,
            control_points_db=control_points_db,
        )

    @property
    def points_db(self) -> tuple[float, float, float, float, float]:
        """Return the five curve points, including range endpoints."""
        if self.control_points_db is None:  # pragma: no cover - set after validation
            raise RuntimeError("Volume control points were not initialized")
        return (self.min_db, *self.control_points_db, self.max_db)

    def _exponent_control_points(self) -> tuple[float, float, float]:
        """Return control points implied by the exponent curve."""
        return _exponent_points(self.min_db, self.max_db, self.curve)

    def level_to_db(self, level: float) -> float:
        """Convert Home Assistant's normalized volume to MiniDSP dB."""
        return round(self._level_to_db_unrounded(level), 1)

    def _level_to_db_unrounded(self, level: float) -> float:
        """Convert normalized volume without device-resolution rounding."""
        clamped = min(1.0, max(0.0, level))
        if self.mode == VOLUME_CURVE_MODE_EXPONENT:
            return self.min_db + (self.max_db - self.min_db) * clamped**self.curve
        return _pchip_interpolate(clamped, self.points_db)

    def db_to_level(self, gain: float) -> float:
        """Convert MiniDSP dB to Home Assistant's normalized volume."""
        clamped = min(self.max_db, max(self.min_db, gain))
        if self.mode == VOLUME_CURVE_MODE_EXPONENT:
            position = (clamped - self.min_db) / (self.max_db - self.min_db)
            return position ** (1 / self.curve)

        low = 0.0
        high = 1.0
        for _ in range(48):
            midpoint = (low + high) / 2
            if self._level_to_db_unrounded(midpoint) < clamped:
                low = midpoint
            else:
                high = midpoint
        return (low + high) / 2


def _exponent_points(
    min_db: float,
    max_db: float,
    curve: float,
) -> tuple[float, float, float]:
    """Return 25%, 50%, and 75% dB points for an exponent curve."""
    width = max_db - min_db
    return tuple(min_db + width * level**curve for level in _LEVELS[1:-1])  # type: ignore[return-value]


def _pchip_interpolate(
    level: float,
    points_db: tuple[float, float, float, float, float],
) -> float:
    """Interpolate monotonic control points with a shape-preserving cubic."""
    segment = min(int(level * 4), 3)
    step = 0.25
    position = (level - _LEVELS[segment]) / step
    slopes = _pchip_slopes(points_db, step)
    position_2 = position * position
    position_3 = position_2 * position
    return (
        (2 * position_3 - 3 * position_2 + 1) * points_db[segment]
        + (position_3 - 2 * position_2 + position) * step * slopes[segment]
        + (-2 * position_3 + 3 * position_2) * points_db[segment + 1]
        + (position_3 - position_2) * step * slopes[segment + 1]
    )


def _pchip_slopes(
    points_db: tuple[float, float, float, float, float],
    step: float,
) -> tuple[float, float, float, float, float]:
    """Calculate Fritsch-Carlson derivatives for monotonic cubic interpolation."""
    secants = tuple((right - left) / step for left, right in pairwise(points_db))
    interior = tuple(
        2 * left * right / (left + right) for left, right in pairwise(secants)
    )
    first = _endpoint_slope(secants[0], secants[1])
    last = _endpoint_slope(secants[-1], secants[-2])
    return (first, *interior, last)


def _endpoint_slope(adjacent: float, next_secant: float) -> float:
    """Return a monotonic endpoint derivative for equal-width segments."""
    slope = (3 * adjacent - next_secant) / 2
    if slope <= 0:
        return 0.0
    return min(slope, 3 * adjacent)
