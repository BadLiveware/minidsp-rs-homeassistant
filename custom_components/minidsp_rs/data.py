"""Runtime data types for the miniDSP-rs integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .api import MiniDSPClient
    from .coordinator import MiniDSPCoordinator


@dataclass(slots=True)
class MiniDSPRuntimeData:
    """Runtime objects for a configured DSP."""

    client: MiniDSPClient
    coordinator: MiniDSPCoordinator


type MiniDSPConfigEntry = ConfigEntry[MiniDSPRuntimeData]
