# Workflows

## Fresh device baseline (planned)

1. Connect device over USB.
2. Validate ADB communication.
3. Pull baseline config and metadata to `backups/Stock/`.
4. Record state marker in `.rhc-state/`.

## Managed customization apply (planned)

1. Select profile.
2. Compare against state marker.
3. Push only needed files.
4. Record completion timestamp.
