"""Integration setup and entity tests for miniDSP-rs."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import RegistryEntryDisabler
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.minidsp_rs.api import MiniDSPConnectionError
from custom_components.minidsp_rs.const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_URL,
    CONF_MUTE_WITH_VOLUME,
    CONF_PRODUCT_NAME,
    CONF_SERIAL,
    CONF_VOLUME_CURVE,
    CONF_VOLUME_CURVE_MODE,
    CONF_VOLUME_MAX_DB,
    CONF_VOLUME_MIN_DB,
    CONF_VOLUME_POINT_25_DB,
    CONF_VOLUME_POINT_50_DB,
    CONF_VOLUME_POINT_75_DB,
    DOMAIN,
    VOLUME_CURVE_MODE_FIVE_POINT,
)
from custom_components.minidsp_rs.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.minidsp_rs.models import (
    MasterStatus,
    MiniDSPData,
    MiniDSPDevice,
    MiniDSPVersion,
    StatusSummary,
)

DEVICE = MiniDSPDevice(
    url="usb:test",
    product_name="2x4HD",
    version=MiniDSPVersion(10, 100, 900001),
)
DATA = MiniDSPData(
    device=DEVICE,
    status=StatusSummary(
        master=MasterStatus(
            preset=1,
            source="Toslink",
            volume=-32.0,
            mute=False,
            dirac=True,
        ),
        input_levels=(-45.1, -46.2),
        output_levels=(-55.1, -56.2, -120.0, -120.0),
    ),
)


def _config_entry(*, options: dict[str, object] | None = None) -> MockConfigEntry:
    """Create a configured MiniDSP entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="2x4HD (900001)",
        unique_id="serial:900001",
        data={
            CONF_URL: "http://minidsp.local:5380",
            CONF_DEVICE_ID: "serial:900001",
            CONF_DEVICE_URL: "usb:test",
            CONF_PRODUCT_NAME: "2x4HD",
            CONF_SERIAL: 900001,
        },
        options=options or {},
    )


async def test_setup_entities_and_command(hass: HomeAssistant) -> None:
    """Setup creates controls and commands immediately update entity state."""
    entry = _config_entry()
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "serial:900001_input_level_1",
        suggested_object_id="input_1_level",
        disabled_by=None,
    )

    async def _set_master(**changes: object) -> MasterStatus:
        return replace(DATA.status.master, **changes)

    with (
        patch(
            "custom_components.minidsp_rs.api.MiniDSPClient.async_get_data",
            return_value=DATA,
        ),
        patch(
            "custom_components.minidsp_rs.api.MiniDSPClient.async_set_master_status",
            new_callable=AsyncMock,
            side_effect=_set_master,
        ) as set_master,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        media_id = registry.async_get_entity_id(
            "media_player",
            DOMAIN,
            "serial:900001_media_player",
        )
        switch_id = registry.async_get_entity_id(
            "switch",
            DOMAIN,
            "serial:900001_dirac_live",
        )
        assert media_id is not None
        assert switch_id is not None

        media_state = hass.states.get(media_id)
        assert media_state is not None
        assert media_state.attributes["source"] == "TOSLINK"
        assert media_state.attributes["sound_mode"] == "Preset 2"
        assert media_state.attributes["volume_db"] == -32.0
        assert hass.states.get(switch_id).state == "on"

        input_sensor = registry.async_get_entity_id(
            "sensor",
            DOMAIN,
            "serial:900001_input_level_1",
        )
        assert input_sensor is not None
        assert registry.async_get(input_sensor).disabled_by is None
        assert hass.states.get(input_sensor).state == "-45.1"

        output_sensor = registry.async_get_entity_id(
            "sensor",
            DOMAIN,
            "serial:900001_output_level_1",
        )
        assert output_sensor is not None
        assert (
            registry.async_get(output_sensor).disabled_by
            is RegistryEntryDisabler.INTEGRATION
        )
        assert hass.states.get(output_sensor) is None

        device = dr.async_get(hass).async_get_device({(DOMAIN, "serial:900001")})
        assert device is not None
        assert device.model == "2x4HD"
        assert device.serial_number == "900001"

        diagnostics = await async_get_config_entry_diagnostics(hass, entry)
        diagnostics_text = str(diagnostics)
        assert "minidsp.local" not in diagnostics_text
        assert "usb:test" not in diagnostics_text
        assert "900001" not in diagnostics_text
        assert diagnostics["status"]["master"]["source"] == "Toslink"

        await hass.services.async_call(
            "media_player",
            "volume_mute",
            {"entity_id": media_id, "is_volume_muted": True},
            blocking=True,
        )
        set_master.assert_awaited_once_with(mute=True)
        assert hass.states.get(media_id).attributes["is_volume_muted"] is True

        await hass.services.async_call(
            "media_player",
            "select_source",
            {"entity_id": media_id, "source": "Analog"},
            blocking=True,
        )
        assert set_master.await_args_list[-1].kwargs == {"source": "Analog"}
        assert hass.states.get(media_id).attributes["source"] == "Analog"

        await hass.services.async_call(
            "media_player",
            "select_sound_mode",
            {"entity_id": media_id, "sound_mode": "Preset 4"},
            blocking=True,
        )
        assert set_master.await_args_list[-1].kwargs == {"preset": 3}
        assert hass.states.get(media_id).attributes["sound_mode"] == "Preset 4"

        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": switch_id},
            blocking=True,
        )
        assert set_master.await_args_list[-1].kwargs == {"dirac": False}
        assert hass.states.get(switch_id).state == "off"

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_scoped_volume_and_soft_mute(hass: HomeAssistant) -> None:
    """Volume uses the nonlinear scope and can avoid hardware mute commands."""
    entry = _config_entry(
        options={
            CONF_VOLUME_MIN_DB: -90.0,
            CONF_VOLUME_MAX_DB: -10.0,
            CONF_VOLUME_CURVE: 0.415,
            CONF_MUTE_WITH_VOLUME: True,
        }
    )
    entry.add_to_hass(hass)

    async def _set_master(**changes: object) -> MasterStatus:
        return replace(entry.runtime_data.coordinator.data.status.master, **changes)

    with (
        patch(
            "custom_components.minidsp_rs.api.MiniDSPClient.async_get_data",
            return_value=DATA,
        ),
        patch(
            "custom_components.minidsp_rs.api.MiniDSPClient.async_set_master_status",
            new_callable=AsyncMock,
            side_effect=_set_master,
        ) as set_master,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        registry = er.async_get(hass)
        media_id = registry.async_get_entity_id(
            "media_player",
            DOMAIN,
            "serial:900001_media_player",
        )
        assert media_id is not None
        state = hass.states.get(media_id)
        assert state.attributes["volume_level"] == pytest.approx(0.461, abs=0.001)
        assert state.attributes["volume_min_db"] == -90.0
        assert state.attributes["volume_max_db"] == -10.0
        assert state.attributes["volume_curve"] == 0.415
        assert state.attributes["mute_with_volume"] is True

        await hass.services.async_call(
            "media_player",
            "volume_set",
            {"entity_id": media_id, "volume_level": 0.5},
            blocking=True,
        )
        assert set_master.await_args_list[-1].kwargs == {"volume": -30.0}

        await hass.services.async_call(
            "media_player",
            "volume_mute",
            {"entity_id": media_id, "is_volume_muted": True},
            blocking=True,
        )
        assert set_master.await_args_list[-1].kwargs == {"volume": -90.0}
        assert hass.states.get(media_id).attributes["is_volume_muted"] is True

        await hass.services.async_call(
            "media_player",
            "volume_mute",
            {"entity_id": media_id, "is_volume_muted": False},
            blocking=True,
        )
        assert set_master.await_args_list[-1].kwargs == {"volume": -30.0}
        assert hass.states.get(media_id).attributes["is_volume_muted"] is False
        assert not any("mute" in call.kwargs for call in set_master.await_args_list)


async def test_five_point_volume_mapping(hass: HomeAssistant) -> None:
    """The media player reports and commands the selected five-point curve."""
    entry = _config_entry(
        options={
            CONF_VOLUME_MIN_DB: -90.0,
            CONF_VOLUME_MAX_DB: -10.0,
            CONF_VOLUME_CURVE: 0.415,
            CONF_VOLUME_CURVE_MODE: VOLUME_CURVE_MODE_FIVE_POINT,
            CONF_VOLUME_POINT_25_DB: -55.0,
            CONF_VOLUME_POINT_50_DB: -32.0,
            CONF_VOLUME_POINT_75_DB: -18.0,
        }
    )
    entry.add_to_hass(hass)

    async def _set_master(**changes: object) -> MasterStatus:
        return replace(entry.runtime_data.coordinator.data.status.master, **changes)

    with (
        patch(
            "custom_components.minidsp_rs.api.MiniDSPClient.async_get_data",
            return_value=DATA,
        ),
        patch(
            "custom_components.minidsp_rs.api.MiniDSPClient.async_set_master_status",
            new_callable=AsyncMock,
            side_effect=_set_master,
        ) as set_master,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        registry = er.async_get(hass)
        media_id = registry.async_get_entity_id(
            "media_player",
            DOMAIN,
            "serial:900001_media_player",
        )
        assert media_id is not None
        state = hass.states.get(media_id)
        assert state.attributes["volume_level"] == pytest.approx(0.5, abs=1e-12)
        assert state.attributes["volume_curve_mode"] == VOLUME_CURVE_MODE_FIVE_POINT
        assert state.attributes["volume_point_25_db"] == -55.0
        assert state.attributes["volume_point_50_db"] == -32.0
        assert state.attributes["volume_point_75_db"] == -18.0

        await hass.services.async_call(
            "media_player",
            "volume_set",
            {"entity_id": media_id, "volume_level": 0.75},
            blocking=True,
        )
        set_master.assert_awaited_once_with(volume=-18.0)


async def test_command_failure_is_translated(hass: HomeAssistant) -> None:
    """Command transport errors become user-facing Home Assistant errors."""
    entry = _config_entry()
    entry.add_to_hass(hass)

    with patch(
        "custom_components.minidsp_rs.api.MiniDSPClient.async_get_data",
        return_value=DATA,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    entry.runtime_data.client.async_set_master_status = AsyncMock(
        side_effect=MiniDSPConnectionError
    )
    with pytest.raises(HomeAssistantError) as error:
        await entry.runtime_data.coordinator.async_set_master_status(mute=True)

    assert error.value.translation_key == "command_failed"


async def test_failed_refresh_marks_entities_unavailable(hass: HomeAssistant) -> None:
    """Communication failures make entities unavailable without removing them."""
    entry = _config_entry()
    entry.add_to_hass(hass)

    with patch(
        "custom_components.minidsp_rs.api.MiniDSPClient.async_get_data",
        return_value=DATA,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    media_id = registry.async_get_entity_id(
        "media_player",
        DOMAIN,
        "serial:900001_media_player",
    )
    assert media_id is not None

    entry.runtime_data.client.async_get_data = AsyncMock(
        side_effect=MiniDSPConnectionError
    )
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(media_id).state == "unavailable"
