from __future__ import annotations

import json
from pathlib import Path

from rhc.state import (
    CURRENT_STATE_VERSION,
    migrate_state_data,
    validate_state_data,
    write_device_state,
)


def test_migrate_state_data_promotes_legacy_pull_keys() -> None:
    legacy = {
        "device_id": "serial-1",
        "last_command": "pull-vanilla:profile",
        "updated_at": "2026-03-21T00:00:00+00:00",
        "pull_vanilla": {"profile": {"last_synced_at": "2026-03-21T00:00:00+00:00"}},
    }

    migrated, from_version, to_version, changed = migrate_state_data(legacy)

    assert changed is True
    assert from_version == 0
    assert to_version == CURRENT_STATE_VERSION
    assert migrated["state_version"] == CURRENT_STATE_VERSION
    assert "pull_vanilla" not in migrated
    assert migrated["pull_stock"]["profile"]["last_synced_at"] == "2026-03-21T00:00:00+00:00"


def test_validate_state_data_accepts_current_schema() -> None:
    data = {
        "state_version": CURRENT_STATE_VERSION,
        "device_id": "serial-1",
        "last_command": "hello",
        "updated_at": "2026-03-21T00:00:00+00:00",
        "pull_stock": {
            "profile": {
                "last_synced_at": "2026-03-21T00:00:00+00:00",
            }
        },
    }

    errors, warnings = validate_state_data(data)

    assert errors == []
    assert warnings == []


def test_write_device_state_sets_version(tmp_path: Path) -> None:
    write_device_state(tmp_path, "serial-2", "hello")

    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1

    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["state_version"] == CURRENT_STATE_VERSION
    assert payload["device_id"] == "serial-2"
