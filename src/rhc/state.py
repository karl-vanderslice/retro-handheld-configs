from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

CURRENT_STATE_VERSION = 2


def _safe_device_key(device_id: str) -> str:
    digest = hashlib.sha256(device_id.encode("utf-8")).hexdigest()[:16]
    slug = "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in device_id)
    return f"{slug[:32]}-{digest}"


def state_file_for_device(state_dir: Path, device_id: str) -> Path:
    return state_dir / f"{_safe_device_key(device_id)}.json"


def read_device_state(state_dir: Path, device_id: str) -> dict:
    state_file = state_file_for_device(state_dir, device_id)
    if not state_file.exists():
        return {}
    return json.loads(state_file.read_text(encoding="utf-8"))


def _coerce_version(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def migrate_state_data(data: dict) -> tuple[dict, int, int, bool]:
    migrated = dict(data)
    from_version = _coerce_version(migrated.get("state_version"))
    version = from_version

    if version < 1:
        version = 1

    if version < 2:
        pull_stock = migrated.get("pull_stock")
        if not isinstance(pull_stock, dict):
            fallback = migrated.get("pull_backups")
            if not isinstance(fallback, dict):
                fallback = migrated.get("pull_vanilla")
            if isinstance(fallback, dict):
                pull_stock = fallback
            else:
                pull_stock = {}
        migrated["pull_stock"] = pull_stock
        migrated.pop("pull_vanilla", None)
        migrated.pop("pull_backups", None)
        version = 2

    migrated["state_version"] = CURRENT_STATE_VERSION
    changed = migrated != data
    return migrated, from_version, CURRENT_STATE_VERSION, changed


def migrate_state_file(path: Path, dry_run: bool = False) -> tuple[bool, int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    migrated, from_version, to_version, changed = migrate_state_data(data)
    if changed and not dry_run:
        path.write_text(json.dumps(migrated, indent=2) + "\n", encoding="utf-8")
    return changed, from_version, to_version


def validate_state_data(data: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(data, dict):
        return ["state file root must be a JSON object"], []

    version = _coerce_version(data.get("state_version"))
    if version <= 0:
        errors.append("missing or invalid state_version")
    elif version > CURRENT_STATE_VERSION:
        errors.append(
            f"unsupported future state_version={version} (max supported={CURRENT_STATE_VERSION})"
        )
    elif version < CURRENT_STATE_VERSION:
        warnings.append(
            f"state_version={version} is older than current={CURRENT_STATE_VERSION}; "
            "run `rhc migrate-state`"
        )

    device_id = data.get("device_id")
    if not isinstance(device_id, str) or not device_id:
        errors.append("missing or invalid device_id")

    last_command = data.get("last_command")
    if not isinstance(last_command, str) or not last_command:
        errors.append("missing or invalid last_command")

    updated_at = data.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at:
        errors.append("missing or invalid updated_at")
    else:
        try:
            datetime.fromisoformat(updated_at)
        except ValueError:
            errors.append("updated_at must be ISO-8601 datetime")

    for legacy_key in ("pull_backups", "pull_vanilla"):
        if legacy_key in data:
            warnings.append(f"legacy key present: {legacy_key}; run `rhc migrate-state`")

    pull_stock = data.get("pull_stock")
    if pull_stock is not None:
        if not isinstance(pull_stock, dict):
            errors.append("pull_stock must be an object when present")
        else:
            for profile, record in pull_stock.items():
                if not isinstance(profile, str) or not profile:
                    errors.append("pull_stock has invalid empty/non-string profile key")
                    continue
                if not isinstance(record, dict):
                    errors.append(f"pull_stock[{profile}] must be an object")
                    continue
                synced_at = record.get("last_synced_at")
                if synced_at is None:
                    warnings.append(f"pull_stock[{profile}] missing last_synced_at")
                elif not isinstance(synced_at, str):
                    errors.append(f"pull_stock[{profile}].last_synced_at must be a string")
                else:
                    try:
                        datetime.fromisoformat(synced_at)
                    except ValueError:
                        errors.append(
                            f"pull_stock[{profile}].last_synced_at must be ISO-8601 datetime"
                        )

    return errors, warnings


def validate_state_file(path: Path) -> tuple[int, list[str], list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    errors, warnings = validate_state_data(data)
    version = _coerce_version(data.get("state_version"))
    return version, errors, warnings


def iter_state_files(state_dir: Path) -> list[Path]:
    if not state_dir.exists():
        return []
    return sorted(path for path in state_dir.glob("*.json") if path.is_file())


def write_device_state(
    state_dir: Path,
    device_id: str,
    command: str,
    metadata: dict | None = None,
) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_file_for_device(state_dir, device_id)
    existing = {}
    if state_file.exists():
        existing_raw = json.loads(state_file.read_text(encoding="utf-8"))
        existing, _, _, _ = migrate_state_data(existing_raw)

    data = {
        **existing,
        "device_id": device_id,
        "last_command": command,
        "updated_at": datetime.now(tz=UTC).isoformat(),
        "state_version": CURRENT_STATE_VERSION,
    }

    if metadata:
        data.update(metadata)

    state_file.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
