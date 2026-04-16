# Retro Handheld Configs

[← docs.vslice.net](https://docs.vslice.net){ .md-button }

Scriptable toolkit for managing retro handheld devices. Captures stock state,
applies managed customizations, and runs idempotent ADB and SD-card operations
across devices.

Currently targets the **Retroid Pocket Classic** (6-button profile). New devices
use profile-specific customization mappings.

## What it does

- **Stock snapshots** — pulls baseline configs and app data from fresh installs
- **Managed customizations** — pushes audio assets, APKs, Obtainium packs,
  system settings, and app configuration via ADB
- **Encrypted backups** — Aurora Store backup and restore with age encryption
  backed by Bitwarden
- **SD card workflows** — format, partition, and bootstrap removable storage

## Quick start

```bash
just                  # list all targets
just check            # validate environment
just customize-auto   # full device customization
```

## Guides

- [Workflows](workflows.md) — step-by-step device setup, customization,
  and backup procedures
