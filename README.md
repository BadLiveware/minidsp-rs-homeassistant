# miniDSP-rs for Home Assistant

A local Home Assistant custom integration for MiniDSP hardware managed by [`minidsp-rs`](https://github.com/mrene/minidsp-rs). It provides master audio controls and signal-level diagnostics without a cloud service.

## Features

- Master volume and mute through a Home Assistant media player
- Input source selection based on the connected MiniDSP hardware revision
- Configuration preset selection as media-player sound modes
- Dirac Live switch on devices that report Dirac support
- Input and output level sensors in dBFS
- Multiple DSPs connected to the same `minidspd` instance
- UI setup, connection validation, reconfiguration, diagnostics, and automatic recovery when a device is temporarily offline

Level sensors are disabled by default because continuously changing meter values can create substantial recorder history. Enable only the channels needed for dashboards or automations.

## Prerequisites

Install and configure `minidspd` on a computer that can access the MiniDSP device. Home Assistant must be able to reach its HTTP server.

The daemon listens only on localhost by default. To make it available on a trusted local network, edit `/etc/minidsp/config.toml`:

```toml
[http_server]
bind_address = "0.0.0.0:5380"
```

Restart `minidspd`, then verify the endpoint from another machine:

```console
curl http://MINIDSP_HOST:5380/devices
```

`minidspd` does not provide HTTP authentication. Do not expose port 5380 to the internet or an untrusted network.

## Installation with HACS

Until the integration is included in the default HACS catalog:

1. Open HACS in Home Assistant.
2. Open the menu and select **Custom repositories**.
3. Add `https://github.com/BadLiveware/minidsp-rs-homeassistant` as an **Integration** repository.
4. Search for **miniDSP-rs** and download it.
5. Restart Home Assistant.

Manual installation is also possible by copying `custom_components/minidsp_rs` into the Home Assistant configuration directory and restarting Home Assistant.

## Configuration

1. In Home Assistant, open **Settings → Devices & services**.
2. Select **Add integration** and search for **miniDSP-rs**.
3. Enter the daemon URL, such as `http://192.168.1.20:5380`.
4. If the daemon exposes more than one DSP, select the device to add.
5. Run **Add integration** again for each additional DSP on the same daemon.

Use **Reconfigure** on the integration entry if the daemon address changes. The configured DSP must be reachable at the new endpoint during reconfiguration.

## Entities

| Entity | Default | Purpose |
| --- | --- | --- |
| Media player | Enabled | Volume, mute, input source, and presets |
| Dirac Live switch | Enabled when supported | Enables or bypasses Dirac Live |
| Input level sensors | Disabled | Per-channel input meter in dBFS |
| Output level sensors | Disabled | Per-channel output meter in dBFS |

### Useful volume range

Home Assistant represents media-player volume from 0% to 100%, while much of a MiniDSP's full -127 dB to 0 dB range is usually silent or too loud for a specific system. The integration therefore defaults to this scoped nonlinear mapping:

```text
gain = -90 dB + 80 dB × volume^0.415
```

This maps 0% to -90 dB, 50% to -30 dB, and 100% to a safe default maximum of -10 dB. Open the integration entry and select **Configure** to set the minimum and maximum gain, then choose one of two curve editors:

- **Exponent curve:** retain the logarithmic-like formula and adjust one exponent. `1` is linear; values below `1` raise the quiet end faster.
- **Five-point curve:** set gain independently at 25%, 50%, and 75%. The configured minimum and maximum provide the 0% and 100% points. A smooth, monotonic curve connects all five points.

The scoped range and curve shape are separate: changing the minimum or maximum changes the safe operating range, while the selected curve controls how the volume slider moves through it.

The optional 0%-volume mute moves the device to the configured minimum without sending a hardware mute command, then restores the previous gain when unmuted. This can avoid popping on systems where MiniDSP hardware mute is audible. The exact current gain and active mapping are available through the media player's volume attributes, including `volume_db`, `volume_curve_mode`, and the configured range and control points.

The source list is derived from the hardware and DSP revision reported by `minidspd`. Advanced DSP configuration—routing, PEQ, crossovers, FIR, compressors, and per-channel settings—is outside the initial integration scope because the daemon status endpoint does not expose dependable readback for those settings.

## Troubleshooting

- **Unable to connect:** confirm the URL includes the correct host and port and that firewalls permit Home Assistant to reach it.
- **No devices found:** run `curl http://MINIDSP_HOST:5380/devices` and confirm that `minidspd` has discovered the hardware.
- **Entities unavailable:** verify the DSP is powered on and still appears in `/devices`. Device indexes may change; the integration resolves the configured device by serial number on every update.
- **Need diagnostic data:** open the integration entry in **Settings → Devices & services**, choose the menu, and download diagnostics. Network addresses are redacted.

## Development

The project uses [uv](https://docs.astral.sh/uv/) for a reproducible Home Assistant test environment:

```console
uv sync --group dev
uv run ruff check .
uv run ruff format . --check
uv run pytest --cov --cov-report=term-missing
```

See [Publishing](docs/publishing.md) for the release and HACS submission workflow.

## License

[MIT](LICENSE)
