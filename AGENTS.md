# AGENTS

This repository is intended for agent-assisted management of retro handheld device configs and baseline/stock snapshots.

## Scope

- Manage Android-based devices via ADB.
- Manage SD-card-based devices via filesystem copy/sync.
- Track both:
  - `backups/Stock/` snapshots (fresh stock post-install state)
  - `backups/<CustomOS>/` snapshots (e.g. `GammaOSNext`, `RockNix`)
  - `managed/` custom overlays/configs
- Keep workflows idempotent and safe with cache/state markers.

## Operating model

1. Identify target device and storage endpoints.
2. Detect prior operations from `.rhc-state/` marker files.
3. Skip destructive or duplicate actions unless explicit `--force` is used.
4. Pull stock snapshots before applying managed changes.
5. Record operation metadata after successful runs.

## Repository conventions

- CLI UX should follow https://clig.dev/.
- Commit messages must follow Conventional Commits.
- Documentation lives under `docs/` and is built with MkDocs.
- Nix is the source of truth for developer tooling.
- `Justfile` is the canonical project entrypoint; run workflows via `just` targets.
- Tooling must be hermetic: do not install CLIs at runtime (no curl-pipe installers, brew, npm -g, etc.) inside workflows.
- If a CLI is required, add it to `flake.nix` and invoke it through `nix develop -c ...`.
- Exclude Firebase telemetry/crash artifacts from backups.
- Linting/formatting/pre-commit checks must ignore `backups/`.

## Safety rules

- Never delete from device storage unless an explicit destructive flag is provided.
- Prefer dry-run support for future sync operations.
- Validate ADB connectivity and selected serial before transfer operations.
- Use deterministic paths and timestamps in state files.
