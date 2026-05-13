# AGENTS

## Snapshot

- Purpose: this repo manages retro handheld device configs, managed overlays,
  and stock/custom OS snapshots.
- Load order: load this file first. Repo-local prompt/skill overlays are not
  present yet.
- Scope: Android-based devices via ADB, SD-card-based devices via filesystem
  copy/sync, and snapshot state under `backups/` plus overlays under
  `managed/`.

## Operating Model

- Identify the target device and storage endpoints first.
- Detect prior operations from `.rhc-state/` marker files.
- Skip destructive or duplicate actions unless explicit `--force` is used.
- Pull stock snapshots before applying managed changes.
- Record operation metadata after successful runs.

## Working Rules

- Use `Justfile` targets with hermetic Nix tooling; do not install CLIs at
  runtime.
- Follow `clig.dev` for CLI UX and Conventional Commits for commit messages.
- Exclude Firebase telemetry and crash artifacts from backups.
- Keep linting, formatting, and pre-commit checks from traversing `backups/`.
- Treat device customization behavior as profile-specific. The current active
  target is `retroid-pocket-classic-6-button-gammaos-next`.
- Never delete from device storage unless an explicit destructive flag is
  provided.
- Prefer dry-run support for sync operations and validate ADB connectivity
  before transfer operations.

## Docs

- Keep `README.md` as the GitHub entrypoint and `docs/index.md` as the docs
  landing page.
- Do not add duplicate overview pages such as `docs/README.md`.
- Shard docs and managed config by device, platform, or workflow domain.
- Keep reference docs factual and brief; put recovery and setup flows in
  separate how-to guides.
