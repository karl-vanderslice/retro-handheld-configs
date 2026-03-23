# Workflows

## Fresh device baseline (planned)

1. Connect device over USB.
2. Validate ADB communication.
3. Pull baseline config and metadata to `backups/Stock/`.
4. Record state marker in `.rhc-state/`.

## Managed customization apply

Prep once:

1. Run `just import-audio-assets` to copy source audio into `managed/<profile>/media/audio`.
2. Optionally run `just download-apks` to cache latest Aurora Store and Obtainium outside the repo (`~/.cache/rhc/apks` by default).

Use `just customize-device` (or `rhc customize-device`) to apply these ADB steps:

1. Confirm SD reformat and partition removable card as public storage.
2. Download/install latest Aurora Store + Obtainium and allow install-other-apps permissions.
3. Remove preloaded ROM files from `/storage/emulated/0/ROMs` while preserving `systeminfo.txt`.
4. Push `managed/<profile>/media/audio` to `/storage/emulated/0/media/audio`.
5. Configure sounds:
	- `go_straight` → alarm
	- `lightning_shield` → charging
	- `sonic_ring` → notification
	- `star_light_zone` → ringtone
6. Set timezone to `America/New_York`.
7. Disable the lock screen.
8. Disable/uninstall Browser, Calendar, Camera, Clock, Files app, Gallery, MIX Explorer, Music, and Sim Toolkit.
9. Record completion timestamp in `.rhc-state/`.
