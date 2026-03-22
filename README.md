# retro-handheld-configs

Scriptable, extensible tooling + config repo for retro handheld devices.

This project manages:

- Device and emulator configs
- Customizations (managed overlays)
- Snapshot backups for stock and custom OS installs
- ADB-based Android device workflows and SD-card workflows

## Goals

- Reproducible development environment via Nix
- Idempotent operations with local state/cache markers
- Strong CLI ergonomics following [clig.dev](https://clig.dev/)
- Conventional Commit enforcement via pre-commit hooks
- Project docs under `docs/` via MkDocs

## Quick start

Use `just` as the single project entrypoint.

```bash
just
just check
```

Common tasks:

```bash
just hello
just pull-stock
just pull-stock-root force=true
just migrate-state dry_run=true
just state-doctor
just docs-build
```

## Current CLI commands

- `rhc hello` — verifies ADB availability, checks connected devices, and prints a greeting for the selected device.
- `rhc pull-backup` — reads a device profile from `configs/devices/` and pulls configured paths into `backups/<Tier>/...`.
- `rhc pull-stock` — alias for `rhc pull-backup` (recommended wording for stock snapshot flows).
	- Use `--root` to pull profile `root_source_paths` via `su` for app-private emulator data.
- `rhc migrate-state` — migrates `.rhc-state/*.json` files to the current schema version.
- `rhc state-doctor` — validates `.rhc-state/*.json` files and reports schema/field problems.

## Workflow entrypoint

- Use the `Justfile` for all day-to-day workflows.
- Prefer `just <target>` over invoking `nix develop`, `rhc`, `pytest`, or `ruff` directly.
- Lint/format/pre-commit checks exclude `backups/` so captured snapshots are preserved as-is.

## Device profiles

Profiles live in `configs/devices/*.toml`.

Included profile:

- `retroid-pocket-classic-6-button-gammaos-next`
	- OS: GammaOS Next `v.1.0.0-RETROIDPOCKETCLASSIC`
	- Tier: `GammaOSNext` (custom OS; not stock)
	- Pull paths:
		- `/storage/emulated/0/PSP`
		- `/storage/emulated/0/Retroarch`
		- `/storage/emulated/0/Android/data/com.retroarch.aarch64`
	- Root pull paths (`--root`):
		- `/data/user/0/com.dsemu.drastic/files/DraStic`
		- `/data/user/0/com.dsemu.drastic/shared_prefs`
		- `/data/user/0/org.mupen64plusae.v3.fzurita/files`
		- `/data/user/0/org.mupen64plusae.v3.fzurita/shared_prefs`
		- `/data/user/0/com.retroarch.aarch64/shared_prefs/com.retroarch.aarch64_preferences.xml`
	- Excludes:
		- `exclude_substrings = ["firebase"]`

## Backup tree

All pulled backups live under `backups/`, split by top-level tier.

Examples:

- `backups/Stock/` — stock device firmware snapshots (planned)
- `backups/GammaOSNext/` — GammaOS Next snapshots
- `backups/RockNix/` — RockNix snapshots (planned)

## State/cache behavior

The CLI stores operation metadata in `.rhc-state/`.

- Device identity is mapped to a file-safe key.
- Each command can write a timestamped marker to support idempotent flows.
- State files include `state_version` for explicit schema tracking.
- Use `rhc state-doctor` to validate file integrity before or after migration.
- Use `rhc migrate-state` to upgrade older state files to the latest schema.
- Future pull/push commands should use these markers to skip already-processed steps unless `--force` is supplied.

## Conventional commits

Conventional Commit format is enforced using Nix-provisioned pre-commit hooks.

Example:

- `feat(cli): add initial adb hello command`
- `chore(nix): add dev shell and git hooks`

## Layout

- `src/rhc/` — Python CLI implementation
- `tests/` — pytest suite
- `Justfile` — canonical automation entrypoint
- `docs/` — MkDocs documentation source
- `mkdocs.yml` — MkDocs configuration
- `flake.nix` / `flake.lock` — Nix flake and pinned inputs

## direnv

`/.envrc` is committed and uses `use flake`.

```bash
direnv allow
```
