"""Tests for the miniDSP-rs config flow."""

from types import SimpleNamespace
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.minidsp_rs.api import MiniDSPConnectionError
from custom_components.minidsp_rs.const import (
    CONF_AUDIO_SENSE_OFF_DELAY,
    CONF_AUDIO_SENSE_OUTPUTS,
    CONF_AUDIO_SENSE_THRESHOLD,
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
    VOLUME_CURVE_MODE_EXPONENT,
    VOLUME_CURVE_MODE_FIVE_POINT,
)
from custom_components.minidsp_rs.models import MiniDSPDevice, MiniDSPVersion

DEVICE_1 = MiniDSPDevice(
    url="usb:first",
    product_name="2x4HD",
    version=MiniDSPVersion(10, 100, 900001),
)
DEVICE_2 = MiniDSPDevice(
    url="usb:second",
    product_name="Flex",
    version=MiniDSPVersion(27, 100, 900002),
)


async def _open_options_step(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    step: str,
) -> dict[str, object]:
    """Open one branch of the integration options menu."""
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is data_entry_flow.FlowResultType.MENU
    assert result["step_id"] == "init"
    return await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"next_step_id": step},
    )


async def test_single_device_creates_entry(hass: HomeAssistant) -> None:
    """A daemon with one DSP can be configured in one step."""
    with patch(
        "custom_components.minidsp_rs.config_flow.MiniDSPClient.async_get_devices",
        return_value=(DEVICE_1,),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_URL: "minidsp.local"},
        )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "2x4HD (900001)"
    assert result["data"][CONF_URL] == "http://minidsp.local:5380"
    assert result["data"][CONF_DEVICE_ID] == "serial:900001"


async def test_multiple_devices_prompts_for_selection(hass: HomeAssistant) -> None:
    """Each DSP exposed by one daemon can receive its own config entry."""
    with patch(
        "custom_components.minidsp_rs.config_flow.MiniDSPClient.async_get_devices",
        return_value=(DEVICE_1, DEVICE_2),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_URL: "http://minidsp.local:5380"},
        )
        assert result["type"] is data_entry_flow.FlowResultType.FORM
        assert result["step_id"] == "device"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE_ID: "serial:900002"},
        )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "Flex (900002)"


async def test_duplicate_device_is_rejected(hass: HomeAssistant) -> None:
    """The same reliable serial cannot be configured twice."""
    MockConfigEntry(
        domain=DOMAIN,
        title="Existing",
        unique_id="serial:900001",
        data={CONF_URL: "http://old:5380"},
    ).add_to_hass(hass)

    with patch(
        "custom_components.minidsp_rs.config_flow.MiniDSPClient.async_get_devices",
        return_value=(DEVICE_1,),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_URL: "http://new:5380"},
        )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_connection_error_is_reported(hass: HomeAssistant) -> None:
    """Connection failures remain in the config form."""
    with patch(
        "custom_components.minidsp_rs.config_flow.MiniDSPClient.async_get_devices",
        side_effect=MiniDSPConnectionError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_URL: "http://offline:5380"},
        )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_invalid_url_and_empty_daemon_are_reported(hass: HomeAssistant) -> None:
    """Input and discovery errors produce actionable form errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_URL: "ftp://unsupported"},
    )
    assert result["errors"] == {"base": "invalid_url"}

    with patch(
        "custom_components.minidsp_rs.config_flow.MiniDSPClient.async_get_devices",
        return_value=(),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={CONF_URL: "http://empty:5380"},
        )
    assert result["errors"] == {"base": "no_devices"}


async def test_reconfigure_updates_endpoint(hass: HomeAssistant) -> None:
    """Reconfiguration follows a reliable serial to a new daemon URL."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="2x4HD (900001)",
        unique_id="serial:900001",
        data={
            CONF_URL: "http://old:5380",
            CONF_DEVICE_ID: "serial:900001",
            CONF_DEVICE_URL: "usb:first",
            CONF_PRODUCT_NAME: "2x4HD",
            CONF_SERIAL: 900001,
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.minidsp_rs.config_flow.MiniDSPClient.async_get_devices",
        return_value=(DEVICE_1,),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
            data={CONF_URL: "http://new:5380"},
        )

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_URL] == "http://new:5380"


async def test_volume_options_flow(hass: HomeAssistant) -> None:
    """Volume scope and soft mute can be configured without YAML."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="2x4HD (900001)",
        unique_id="serial:900001",
        data={CONF_URL: "http://minidsp:5380"},
    )
    entry.add_to_hass(hass)

    result = await _open_options_step(hass, entry, "volume")
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "volume"

    range_options = {
        CONF_VOLUME_MIN_DB: -80.0,
        CONF_VOLUME_MAX_DB: -15.0,
        CONF_VOLUME_CURVE_MODE: VOLUME_CURVE_MODE_EXPONENT,
        CONF_MUTE_WITH_VOLUME: True,
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        range_options,
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "exponent"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_VOLUME_CURVE: 0.5},
    )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert entry.options.items() >= (range_options | {CONF_VOLUME_CURVE: 0.5}).items()


async def test_volume_options_reject_invalid_range(hass: HomeAssistant) -> None:
    """Volume scope must remain ordered and within device limits."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="2x4HD (900001)",
        unique_id="serial:900001",
        data={CONF_URL: "http://minidsp:5380"},
    )
    entry.add_to_hass(hass)

    result = await _open_options_step(hass, entry, "volume")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_VOLUME_MIN_DB: -10.0,
            CONF_VOLUME_MAX_DB: -90.0,
            CONF_VOLUME_CURVE_MODE: VOLUME_CURVE_MODE_EXPONENT,
            CONF_MUTE_WITH_VOLUME: False,
        },
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_volume_profile"}


async def test_five_point_options_flow(hass: HomeAssistant) -> None:
    """Five-point mode validates and saves its three editable anchors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="2x4HD (900001)",
        unique_id="serial:900001",
        data={CONF_URL: "http://minidsp:5380"},
    )
    entry.add_to_hass(hass)

    result = await _open_options_step(hass, entry, "volume")
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_VOLUME_MIN_DB: -90.0,
            CONF_VOLUME_MAX_DB: -10.0,
            CONF_VOLUME_CURVE_MODE: VOLUME_CURVE_MODE_FIVE_POINT,
            CONF_MUTE_WITH_VOLUME: True,
        },
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "five_point"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_VOLUME_POINT_25_DB: -55.0,
            CONF_VOLUME_POINT_50_DB: -60.0,
            CONF_VOLUME_POINT_75_DB: -20.0,
        },
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_volume_profile"}

    points = {
        CONF_VOLUME_POINT_25_DB: -55.0,
        CONF_VOLUME_POINT_50_DB: -32.0,
        CONF_VOLUME_POINT_75_DB: -18.0,
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        points,
    )
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert entry.options.items() >= points.items()
    assert entry.options[CONF_VOLUME_CURVE_MODE] == VOLUME_CURVE_MODE_FIVE_POINT


async def test_audio_sense_options_flow(hass: HomeAssistant) -> None:
    """Audio sensing can be configured independently for selected outputs."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="2x4HD (900001)",
        unique_id="serial:900001",
        data={CONF_URL: "http://minidsp:5380"},
        options={CONF_VOLUME_CURVE: 0.5},
    )
    entry.runtime_data = SimpleNamespace(
        coordinator=SimpleNamespace(
            data=SimpleNamespace(
                status=SimpleNamespace(output_levels=(-127.0,) * 4),
            )
        )
    )
    entry.add_to_hass(hass)

    result = await _open_options_step(hass, entry, "audio_sense")
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "audio_sense"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_AUDIO_SENSE_OUTPUTS: ["0", "2"]},
    )
    assert result["step_id"] == "audio_output"
    assert result["description_placeholders"] == {"output": "1"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_AUDIO_SENSE_THRESHOLD: -120.0,
            CONF_AUDIO_SENSE_OFF_DELAY: 15,
        },
    )
    assert result["step_id"] == "audio_output"
    assert result["description_placeholders"] == {"output": "3"}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_AUDIO_SENSE_THRESHOLD: -110.0,
            CONF_AUDIO_SENSE_OFF_DELAY: 5,
        },
    )
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_AUDIO_SENSE_OUTPUTS] == {
        "0": {
            CONF_AUDIO_SENSE_THRESHOLD: -120.0,
            CONF_AUDIO_SENSE_OFF_DELAY: 15,
        },
        "2": {
            CONF_AUDIO_SENSE_THRESHOLD: -110.0,
            CONF_AUDIO_SENSE_OFF_DELAY: 5,
        },
    }
    assert entry.options[CONF_VOLUME_CURVE] == 0.5


async def test_audio_sense_requires_loaded_output_data(hass: HomeAssistant) -> None:
    """Audio output selection is unavailable before status has loaded."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="2x4HD (900001)",
        unique_id="serial:900001",
        data={CONF_URL: "http://minidsp:5380"},
    )
    entry.add_to_hass(hass)

    result = await _open_options_step(hass, entry, "audio_sense")

    assert result["type"] is data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "audio_sense_unavailable"


async def test_reconfigure_requires_same_device(hass: HomeAssistant) -> None:
    """Reconfiguration cannot silently retarget an entry to another DSP."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="2x4HD (900001)",
        unique_id="serial:900001",
        data={
            CONF_URL: "http://old:5380",
            CONF_DEVICE_ID: "serial:900001",
            CONF_DEVICE_URL: "usb:first",
            CONF_PRODUCT_NAME: "2x4HD",
            CONF_SERIAL: 900001,
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.minidsp_rs.config_flow.MiniDSPClient.async_get_devices",
        return_value=(DEVICE_2,),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
            data={CONF_URL: "http://wrong:5380"},
        )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "device_not_found"}
    assert entry.data[CONF_URL] == "http://old:5380"
