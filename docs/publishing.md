# Publishing miniDSP-rs for Home Assistant

This repository is structured for installation as a HACS integration. Publishing requires a public GitHub repository and a full GitHub release.

## Prepare the GitHub repository

1. Create the public repository `BadLiveware/minidsp-rs-ha` and push the `main` branch.
2. Add a concise repository description, such as `Home Assistant integration for MiniDSP devices managed by minidsp-rs`.
3. Enable GitHub Issues.
4. Add searchable topics such as `home-assistant`, `hacs`, `minidsp`, `minidsp-rs`, `custom-component`, and `home-automation`.
5. Confirm the **Validate** workflow passes. It runs Ruff, pytest, Hassfest, and HACS validation.

The repository already includes the required HACS layout:

```text
custom_components/minidsp_rs/
  __init__.py
  manifest.json
  brand/icon.png
hacs.json
README.md
```

## Publish a release

1. Update `version` in `custom_components/minidsp_rs/manifest.json`.
2. Update the project version in `pyproject.toml` to the same value.
3. Run the local checks:

   ```console
   uv sync --frozen --group dev
   uv run ruff check .
   uv run ruff format . --check
   uv run pytest --cov --cov-report=term-missing
   ```

4. Commit and push the version change.
5. Wait for the GitHub validation workflow to pass.
6. Create a GitHub release with a matching semantic-version tag, for example `v0.1.0`. A tag without a GitHub release does not count as a HACS release.
7. Test installation by adding the repository to HACS as a custom **Integration** repository.

HACS reads the GitHub release tag as the available version and the integration manifest version as the installed version. Keep them aligned.

## Request inclusion in the default HACS catalog

Default inclusion is optional; users can install the integration as a custom repository immediately after it is public.

Before submitting:

- Confirm the repository can be added as a custom HACS repository.
- Confirm the HACS and Hassfest GitHub Actions pass without ignored checks.
- Confirm at least one GitHub release exists.
- Confirm the repository has a description, topics, enabled issues, README, `hacs.json`, valid integration manifest, and `brand/icon.png`.

Fork [`hacs/default`](https://github.com/hacs/default), create a branch from `master`, add `BadLiveware/minidsp-rs-ha` alphabetically to the `integration` file, and open a pull request using the repository's template. The pull request must be opened by the repository owner or a major contributor and must allow maintainer edits.

Review may take time. Custom-repository installation remains available while the inclusion request is pending.

## References

- [HACS integration requirements](https://hacs.xyz/docs/publish/integration/)
- [HACS general publishing requirements](https://hacs.xyz/docs/publish/start/)
- [HACS default inclusion](https://hacs.xyz/docs/publish/include/)
- [Home Assistant integration manifest](https://developers.home-assistant.io/docs/creating_integration_manifest/)
