# Workflows

## Fresh device baseline (planned)

1. Connect device over USB.
2. Validate ADB communication.
3. Pull baseline config and metadata to `backups/Stock/`.
4. Record state marker in `.rhc-state/`.

## Managed customization apply

Tooling policy: workflows are hermetic. Required CLIs must come from `flake.nix` via `nix develop -c ...`; do not install dependencies at runtime.

Prep once:

1. Run `just import-audio-assets` to copy source audio into `managed/<profile>/media/audio`.
2. Optionally run `just download-apks` to cache latest Obtainium outside the repo (`~/.cache/rhc/apks` by default).

Use `just customize-device` (or `rhc customize-device`) to apply these ADB steps:

1. Confirm SD reformat and partition removable card as public storage.
2. Download/install latest Obtainium and allow install-other-apps permissions.
3. Download latest single-device Obtainium Emulation Pack JSON, copy it to `/sdcard/Download`, and automate Obtainium import.
4. Remove preloaded ROM files from `/storage/emulated/0/ROMs` while preserving `systeminfo.txt`.
5. Push `managed/<profile>/media/audio` to `/storage/emulated/0/media/audio`.
6. Configure sounds:
	- `go_straight` → alarm
	- `lightning_shield` → charging
	- `sonic_ring` → notification
	- `star_light_zone` → ringtone
7. Set timezone to `America/New_York`.
8. Disable the lock screen.
9. Disable/uninstall Browser, Calendar, Camera, Clock, Files app, Gallery, MIX Explorer, Music, and Sim Toolkit.
10. Record completion timestamp in `.rhc-state/`.

Targeted runs are supported with `--target` (repeatable), for example:

- SD format only: `just format-sd yes_format_sd=true`
- APK setup only: `just configure-apks`
- Obtainium import only: `just import-obtainium-pack cleanup_rpc=true`
- CLI direct: `rhc customize-device --target timezone --target lockscreen`

Use `--cleanup-rpc` on `rhc customize-device` (or `cleanup_rpc=true` in `just` wrappers)
to stop the `uiautomator2` RPC service after import automation completes.

Machine-readable output is available on all commands:

- `--output json` for JSONL events on stdout/stderr
- `--log-file /path/to/rhc.log.jsonl` for persisted JSON event logs
