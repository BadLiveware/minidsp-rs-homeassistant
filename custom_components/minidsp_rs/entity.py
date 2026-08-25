"""Shared entity support for miniDSP-rs."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MiniDSPCoordinator


class MiniDSPEntity(CoordinatorEntity[MiniDSPCoordinator]):
    """Base class for entities belonging to a MiniDSP device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MiniDSPCoordinator, key: str) -> None:
        """Initialize a MiniDSP entity."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.unique_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information."""
        device = self.coordinator.data.device
        version = device.version
        info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.unique_id)},
            manufacturer="miniDSP",
            model=device.name,
            name=device.display_label(),
        )
        if version is not None:
            info["hw_version"] = str(version.hw_id)
            info["sw_version"] = str(version.dsp_version)
            if device.serial is not None:
                info["serial_number"] = str(device.serial)
        return info
