"""Data coordinator for the miniDSP-rs integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import MiniDSPClient, MiniDSPError
from .const import DOMAIN, LOGGER, UPDATE_INTERVAL
from .data import MiniDSPConfigEntry
from .models import MiniDSPData


class MiniDSPCoordinator(DataUpdateCoordinator[MiniDSPData]):
    """Coordinate status updates for one DSP."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: MiniDSPConfigEntry,
        client: MiniDSPClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            always_update=False,
        )
        self.client = client

    async def _async_update_data(self) -> MiniDSPData:
        """Fetch the latest device status."""
        try:
            return await self.client.async_get_data()
        except MiniDSPError as err:
            raise UpdateFailed(str(err)) from err

    async def async_set_master_status(self, **changes: object) -> None:
        """Apply master controls and publish the returned state immediately."""
        try:
            master = await self.client.async_set_master_status(**changes)
        except MiniDSPError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
            ) from err
        self.async_set_updated_data(
            MiniDSPData(
                device=self.data.device,
                status=self.data.status.with_master(master),
            )
        )
