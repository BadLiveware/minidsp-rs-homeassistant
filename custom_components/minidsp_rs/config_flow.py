"""Config flow for miniDSP-rs."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_URL
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import MiniDSPClient, MiniDSPError, normalize_base_url
from .audio_sense import (
    AudioSenseConfig,
    audio_sense_configs,
    serialize_audio_sense_configs,
)
from .const import (
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
    DEFAULT_MUTE_WITH_VOLUME,
    DEFAULT_VOLUME_CURVE,
    DEFAULT_VOLUME_CURVE_MODE,
    DEFAULT_VOLUME_MAX_DB,
    DEFAULT_VOLUME_MIN_DB,
    DEVICE_MAX_VOLUME_DB,
    DEVICE_MIN_VOLUME_DB,
    DOMAIN,
    LOGGER,
    MAX_AUDIO_SENSE_OFF_DELAY,
    MAX_VOLUME_CURVE,
    MIN_VOLUME_CURVE,
    VOLUME_CURVE_MODE_EXPONENT,
    VOLUME_CURVE_MODE_FIVE_POINT,
)
from .models import MiniDSPDevice
from .volume import VolumeProfile


class MiniDSPConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle configuration for a miniDSP-rs device."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._base_url: str | None = None
        self._devices: tuple[MiniDSPDevice, ...] = ()

    @staticmethod
    @callback
    def async_get_options_flow(
        _config_entry: ConfigEntry,
    ) -> MiniDSPOptionsFlow:
        """Create the options flow."""
        return MiniDSPOptionsFlow()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Collect the minidspd endpoint and discover devices."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                base_url = normalize_base_url(user_input[CONF_URL])
            except ValueError:
                errors["base"] = "invalid_url"
            else:
                try:
                    devices = await self._async_discover(base_url)
                except MiniDSPError as err:
                    LOGGER.debug("Unable to discover miniDSP devices: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    if not devices:
                        errors["base"] = "no_devices"
                    else:
                        self._base_url = base_url
                        self._devices = devices
                        if len(devices) == 1:
                            return await self._async_create_entry(devices[0])
                        return await self.async_step_device()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_URL,
                        default=(user_input or {}).get(CONF_URL, "http://minidsp:5380"),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_device(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Select one DSP when the daemon exposes multiple devices."""
        if self._base_url is None or not self._devices:
            return self.async_abort(reason="discovery_expired")

        devices_by_id = {
            device.identity(self._base_url): device for device in self._devices
        }
        errors: dict[str, str] = {}
        if user_input is not None:
            device = devices_by_id.get(user_input[CONF_DEVICE_ID])
            if device is None:
                errors["base"] = "device_not_found"
            else:
                return await self._async_create_entry(device)

        options = [
            selector.SelectOptionDict(value=identity, label=device.display_label())
            for identity, device in devices_by_id.items()
        ]
        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=options)
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Update the minidspd endpoint while preserving device identity."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                base_url = normalize_base_url(user_input[CONF_URL])
            except ValueError:
                errors["base"] = "invalid_url"
            else:
                try:
                    devices = await self._async_discover(base_url)
                except MiniDSPError as err:
                    LOGGER.debug("Unable to reconfigure miniDSP endpoint: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    device = _find_configured_device(
                        devices,
                        serial=entry.data.get(CONF_SERIAL),
                        device_url=entry.data.get(CONF_DEVICE_URL),
                    )
                    if device is None:
                        errors["base"] = "device_not_found"
                    else:
                        return self.async_update_reload_and_abort(
                            entry,
                            data_updates=_entry_data(base_url, device),
                        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_URL,
                        default=(user_input or {}).get(
                            CONF_URL,
                            entry.data[CONF_URL],
                        ),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def _async_discover(self, base_url: str) -> tuple[MiniDSPDevice, ...]:
        """Discover devices using Home Assistant's shared HTTP session."""
        client = MiniDSPClient(base_url, async_get_clientsession(self.hass))
        return await client.async_get_devices()

    async def _async_create_entry(self, device: MiniDSPDevice) -> ConfigFlowResult:
        """Create an entry for a discovered DSP."""
        assert self._base_url is not None
        await self.async_set_unique_id(device.identity(self._base_url))
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=device.display_label(),
            data=_entry_data(self._base_url, device),
        )


class MiniDSPOptionsFlow(OptionsFlowWithReload):
    """Configure volume behavior and per-output audio sensing."""

    _pending_options: dict[str, Any]
    _audio_configs: dict[int, AudioSenseConfig]
    _audio_selected_channels: list[int]
    _audio_step_index: int

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Choose an integration feature to configure."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["volume", "audio_sense"],
        )

    async def async_step_volume(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Configure the range and choose a curve editor."""
        current = _default_volume_options() | dict(self.config_entry.options)
        errors: dict[str, str] = {}
        if user_input is not None:
            pending = current | user_input
            try:
                VolumeProfile.from_options(
                    pending | {CONF_VOLUME_CURVE_MODE: VOLUME_CURVE_MODE_EXPONENT}
                )
            except ValueError:
                errors["base"] = "invalid_volume_profile"
            else:
                self._pending_options = pending
                if pending[CONF_VOLUME_CURVE_MODE] == VOLUME_CURVE_MODE_FIVE_POINT:
                    return await self.async_step_five_point()
                return await self.async_step_exponent()

        return self.async_show_form(
            step_id="volume",
            data_schema=self.add_suggested_values_to_schema(
                _volume_range_schema(),
                current if user_input is None else user_input,
            ),
            errors=errors,
        )

    async def async_step_audio_sense(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Select outputs that should expose audio-sense sensors."""
        output_count = self._output_count()
        if output_count == 0:
            return self.async_abort(reason="audio_sense_unavailable")

        try:
            existing = audio_sense_configs(self.config_entry.options)
        except ValueError:
            existing = {}

        if user_input is not None:
            self._audio_selected_channels = sorted(
                int(channel) for channel in user_input[CONF_AUDIO_SENSE_OUTPUTS]
            )
            self._audio_configs = {}
            self._audio_step_index = 0
            if not self._audio_selected_channels:
                return self._create_audio_sense_entry()
            return await self.async_step_audio_output()

        output_options = [
            selector.SelectOptionDict(value=str(channel), label=f"Output {channel + 1}")
            for channel in range(output_count)
        ]
        return self.async_show_form(
            step_id="audio_sense",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(
                    {
                        vol.Required(CONF_AUDIO_SENSE_OUTPUTS): (
                            selector.SelectSelector(
                                selector.SelectSelectorConfig(
                                    options=output_options,
                                    multiple=True,
                                )
                            )
                        )
                    }
                ),
                {CONF_AUDIO_SENSE_OUTPUTS: [str(channel) for channel in existing]},
            ),
        )

    async def async_step_audio_output(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Configure activity detection for one selected output."""
        channel = self._audio_selected_channels[self._audio_step_index]
        try:
            existing = audio_sense_configs(self.config_entry.options)
        except ValueError:
            existing = {}
        current = existing.get(channel, AudioSenseConfig(channel=channel))
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                config = AudioSenseConfig.from_dict(channel, user_input)
            except TypeError, ValueError:
                errors["base"] = "invalid_audio_sense"
            else:
                self._audio_configs[channel] = config
                self._audio_step_index += 1
                if self._audio_step_index == len(self._audio_selected_channels):
                    return self._create_audio_sense_entry()
                return await self.async_step_audio_output()

        suggestions = current.as_dict() if user_input is None else user_input
        return self.async_show_form(
            step_id="audio_output",
            data_schema=self.add_suggested_values_to_schema(
                _audio_output_schema(),
                suggestions,
            ),
            errors=errors,
            description_placeholders={"output": str(channel + 1)},
        )

    def _create_audio_sense_entry(self) -> ConfigFlowResult:
        """Save the selected per-output audio-sense configuration."""
        options = dict(self.config_entry.options)
        options[CONF_AUDIO_SENSE_OUTPUTS] = serialize_audio_sense_configs(
            self._audio_configs
        )
        return self.async_create_entry(data=options)

    def _output_count(self) -> int:
        """Return the output count from the loaded coordinator."""
        runtime_data = getattr(self.config_entry, "runtime_data", None)
        if runtime_data is None:
            return 0
        return len(runtime_data.coordinator.data.status.output_levels)

    async def async_step_exponent(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Configure the exponent curve."""
        errors: dict[str, str] = {}
        if user_input is not None:
            options = self._pending_options | user_input
            try:
                VolumeProfile.from_options(options)
            except ValueError:
                errors["base"] = "invalid_volume_profile"
            else:
                return self.async_create_entry(data=options)

        return self.async_show_form(
            step_id="exponent",
            data_schema=self.add_suggested_values_to_schema(
                _exponent_schema(),
                self._pending_options if user_input is None else user_input,
            ),
            errors=errors,
        )

    async def async_step_five_point(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Configure the three editable points of the five-point curve."""
        errors: dict[str, str] = {}
        if user_input is not None:
            options = self._pending_options | user_input
            try:
                VolumeProfile.from_options(options)
            except ValueError:
                errors["base"] = "invalid_volume_profile"
            else:
                return self.async_create_entry(data=options)

        suggestions = _five_point_suggestions(self._pending_options)
        if user_input is not None:
            suggestions.update(user_input)
        return self.async_show_form(
            step_id="five_point",
            data_schema=self.add_suggested_values_to_schema(
                _five_point_schema(self._pending_options),
                suggestions,
            ),
            errors=errors,
        )


def _audio_output_schema() -> vol.Schema:
    """Return threshold and inactivity-delay controls for one output."""
    return vol.Schema(
        {
            vol.Required(CONF_AUDIO_SENSE_THRESHOLD): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=DEVICE_MIN_VOLUME_DB,
                    max=DEVICE_MAX_VOLUME_DB,
                    step=0.5,
                    unit_of_measurement="dBFS",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(CONF_AUDIO_SENSE_OFF_DELAY): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=MAX_AUDIO_SENSE_OFF_DELAY,
                    step=1,
                    unit_of_measurement="min",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


def _default_volume_options() -> dict[str, Any]:
    """Return complete backward-compatible volume defaults."""
    profile = VolumeProfile()
    point_25, point_50, point_75 = profile.points_db[1:-1]
    return {
        CONF_VOLUME_MIN_DB: DEFAULT_VOLUME_MIN_DB,
        CONF_VOLUME_MAX_DB: DEFAULT_VOLUME_MAX_DB,
        CONF_VOLUME_CURVE_MODE: DEFAULT_VOLUME_CURVE_MODE,
        CONF_VOLUME_CURVE: DEFAULT_VOLUME_CURVE,
        CONF_VOLUME_POINT_25_DB: round(point_25, 1),
        CONF_VOLUME_POINT_50_DB: round(point_50, 1),
        CONF_VOLUME_POINT_75_DB: round(point_75, 1),
        CONF_MUTE_WITH_VOLUME: DEFAULT_MUTE_WITH_VOLUME,
    }


def _volume_range_schema() -> vol.Schema:
    """Return the range and curve-mode schema."""
    return vol.Schema(
        {
            vol.Required(CONF_VOLUME_MIN_DB): _db_selector(
                DEVICE_MIN_VOLUME_DB, DEVICE_MAX_VOLUME_DB
            ),
            vol.Required(CONF_VOLUME_MAX_DB): _db_selector(
                DEVICE_MIN_VOLUME_DB, DEVICE_MAX_VOLUME_DB
            ),
            vol.Required(CONF_VOLUME_CURVE_MODE): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(
                            value=VOLUME_CURVE_MODE_EXPONENT,
                            label="Exponent curve",
                        ),
                        selector.SelectOptionDict(
                            value=VOLUME_CURVE_MODE_FIVE_POINT,
                            label="Five-point curve",
                        ),
                    ]
                )
            ),
            vol.Required(CONF_MUTE_WITH_VOLUME): selector.BooleanSelector(),
        }
    )


def _exponent_schema() -> vol.Schema:
    """Return the exponent-curve schema."""
    return vol.Schema(
        {
            vol.Required(CONF_VOLUME_CURVE): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_VOLUME_CURVE,
                    max=MAX_VOLUME_CURVE,
                    step=0.001,
                    mode=selector.NumberSelectorMode.BOX,
                )
            )
        }
    )


def _five_point_schema(options: dict[str, Any]) -> vol.Schema:
    """Return controls for the 25%, 50%, and 75% curve points."""
    min_db = float(options[CONF_VOLUME_MIN_DB])
    max_db = float(options[CONF_VOLUME_MAX_DB])
    return vol.Schema(
        {
            vol.Required(CONF_VOLUME_POINT_25_DB): _db_selector(min_db, max_db),
            vol.Required(CONF_VOLUME_POINT_50_DB): _db_selector(min_db, max_db),
            vol.Required(CONF_VOLUME_POINT_75_DB): _db_selector(min_db, max_db),
        }
    )


def _five_point_suggestions(options: dict[str, Any]) -> dict[str, float]:
    """Keep valid stored points or derive points from the exponent curve."""
    try:
        profile = VolumeProfile.from_options(options)
    except ValueError:
        profile = VolumeProfile.from_options(
            options | {CONF_VOLUME_CURVE_MODE: VOLUME_CURVE_MODE_EXPONENT}
        )
    point_25, point_50, point_75 = profile.points_db[1:-1]
    return {
        CONF_VOLUME_POINT_25_DB: round(point_25, 1),
        CONF_VOLUME_POINT_50_DB: round(point_50, 1),
        CONF_VOLUME_POINT_75_DB: round(point_75, 1),
    }


def _db_selector(minimum: float, maximum: float) -> selector.NumberSelector:
    """Return a dB number selector."""
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=minimum,
            max=maximum,
            step=0.5,
            unit_of_measurement="dB",
            mode=selector.NumberSelectorMode.BOX,
        )
    )


def _find_configured_device(
    devices: tuple[MiniDSPDevice, ...],
    *,
    serial: int | None,
    device_url: str | None,
) -> MiniDSPDevice | None:
    """Find a configured device in a fresh discovery result."""
    for device in devices:
        if serial is not None and device.serial == serial:
            return device
        if serial is None and device.url == device_url:
            return device
    return None


def _entry_data(base_url: str, device: MiniDSPDevice) -> dict[str, Any]:
    """Build persisted config-entry data."""
    return {
        CONF_URL: base_url,
        CONF_DEVICE_ID: device.identity(base_url),
        CONF_DEVICE_URL: device.url,
        CONF_PRODUCT_NAME: device.product_name,
        CONF_SERIAL: device.serial,
    }
