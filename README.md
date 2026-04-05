# retro-handheld-configs

Scriptable, extensible tooling + config repo for retro handheld devices.

Current active customization scope is the Retroid Pocket Classic 6-button profile.
New devices should use profile-specific customization mappings rather than reusing
this device's assumptions by default.

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
just import-audio-assets
just download-apks
just customize-auto
just format-sd yes_format_sd=true
just configure-apks
just import-obtainium-pack cleanup_rpc=true
just adb-root
just backup-aurora-secure
just restore-aurora-secure
just migrate-state dry_run=true
just state-doctor
just docs-build
```

Global CLI output options for all commands:

- `--output text|json` (default: `text`)
- `--log-file <path>` to append structured JSON events
- `--no-color` to disable ANSI color in text mode

## Current CLI commands

- `rhc hello` — verifies ADB availability, checks connected devices, and prints a greeting for the selected device.
- `rhc pull-backup` — reads a device profile from `configs/devices/` and pulls configured paths into `backups/<Tier>/...`.
- `rhc pull-stock` — alias for `rhc pull-backup` (recommended wording for stock snapshot flows).
	- Use `--root` to pull profile `root_source_paths` via `su` for app-private emulator data.
- `rhc migrate-state` — migrates `.rhc-state/*.json` files to the current schema version.
- `rhc state-doctor` — validates `.rhc-state/*.json` files and reports schema/field problems.
- `rhc import-audio-assets` — one-time copy from local audio source path into `managed/<profile>/media/audio` (preserves structure).
- `rhc download-apks` — downloads latest Obtainium APK into an external cache (default: `~/.cache/rhc/apks`) and downloads latest single-device Obtainium Emulation Pack JSON into `~/Downloads`.
- `rhc customize-device` — runs ADB customization steps:
	- formats SD card as removable/public storage by default (or use `--yes-format-sd` for non-interactive confirm)
	- use `--skip-format-sd` to leave SD card untouched
	- downloads latest Obtainium APK at runtime (temporary directory), installs it, and enables install-other-apps app-op for Obtainium and Aurora Store
	- restores encrypted Aurora backup after APK setup (kills Aurora process before restore)
	- applies managed Obtainium settings before import when present (`managed/<profile>/obtainium/settings-only.json.age` preferred, `settings-only.json` supported): `github-creds`, `gitlab-creds`, and `useFGService`
	  - token resolution precedence: `RHC_OBTAINIUM_GITHUB_TOKEN`/`RHC_OBTAINIUM_GITLAB_TOKEN` env vars, then Bitwarden items `RHC_BW_OBTAINIUM_GITHUB_ITEM`/`RHC_BW_OBTAINIUM_GITLAB_ITEM` (requires unlocked `BW_SESSION`), then file values
	- downloads latest single-device Obtainium Emulation Pack JSON, copies it to `/sdcard/Download/`, and automates Obtainium import via `uiautomator2`
	  - bootstraps `Aurora Store` from Obtainium first
	  - then installs required Aurora apps
	  - then installs remaining required Obtainium apps (`RetroArch AArch64`, `Argosy`, and `GameNative`)
	- installs from Aurora Store:
		- Firefox
		- CX File Explorer
		- Daijishō
		- YabaSanshiro 2 Pro (6-button Retroid profile only)
	- installs required Obtainium apps through Obtainium automation (no direct sideload in customization flow)
	- disables Obtanium foreground service (`flutter.useFGService=false`) to hide persistent foreground notifications
	- supports `--cleanup-rpc` to stop `uiautomator2` RPC service after import automation
	- removes preloaded ROM files under `/storage/emulated/0/ROMs` while preserving `systeminfo.txt`
	- pushes `managed/<profile>/media/audio` to `/storage/emulated/0/media/audio` preserving structure
	- sets system sounds:
		- `go_straight` as alarm
		- `lightning_shield` as charging sound
		- `sonic_ring` as default notification
		- `star_light_zone` as ringtone
		- lowers ring/notification/alarm volumes to a handheld-friendly level
	- sets timezone to `America/New_York`
	- disables lock screen
	- removes DraStic, M64Plus FZ, PPSSPP, and Flycast for user 0 while keeping app data (`pm uninstall -k --user 0`)
	  - Flycast package for this profile: `com.flycast.emulator`
	- disables or uninstalls Browser, Calendar, Camera, Clock, Files app, Gallery, MIX Explorer, Music, and Sim Toolkit when present
	- supports `--target` (repeatable) for partial runs: `format-sd`, `apks`, `aurora-restore`, `aurora-install-apps`, `obtainium-import`, `rom-cleanup`, `audio-sync`, `system-sounds`, `auto-rotate`, `timezone`, `lockscreen`, `remove-apps-keep-data`, `remove-apps`
	- supports machine-friendly output with `--output json` and persisted event logs via `--log-file`

Encrypted Android app backup workflows:

- `just bootstrap-age-key` — pulls the `age` identity from Bitwarden and writes it to a local untracked file (default: `.rhc-secrets/age-identity.txt`).
	- Requires Bitwarden to be unlocked in the current shell (`BW_SESSION`).
	- Uses `RHC_BW_AGE_ITEM` or `bw_item="..."` to select the source item.
	- Uses `RHC_AGE_IDENTITY_FILE` or `out_file="..."` for destination path.
- `just backup-aurora-secure` — captures Aurora Store private + external app data over ADB and writes only `age`-encrypted files into `backups/Android/aurora-store/current/encrypted/`.
	- Uses a local identity file when available (`RHC_AGE_IDENTITY_FILE` or `--identity-file`), otherwise reads from Bitwarden (`RHC_BW_AGE_ITEM` / `--bw-item`).
	- You can also pass the item through `just`: `just backup-aurora-secure bw_item="<item-id-or-name>"`.
	- You can also pass the identity file through `just`: `just backup-aurora-secure identity_file=".rhc-secrets/age-identity.txt"`.
	- Uses a single in-repo backup version (`current`) and replaces it on each run.
	- No tarballs/archives are retained in-repo by this workflow.
- `just restore-aurora-secure` — decrypts the `current` Aurora backup and restores it to device storage.
	- Uses a local identity file when available (`RHC_AGE_IDENTITY_FILE` or `--identity-file`), otherwise reads from Bitwarden (`RHC_BW_AGE_ITEM` / `--bw-item` / metadata hint).
	- You can also pass the item through `just`: `just restore-aurora-secure bw_item="<item-id-or-name>"`.
	- You can also pass the identity file through `just`: `just restore-aurora-secure identity_file=".rhc-secrets/age-identity.txt"`.
	- Force-stops Aurora (`am force-stop com.aurora.store`) before restore.
	- Uses a single backup version (`current`).

`just customize-auto` skips SD formatting by default; pass `format_sd="true"` to include formatting.

Target-specific wrappers:

- `just format-sd yes_format_sd=true`
- `just configure-apks`
- `just import-obtainium-pack cleanup_rpc=true`
- `just customize-target target="timezone"`

Legacy aliases (`customize-device*`) are still available for backward compatibility.

## Workflow entrypoint

- Use the `Justfile` for all day-to-day workflows.
- Prefer `just <target>` over invoking `nix develop`, `rhc`, `pytest`, or `ruff` directly.
- Tooling is hermetic and Nix-managed: required CLIs must be declared in `flake.nix`.
- Do not install workflow dependencies at runtime from recipes/scripts.
- Lint/format/pre-commit checks exclude `backups/` so captured snapshots are preserved as-is.

## Device profiles

Profiles live in `configs/devices/*.toml`.

Included profile:

- `retroid-pocket-classic-6-button-gammaos-next`
	- Primary use: Sega, DOS, and Arcade emulation workflows.
	- OS: GammaOS Next `v.1.0.0-RETROIDPOCKETCLASSIC`
	- Tier: `GammaOSNext` (custom OS; not stock)
	- ADB root guidance:
		- Run `just adb-root` before root-sensitive pulls/restores.
		- If it reports root is disabled by system setting, enable on-device:
			- `Settings -> System -> Developer options -> ADB Root access` (or `Rooted debugging` on some builds).
		- Re-run `just adb-root` after enabling the setting.
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

## Managed assets tree

Managed customizations are grouped by profile so each device can have its own theme/config set.

Examples:

- `managed/retroid-pocket-classic-6-button-gammaos-next/media/audio/...`
- `managed/retroid-pocket-classic-4-button-gammaos-next/media/audio/...` (when added)

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
