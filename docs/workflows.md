# Workflows

## Fresh device baseline (planned)

1. Connect device over USB.
2. Validate ADB communication.
3. Pull baseline config and metadata to `backups/Stock/`.
4. Record state marker in `.rhc-state/`.

## Managed customization apply

Prep once:

1. Run `just import-audio-assets` to copy source audio into `managed/<profile>/media/audio`.
2. Optionally run `just download-apks` to cache latest Obtainium outside the repo (`~/.cache/rhc/apks` by default).

Use `just customize-device` (or `rhc customize-device`) to apply these ADB steps:

1. Confirm SD reformat and partition removable card as public storage.
1. Download/install latest Obtainium and allow install-other-apps permissions.
    - Pre-Obtainium sideloads: `Pixel Guide Android` is installed from its GitHub releases source.
1. Apply managed Obtainium settings from `managed/<profile>/obtainium/settings-only.json.age` (or `settings-only.json` when unencrypted): `github-creds`, `gitlab-creds`, and `useFGService`.
    - Token precedence: `RHC_OBTAINIUM_GITHUB_TOKEN` / `RHC_OBTAINIUM_GITLAB_TOKEN`, then Bitwarden items `RHC_BW_OBTAINIUM_GITHUB_ITEM` / `RHC_BW_OBTAINIUM_GITLAB_ITEM` (requires unlocked `BW_SESSION`), then file values.
1. Download latest single-device Obtainium Emulation Pack JSON, copy it to `/sdcard/Download`, and automate Obtainium import.
    - Bootstrap `Aurora Store` from Obtainium first.
1. Install required apps from Aurora Store (`Firefox`, `CX File Explorer`, `Daijishō`, and profile-specific apps such as `YabaSanshiro 2 Pro`).
1. Install remaining required Obtainium apps (`RetroArch AArch64`, `Argosy`, and `GameNative`) through Obtainium automation.
    - Obtanium foreground service is disabled (`flutter.useFGService=false`) to hide the persistent foreground notification.
1. Remove preloaded ROM files from `/storage/emulated/0/ROMs` while preserving `systeminfo.txt`.
1. Push `managed/<profile>/media/audio` to `/storage/emulated/0/media/audio`.
1. Configure sounds:
    - `go_straight` → alarm
    - `lightning_shield` → charging
    - `sonic_ring` → notification
    - `star_light_zone` → ringtone
    - set system/ring/notification/alarm to a handheld-default level (about 30% with minimum level 2 fallback)
1. Set timezone to `America/New_York`.
1. Disable the lock screen.
1. Disable/uninstall Browser, Calendar, Camera, Clock, Files app, Gallery, MIX Explorer, Music, and Sim Toolkit.
1. Record completion timestamp in `.rhc-state/`.

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

Optional root-adbd helper:

- `just adb-root` attempts to enable root over ADB on the connected device.
- This succeeds only when the device/build supports root adbd; otherwise it exits with a clear failure.

## Encrypted Aurora backup + restore

Use these workflows to keep Aurora Store backups encrypted at rest in-repo.

Before running backup/restore, unlock Bitwarden in your current shell and export `BW_SESSION`:

- `export BW_SESSION="$(bw unlock --raw)"`

Bootstrap local untracked identity file from Bitwarden:

- `just bootstrap-age-key`
- Optional overrides: `just bootstrap-age-key bw_item="<item-id-or-name>" out_file=".rhc-secrets/age-identity.txt"`

1. Run `just backup-aurora-secure` to capture current Aurora app state.
    - Uses local identity file first (`RHC_AGE_IDENTITY_FILE` / `--identity-file`) when present.
    - Otherwise reads `age` secret key from Bitwarden (`bw get notes <item>`), derives the public recipient, and encrypts files.
    - Set the Bitwarden item via `RHC_BW_AGE_ITEM` or pass `--bw-item`.
    - Optional `just` passthrough: `just backup-aurora-secure bw_item="<item-id-or-name>"`.
    - Optional local identity passthrough: `just backup-aurora-secure identity_file=".rhc-secrets/age-identity.txt"`.
    - Writes encrypted files to `backups/Android/aurora-store/current/encrypted/`.
    - Uses a single backup version (`current`) and replaces it on each run.
    - Does not keep tarballs/archives in the repository.
1. Run `just restore-aurora-secure` to restore from encrypted snapshot.
    - Uses local identity file first (`RHC_AGE_IDENTITY_FILE` / `--identity-file`) when present.
    - Otherwise reads the same Bitwarden `age` secret key for decryption.
    - Uses `RHC_BW_AGE_ITEM`, `--bw-item`, or backup metadata (`bitwarden_item`) to locate the key source.
    - Optional `just` passthrough: `just restore-aurora-secure bw_item="<item-id-or-name>"`.
    - Optional local identity passthrough: `just restore-aurora-secure identity_file=".rhc-secrets/age-identity.txt"`.
    - Restores from `backups/Android/aurora-store/current/`.
    - Force-stops Aurora Store before restore operations.
