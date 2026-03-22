from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import tomllib
from datetime import UTC, datetime
from pathlib import Path

from rhc.state import (
    iter_state_files,
    migrate_state_file,
    read_device_state,
    validate_state_file,
    write_device_state,
)


def _state_dir() -> Path:
    return Path(os.environ.get("RHC_STATE_DIR", ".rhc-state"))


def _adb_path() -> str:
    adb = shutil.which("adb")
    if adb is None:
        raise RuntimeError("adb is not available in PATH. Enter `nix develop` first.")
    return adb


def _connected_devices(adb: str) -> list[str]:
    result = subprocess.run(
        [adb, "devices"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    devices: list[str] = []
    for line in result.stdout.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        serial, status, *_ = line.split()
        if status == "device":
            devices.append(serial)
    return devices


def _device_model(adb: str, serial: str) -> str:
    result = subprocess.run(
        [adb, "-s", serial, "shell", "getprop", "ro.product.model"],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    return result.stdout.strip() or "unknown-model"


def _select_device(serial: str | None, devices: list[str]) -> str | None:
    if not devices:
        print("No attached ADB devices detected.", file=sys.stderr)
        return None

    if serial is None:
        return devices[0]

    if serial not in devices:
        print(f"error: requested serial '{serial}' is not connected", file=sys.stderr)
        return None

    return serial


def _load_profile(profile: str) -> dict:
    profile_path = Path("configs") / "devices" / f"{profile}.toml"
    if not profile_path.exists():
        raise RuntimeError(f"profile not found: {profile_path}")

    with profile_path.open("rb") as fh:
        return tomllib.load(fh)


def _remote_exists(adb: str, serial: str, remote_path: str) -> bool:
    result = subprocess.run(
        [adb, "-s", serial, "shell", "ls", "-d", remote_path],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    return result.returncode == 0


def _root_remote_exists(adb: str, serial: str, remote_path: str) -> bool:
    result = subprocess.run(
        [adb, "-s", serial, "shell", "su", "-c", f"test -e {shlex.quote(remote_path)}"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    return result.returncode == 0


def _package_uid(adb: str, serial: str, package_name: str) -> str | None:
    result = subprocess.run(
        [adb, "-s", serial, "shell", "dumpsys", "package", package_name],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    if result.returncode != 0:
        return None

    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("userId="):
            value = line.split("=", 1)[1].strip()
            if value.isdigit():
                return value
    return None


def _is_within(base: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(base)
        return True
    except ValueError:
        return False


def _should_exclude_member(member_name: str, exclude_substrings: list[str]) -> bool:
    lowered = member_name.lower()
    return any(token in lowered for token in exclude_substrings)


def _pull_root_path(
    adb: str,
    serial: str,
    remote_path: str,
    destination_root: Path,
    exclude_substrings: list[str],
) -> None:
    relative_remote = remote_path.lstrip("/")
    tar_command = f"tar -C / -cf - {shlex.quote(relative_remote)}"

    su_args = ["su", "-c", tar_command]
    data_user_prefix = "/data/user/0/"
    if remote_path.startswith(data_user_prefix):
        remainder = remote_path[len(data_user_prefix) :]
        package_name = remainder.split("/", 1)[0]
        if package_name:
            uid = _package_uid(adb, serial, package_name)
            if uid is not None:
                su_args = ["su", uid, "-c", tar_command]

    tmp_tar_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="rhc-root-",
            suffix=".tar",
            delete=False,
        ) as tmp_file:
            tmp_tar_path = Path(tmp_file.name)

        with tmp_tar_path.open("wb") as out_file:
            subprocess.run(
                [adb, "-s", serial, "exec-out", *su_args],
                stdout=out_file,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=300,
            )

        if tmp_tar_path.stat().st_size == 0:
            raise RuntimeError("received empty tar stream")

        destination_abs = destination_root.resolve()
        with tarfile.open(tmp_tar_path, mode="r:*") as archive:
            for member in archive:
                target_path = (destination_root / member.name).resolve()
                if not _is_within(destination_abs, target_path):
                    continue
                if _should_exclude_member(member.name, exclude_substrings):
                    continue
                archive.extract(member, path=destination_root, filter="data")
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"failed to pull root path {remote_path}: {exc}") from exc
    finally:
        if tmp_tar_path is not None and tmp_tar_path.exists():
            tmp_tar_path.unlink(missing_ok=True)


def cmd_hello(serial: str | None) -> int:
    try:
        adb = _adb_path()
        devices = _connected_devices(adb)
    except subprocess.TimeoutExpired:
        print(
            "error: timed out waiting for `adb devices`; check USB mode/authorization",
            file=sys.stderr,
        )
        return 1
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    selected = _select_device(serial, devices)
    if selected is None:
        return 1

    try:
        model = _device_model(adb, selected)
    except subprocess.TimeoutExpired:
        print(f"error: timed out reading model for {selected}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"error: failed to read model for {selected}: {exc}", file=sys.stderr)
        return 1

    previous = read_device_state(_state_dir(), selected)
    write_device_state(_state_dir(), selected, command="hello")

    greeting = f"Hello, {model}! (serial: {selected})"
    print(greeting)

    if previous:
        updated_at = previous.get("updated_at", "unknown")
        print(f"Previous cached operation at: {updated_at}")
    else:
        print("No previous local state cache found for this device.")

    return 0


def cmd_pull_backup(profile: str, serial: str | None, force: bool, use_root: bool) -> int:
    try:
        adb = _adb_path()
        devices = _connected_devices(adb)
        cfg = _load_profile(profile)
    except subprocess.TimeoutExpired:
        print(
            "error: timed out waiting for `adb devices`; check USB mode/authorization",
            file=sys.stderr,
        )
        return 1
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    selected = _select_device(serial, devices)
    if selected is None:
        return 1

    previous = read_device_state(_state_dir(), selected)
    pull_stock = previous.get(
        "pull_stock",
        previous.get("pull_backups", previous.get("pull_vanilla", {})),
    )
    marker_key = f"{profile}:root" if use_root else profile
    if pull_stock.get(marker_key) and not force:
        print(
            f"Skipping pull: profile '{profile}' already synced at "
            f"{pull_stock[marker_key].get('last_synced_at', 'unknown')} "
            "(use --force to pull again)."
        )
        return 0

    backup_tier = cfg.get("backup_tier")
    if not isinstance(backup_tier, str) or not backup_tier:
        print("error: profile is missing a valid 'backup_tier'", file=sys.stderr)
        return 1

    backup_subdir = cfg.get("backup_subdir", cfg.get("vanilla_subdir"))
    if not isinstance(backup_subdir, str) or not backup_subdir:
        print("error: profile is missing a valid 'backup_subdir'", file=sys.stderr)
        return 1

    source_paths = cfg.get("source_paths")
    root_source_paths = cfg.get("root_source_paths", [])
    exclude_substrings = cfg.get("exclude_substrings", ["firebase"])
    if not isinstance(source_paths, list) or not source_paths:
        print("error: profile is missing a valid 'source_paths' list", file=sys.stderr)
        return 1
    if not isinstance(root_source_paths, list):
        print("error: profile has invalid 'root_source_paths' list", file=sys.stderr)
        return 1
    if not isinstance(exclude_substrings, list):
        print("error: profile has invalid 'exclude_substrings' list", file=sys.stderr)
        return 1

    normalized_excludes: list[str] = []
    for entry in exclude_substrings:
        if isinstance(entry, str) and entry.strip():
            normalized_excludes.append(entry.strip().lower())

    selected_paths = root_source_paths if use_root else source_paths
    if not selected_paths:
        mode_name = "root_source_paths" if use_root else "source_paths"
        print(f"error: profile has empty '{mode_name}'", file=sys.stderr)
        return 1

    destination_root = Path("backups") / backup_tier / backup_subdir
    copied_any = False

    for remote_path in selected_paths:
        if not isinstance(remote_path, str) or not remote_path.startswith("/"):
            print(f"warning: invalid remote path in profile: {remote_path!r}")
            continue

        exists = (
            _root_remote_exists(adb, selected, remote_path)
            if use_root
            else _remote_exists(adb, selected, remote_path)
        )
        if not exists:
            print(f"warning: remote path not found, skipping: {remote_path}")
            continue

        local_path = destination_root / remote_path.lstrip("/")
        local_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Pulling {remote_path} -> {local_path}")
        try:
            if use_root:
                _pull_root_path(
                    adb,
                    selected,
                    remote_path,
                    destination_root,
                    exclude_substrings=normalized_excludes,
                )
            else:
                subprocess.run(
                    [adb, "-s", selected, "pull", remote_path, str(local_path)],
                    check=True,
                )
        except (subprocess.CalledProcessError, RuntimeError) as exc:
            print(f"error: failed to pull {remote_path}: {exc}", file=sys.stderr)
            return 1

        copied_any = True

    if not copied_any:
        print("No configured remote paths were pulled.", file=sys.stderr)
        return 1

    pull_stock[marker_key] = {"last_synced_at": datetime.now(tz=UTC).isoformat()}
    write_device_state(
        _state_dir(),
        selected,
        command=f"pull-backup:{profile}{':root' if use_root else ''}",
        metadata={"pull_stock": pull_stock},
    )

    print(f"Backup pull completed at {destination_root}")
    return 0


def cmd_migrate_state(dry_run: bool) -> int:
    state_dir = _state_dir()
    files = iter_state_files(state_dir)
    if not files:
        print(f"No state files found in {state_dir}")
        return 0

    migrated_count = 0
    unchanged_count = 0
    failed_count = 0

    for file_path in files:
        try:
            changed, from_version, to_version = migrate_state_file(file_path, dry_run=dry_run)
        except (OSError, ValueError) as exc:
            failed_count += 1
            print(f"error: failed to migrate {file_path.name}: {exc}", file=sys.stderr)
            continue

        if changed:
            migrated_count += 1
            mode = "would migrate" if dry_run else "migrated"
            print(f"{mode}: {file_path.name} (v{from_version} -> v{to_version})")
        else:
            unchanged_count += 1
            print(f"unchanged: {file_path.name}")

    summary_mode = "dry-run" if dry_run else "applied"
    print(
        f"Migration {summary_mode}: {migrated_count} migrated, "
        f"{unchanged_count} unchanged, {failed_count} failed."
    )

    return 1 if failed_count else 0


def cmd_state_doctor() -> int:
    state_dir = _state_dir()
    files = iter_state_files(state_dir)
    if not files:
        print(f"No state files found in {state_dir}")
        return 0

    error_count = 0
    warning_count = 0
    ok_count = 0

    for file_path in files:
        try:
            version, errors, warnings = validate_state_file(file_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            error_count += 1
            print(f"error: {file_path.name}: invalid JSON or unreadable file ({exc})")
            continue

        if errors:
            error_count += 1
            print(f"invalid: {file_path.name} (state_version={version})")
            for message in errors:
                print(f"  error: {message}")
        else:
            ok_count += 1
            print(f"ok: {file_path.name} (state_version={version})")

        if warnings:
            warning_count += len(warnings)
            for message in warnings:
                print(f"  warning: {message}")

    print(
        f"State doctor summary: {ok_count} valid, {error_count} invalid, {warning_count} warnings."
    )
    return 1 if error_count else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rhc",
        description="Retro handheld config manager.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    hello_parser = subparsers.add_parser(
        "hello",
        help="Say hello to a connected ADB device and write state marker.",
    )
    hello_parser.add_argument(
        "--serial",
        help="ADB serial to target. Defaults to first connected device.",
    )

    pull_backup_parser = subparsers.add_parser(
        "pull-backup",
        help="Pull backup snapshot paths from a profile into the repository.",
    )
    pull_backup_parser.add_argument(
        "--profile",
        default="retroid-pocket-classic-6-button-gammaos-next",
        help="Profile name in configs/devices/<profile>.toml.",
    )
    pull_backup_parser.add_argument(
        "--serial",
        help="ADB serial to target. Defaults to first connected device.",
    )
    pull_backup_parser.add_argument(
        "--force",
        action="store_true",
        help="Force pull even if cache state indicates prior completion.",
    )
    pull_backup_parser.add_argument(
        "--root",
        action="store_true",
        help="Use root mode and pull paths from profile 'root_source_paths'.",
    )

    pull_stock_parser = subparsers.add_parser(
        "pull-stock",
        help="Alias for pull-backup (recommended for stock snapshots).",
    )
    pull_stock_parser.add_argument(
        "--profile",
        default="retroid-pocket-classic-6-button-gammaos-next",
        help="Profile name in configs/devices/<profile>.toml.",
    )
    pull_stock_parser.add_argument(
        "--serial",
        help="ADB serial to target. Defaults to first connected device.",
    )
    pull_stock_parser.add_argument(
        "--force",
        action="store_true",
        help="Force pull even if cache state indicates prior completion.",
    )
    pull_stock_parser.add_argument(
        "--root",
        action="store_true",
        help="Use root mode and pull paths from profile 'root_source_paths'.",
    )

    migrate_parser = subparsers.add_parser(
        "migrate-state",
        help="Migrate .rhc-state files to the current schema version.",
    )
    migrate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview migrations without writing changes.",
    )

    subparsers.add_parser(
        "state-doctor",
        help="Validate .rhc-state files and report schema issues.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parsed_argv = list(argv) if argv is not None else sys.argv[1:]
    if parsed_argv and parsed_argv[0] == "pull-vanilla":
        parsed_argv[0] = "pull-backup"
    args = parser.parse_args(parsed_argv)

    if args.command == "hello":
        return cmd_hello(serial=args.serial)
    if args.command in {"pull-backup", "pull-stock"}:
        return cmd_pull_backup(
            profile=args.profile,
            serial=args.serial,
            force=args.force,
            use_root=args.root,
        )
    if args.command == "migrate-state":
        return cmd_migrate_state(dry_run=args.dry_run)
    if args.command == "state-doctor":
        return cmd_state_doctor()

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
