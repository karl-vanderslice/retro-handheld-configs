from __future__ import annotations

import argparse
import builtins
import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rhc.state import (
    iter_state_files,
    migrate_state_file,
    read_device_state,
    validate_state_file,
    write_device_state,
)

ROM_FILE_EXTENSIONS = {
    ".3ds",
    ".7z",
    ".a26",
    ".bin",
    ".chd",
    ".cue",
    ".fds",
    ".gb",
    ".gba",
    ".gbc",
    ".gen",
    ".gg",
    ".iso",
    ".md",
    ".n64",
    ".nds",
    ".nes",
    ".pbp",
    ".pce",
    ".pcecd",
    ".sfc",
    ".smc",
    ".smd",
    ".v64",
    ".xci",
    ".zip",
    ".z64",
}


APP_PACKAGE_CANDIDATES = {
    "Browser": [
        "com.android.browser",
        "com.android.chrome",
        "org.chromium.chrome",
        "org.lineageos.jelly",
    ],
    "Calendar": ["com.android.calendar", "com.google.android.calendar", "org.lineageos.etar"],
    "Camera": [
        "com.android.camera",
        "com.android.camera2",
        "com.mediatek.camera",
        "org.lineageos.aperture",
    ],
    "Clock": ["com.android.deskclock", "com.google.android.deskclock"],
    "Files app": [
        "com.android.documentsui",
        "com.google.android.documentsui",
        "com.android.fileexplorer",
        "com.android.filemanager",
    ],
    "Gallery": ["com.android.gallery", "com.android.gallery3d", "com.google.android.apps.photos"],
    "MIX Explorer": ["com.mixplorer", "com.mixplorer.silver"],
    "Music": [
        "com.android.music",
        "com.google.android.apps.youtube.music",
        "org.lineageos.eleven",
    ],
    "Sim Toolkit": ["com.android.stk"],
}

APP_REMOVE_KEEP_DATA_CANDIDATES = {
    "M64Plus FZ": ["org.mupen64plusae.v3.fzurita"],
    "PPSSPP": ["org.ppsspp.ppsspp", "org.ppsspp.ppssppgold"],
}

MANAGED_AUDIO_DIR = Path("managed") / "media" / "audio"
DEFAULT_APK_CACHE_DIR = Path.home() / ".cache" / "rhc" / "apks"
DEFAULT_AUDIO_IMPORT_SOURCE = (
    "/Volumes/media-emulation/Devices/Retroid Pocket Classic/6 Button/sdcard/media/audio"
)

OBTAINIUM_RELEASES_API_URL = "https://api.github.com/repos/ImranR98/Obtainium/releases/latest"
OBTAINIUM_EMULATION_PACK_RELEASES_API_URL = (
    "https://api.github.com/repos/RJNY/Obtainium-Emulation-Pack/releases/latest"
)

APK_LOCAL_FILENAMES = {
    "Obtainium": "Obtainium-latest.apk",
}

OBTAINIUM_EMULATION_PACK_LOCAL_FILENAME = "obtainium-emulation-pack-single-device-latest.json"
DEFAULT_DOWNLOADS_DIR = Path.home() / "Downloads"
DEVICE_DOWNLOADS_DIR = "/sdcard/Download"
OBTAINIUM_APPS_POPULATED_HINTS = [
    "RetroArch",
    "DraStic",
    "Daijish",
    "Flycast",
    "Aurora Store",
]

APK_PERMISSION_PACKAGE_CANDIDATES = {
    "Obtainium": ["dev.imranr.obtainium", "dev.imranr.obtainium.fdroid"],
    "Aurora Store": ["com.aurora.store"],
}

SYSTEM_SOUND_MAP = {
    "alarm_alert": "alarms/go_straight.mp3",
    "notification_sound": "notifications/sonic_ring.mp3",
    "ringtone": "ringtones/star_light_zone.mp3",
}

CHARGING_SOUND_RELATIVE_PATH = "notifications/lightning_shield.mp3"
DEFAULT_PROFILE = "retroid-pocket-classic-6-button-gammaos-next"

OUTPUT_TEXT = "text"
OUTPUT_JSON = "json"
OUTPUT_MODES = {OUTPUT_TEXT, OUTPUT_JSON}

CUSTOMIZE_TARGETS_ORDER = [
    "format-sd",
    "apks",
    "obtainium-import",
    "rom-cleanup",
    "audio-sync",
    "system-sounds",
    "auto-rotate",
    "timezone",
    "lockscreen",
    "remove-apps-keep-data",
    "remove-apps",
]
CUSTOMIZE_TARGETS = set(CUSTOMIZE_TARGETS_ORDER)
CUSTOMIZE_TARGET_ALIASES = {
    "format_sd": "format-sd",
    "apk": "apks",
    "apk-config": "apks",
    "obtainium": "obtainium-import",
    "obtainium-pack": "obtainium-import",
    "roms": "rom-cleanup",
    "audio": "audio-sync",
    "sounds": "system-sounds",
    "rotate": "auto-rotate",
    "remove-apps-keepdata": "remove-apps-keep-data",
}

ANSI_RESET = "\033[0m"
ANSI_COLORS = {
    "error": "\033[31m",
    "warning": "\033[33m",
    "success": "\033[32m",
    "info": "\033[36m",
    "step": "\033[34m",
}
LEVEL_LABELS = {
    "error": "[ERR]",
    "warning": "[WARN]",
    "success": "[OK]",
    "info": "[INFO]",
    "step": "[STEP]",
}

_OUTPUT_MODE = OUTPUT_TEXT
_NO_COLOR = False
_LOG_FILE_PATH: Path | None = None


def _default_output_mode() -> str:
    env_mode = os.environ.get("RHC_OUTPUT", OUTPUT_TEXT).strip().lower()
    if env_mode in OUTPUT_MODES:
        return env_mode
    return OUTPUT_TEXT


def configure_output(mode: str, log_file: str | None, no_color: bool) -> None:
    global _OUTPUT_MODE, _NO_COLOR, _LOG_FILE_PATH
    _OUTPUT_MODE = mode if mode in OUTPUT_MODES else OUTPUT_TEXT
    _NO_COLOR = no_color

    if log_file:
        _LOG_FILE_PATH = Path(log_file).expanduser()
        _LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    else:
        _LOG_FILE_PATH = None


def _log_json_event(event: dict[str, Any]) -> None:
    if _LOG_FILE_PATH is None:
        return
    with _LOG_FILE_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(event, sort_keys=True) + "\n")


def _stream_supports_color(stream: object) -> bool:
    if _NO_COLOR:
        return False

    if os.environ.get("NO_COLOR") is not None:
        return False

    term = os.environ.get("TERM", "")
    if term.lower() == "dumb":
        return False

    isatty = getattr(stream, "isatty", None)
    if callable(isatty):
        return bool(isatty())
    return False


def _paint(level: str, text: str, stream: object) -> str:
    if not _stream_supports_color(stream):
        return text
    color = ANSI_COLORS.get(level)
    if not color:
        return text
    return f"{color}{text}{ANSI_RESET}"


def _classify_message(message: str, stream: object) -> tuple[str, str]:
    stripped = message.strip()
    lowered = stripped.lower()

    if lowered.startswith("error:"):
        return "error", stripped.split(":", 1)[1].strip()
    if lowered.startswith("warning:"):
        return "warning", stripped.split(":", 1)[1].strip()
    if lowered.startswith("ok:"):
        return "success", stripped.split(":", 1)[1].strip()
    if lowered.startswith("done:"):
        return "success", stripped.split(":", 1)[1].strip()
    if lowered.startswith("step:"):
        return "step", stripped.split(":", 1)[1].strip()
    if lowered.startswith("invalid:"):
        return "error", stripped
    if lowered.startswith("migrated:") or lowered.startswith("would migrate:"):
        return "success", stripped
    if lowered.startswith("unchanged:"):
        return "info", stripped
    if lowered.startswith("pulling ") or lowered.startswith("formatting "):
        return "step", stripped
    if lowered.startswith("skipping "):
        return "warning", stripped
    if lowered.startswith("downloaded "):
        return "success", stripped

    if stream is sys.stderr:
        return "error", stripped
    return "info", stripped


def print(
    *values: object,
    sep: str = " ",
    end: str = "\n",
    file: object | None = None,
    flush: bool = False,
) -> None:
    stream = file if file is not None else sys.stdout
    raw = sep.join(str(value) for value in values)

    if not raw.strip():
        builtins.print(raw, end=end, file=stream, flush=flush)
        return

    level, message = _classify_message(raw, stream)
    event = {
        "ts": datetime.now(tz=UTC).isoformat(),
        "level": level,
        "message": message,
        "stream": "stderr" if stream is sys.stderr else "stdout",
    }

    _log_json_event(event)

    if _OUTPUT_MODE == OUTPUT_JSON:
        builtins.print(json.dumps(event, sort_keys=True), end=end, file=stream, flush=flush)
        return

    label = LEVEL_LABELS.get(level, LEVEL_LABELS["info"])
    prefix = _paint(level, label, stream)
    builtins.print(f"{prefix} {message}", end=end, file=stream, flush=flush)


def _normalize_customize_targets(targets: list[str] | None) -> list[str]:
    if not targets:
        return list(CUSTOMIZE_TARGETS_ORDER)

    selected: set[str] = set()
    for target in targets:
        normalized = CUSTOMIZE_TARGET_ALIASES.get(target, target)
        if normalized == "all":
            return list(CUSTOMIZE_TARGETS_ORDER)
        if normalized not in CUSTOMIZE_TARGETS:
            raise RuntimeError(f"unknown customization target: {target}")
        selected.add(normalized)

    return [target for target in CUSTOMIZE_TARGETS_ORDER if target in selected]


def _state_dir() -> Path:
    return Path(os.environ.get("RHC_STATE_DIR", ".rhc-state"))


def _managed_audio_dir(profile: str) -> Path:
    return Path("managed") / profile / "media" / "audio"


def _print_phase_one_completion_banner() -> None:
    print("")
    print("🎉 ╔══════════════════════════════════════════════════════════════════════╗")
    print("🎉 ║                      PHASE 1 COMPLETE                              ║")
    print("🎉 ╚══════════════════════════════════════════════════════════════════════╝")
    print("")
    print("➡️  Import the Obtainium JSON in Downloads (or wherever we put it).")
    print("➡️  We’ll expand these instructions a bit further shortly.")


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


def _adb_shell(
    adb: str,
    serial: str,
    shell_command: str,
    *,
    check: bool,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [adb, "-s", serial, "shell", shell_command],
        capture_output=True,
        text=True,
        check=check,
        timeout=timeout,
    )


def _download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "retro-handheld-configs/0.1 (+https://github.com/karl-vanderslice)",
            "Accept": "application/octet-stream,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read()
    destination.write_bytes(data)


def _resolve_obtainium_download_url() -> str:
    request = urllib.request.Request(
        OBTAINIUM_RELEASES_API_URL,
        headers={
            "User-Agent": "retro-handheld-configs/0.1 (+https://github.com/karl-vanderslice)",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    assets = payload.get("assets")
    if not isinstance(assets, list) or not assets:
        raise RuntimeError("unable to find Obtainium release assets")

    preferred_url: str | None = None
    fallback_url: str | None = None

    for asset in assets:
        if not isinstance(asset, dict):
            continue

        name = asset.get("name")
        browser_download_url = asset.get("browser_download_url")
        if not isinstance(name, str) or not isinstance(browser_download_url, str):
            continue
        if not name.lower().endswith(".apk"):
            continue

        if fallback_url is None:
            fallback_url = browser_download_url

        lowered = name.lower()
        if "arm64" in lowered or "universal" in lowered:
            preferred_url = browser_download_url
            break

    if preferred_url:
        return preferred_url
    if fallback_url:
        return fallback_url
    raise RuntimeError("unable to find an APK asset for Obtainium latest release")


def _resolve_obtainium_emulation_pack_download() -> tuple[str, str]:
    request = urllib.request.Request(
        OBTAINIUM_EMULATION_PACK_RELEASES_API_URL,
        headers={
            "User-Agent": "retro-handheld-configs/0.1 (+https://github.com/karl-vanderslice)",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    assets = payload.get("assets")
    if not isinstance(assets, list) or not assets:
        raise RuntimeError("unable to find Obtainium Emulation Pack release assets")

    preferred_download_url: str | None = None
    preferred_name: str | None = None
    fallback_download_url: str | None = None
    fallback_name: str | None = None

    for asset in assets:
        if not isinstance(asset, dict):
            continue

        name = asset.get("name")
        browser_download_url = asset.get("browser_download_url")
        if not isinstance(name, str) or not isinstance(browser_download_url, str):
            continue

        lowered = name.lower()
        if not lowered.endswith(".json"):
            continue

        if "obtainium-emulation-pack" not in lowered:
            continue

        if fallback_download_url is None:
            fallback_download_url = browser_download_url
            fallback_name = name

        if "dual-screen" in lowered:
            continue

        preferred_download_url = browser_download_url
        preferred_name = name
        break

    if preferred_download_url and preferred_name:
        return preferred_download_url, preferred_name
    if fallback_download_url and fallback_name:
        return fallback_download_url, fallback_name
    raise RuntimeError("unable to find a JSON asset for Obtainium Emulation Pack")


def _download_latest_apks(force: bool, destination_dir: Path | None = None) -> dict[str, Path]:
    destination_root = destination_dir if destination_dir is not None else DEFAULT_APK_CACHE_DIR
    destinations = {
        "Obtainium": destination_root / APK_LOCAL_FILENAMES["Obtainium"],
    }

    if force or not destinations["Obtainium"].exists():
        obtainium_url = _resolve_obtainium_download_url()
        _download_file(obtainium_url, destinations["Obtainium"])
        print(f"Downloaded Obtainium -> {destinations['Obtainium']}")

    return destinations


def _download_obtainium_emulation_pack(force: bool, destination_dir: Path) -> Path:
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / OBTAINIUM_EMULATION_PACK_LOCAL_FILENAME

    if force or not destination.exists():
        pack_url, asset_name = _resolve_obtainium_emulation_pack_download()
        _download_file(pack_url, destination)
        print(f"Downloaded Obtainium Emulation Pack ({asset_name}) -> {destination}")

    return destination


def _copy_directory_tree(source_root: Path, destination_root: Path, overwrite: bool) -> int:
    if not source_root.exists() or not source_root.is_dir():
        raise RuntimeError(f"source audio path not found: {source_root}")

    copied_files = 0
    for source_file in source_root.rglob("*"):
        if not source_file.is_file():
            continue
        relative_path = source_file.relative_to(source_root)
        destination_file = destination_root / relative_path
        destination_file.parent.mkdir(parents=True, exist_ok=True)

        if destination_file.exists() and not overwrite:
            continue

        shutil.copy2(source_file, destination_file)
        copied_files += 1

    return copied_files


def cmd_import_audio_assets(profile: str, source: str, overwrite: bool) -> int:
    try:
        _load_profile(profile)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    source_root = Path(source)
    destination_root = _managed_audio_dir(profile)
    try:
        copied_files = _copy_directory_tree(source_root, destination_root, overwrite=overwrite)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(
        f"Audio import complete: copied {copied_files} files from {source_root} "
        f"to {destination_root}."
    )
    return 0


def cmd_download_apks(force: bool, destination: str) -> int:
    try:
        destination_dir = Path(destination)
        _download_latest_apks(force=force, destination_dir=destination_dir)
        _download_obtainium_emulation_pack(
            force=force,
            destination_dir=DEFAULT_DOWNLOADS_DIR,
        )
    except (RuntimeError, urllib.error.URLError, ValueError) as exc:
        print(f"error: failed to download latest APKs: {exc}", file=sys.stderr)
        return 1

    print(f"APK download complete in {destination_dir}.")
    print(f"Obtainium emulation pack JSON saved to {DEFAULT_DOWNLOADS_DIR}.")
    return 0


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


def _confirm_format_sd(auto_confirm: bool) -> None:
    if auto_confirm:
        return

    if not sys.stdin.isatty():
        raise RuntimeError(
            "SD formatting requires interactive confirmation. Re-run with --yes-format-sd "
            "for non-interactive runs."
        )

    prompt = "Format removable SD card as public storage (erases SD data). Continue? [y/N]: "
    response = input(prompt).strip().lower()
    if response not in {"y", "yes"}:
        raise RuntimeError("aborted by user")


def _list_sd_disks(adb: str, serial: str) -> list[str]:
    candidates: list[str] = []
    for command in ("sm list-disks adoptable", "sm list-disks"):
        result = _adb_shell(adb, serial, command, check=False, timeout=15)
        for token in result.stdout.split():
            cleaned = token.strip().rstrip(",")
            if cleaned.startswith("disk:") and cleaned not in candidates:
                candidates.append(cleaned)
    return candidates


def _format_sd_as_public(adb: str, serial: str) -> None:
    disks = _list_sd_disks(adb, serial)
    if not disks:
        raise RuntimeError("no removable/adoptable SD disks reported by `sm list-disks`")

    _adb_shell(adb, serial, "sm set-force-adoptable false", check=False, timeout=15)

    for disk in disks:
        print(f"Formatting {disk} as public storage...")
        _adb_shell(
            adb,
            serial,
            f"sm partition {shlex.quote(disk)} public",
            check=True,
            timeout=180,
        )


def _list_rom_files(adb: str, serial: str) -> list[str]:
    result = _adb_shell(
        adb,
        serial,
        "find /storage/emulated/0/ROMs -type f 2>/dev/null",
        check=False,
        timeout=30,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _is_removable_rom_file(path: str) -> bool:
    name = Path(path).name.lower()
    if name == "systeminfo.txt":
        return False
    return Path(name).suffix.lower() in ROM_FILE_EXTENSIONS


def _remove_preloaded_roms(adb: str, serial: str) -> tuple[int, int]:
    files = _list_rom_files(adb, serial)
    if not files:
        return 0, 0

    removable = [entry for entry in files if _is_removable_rom_file(entry)]
    for file_path in removable:
        _adb_shell(adb, serial, f"rm -f {shlex.quote(file_path)}", check=True, timeout=20)
    return len(files), len(removable)


def _set_timezone_new_york(adb: str, serial: str) -> None:
    target_zone = "America/New_York"
    _adb_shell(adb, serial, "settings put global auto_time_zone 0", check=False, timeout=15)
    _adb_shell(adb, serial, f"settings put global time_zone {target_zone}", check=False, timeout=15)
    _adb_shell(adb, serial, f"settings put system time_zone {target_zone}", check=False, timeout=15)
    _adb_shell(adb, serial, f"setprop persist.sys.timezone {target_zone}", check=False, timeout=15)
    _adb_shell(adb, serial, f"setprop sys.timezone {target_zone}", check=False, timeout=15)
    _adb_shell(adb, serial, f"cmd alarm set-timezone {target_zone}", check=False, timeout=20)
    _adb_shell(adb, serial, f"service call alarm 3 s16 {target_zone}", check=False, timeout=20)
    _adb_shell(
        adb,
        serial,
        f"am broadcast -a android.intent.action.TIMEZONE_CHANGED --es time-zone {target_zone}",
        check=False,
        timeout=20,
    )

    checks = [
        "settings get global time_zone",
        "settings get system time_zone",
        "getprop persist.sys.timezone",
        "getprop sys.timezone",
    ]
    for check_command in checks:
        result = _adb_shell(adb, serial, check_command, check=False, timeout=15)
        value = result.stdout.strip()
        if value == target_zone:
            return

    raise RuntimeError(f"failed to apply timezone {target_zone}")


def _disable_lock_screen(adb: str, serial: str) -> None:
    attempts = [
        "locksettings set-disabled true",
        "cmd lock_settings set-disabled true",
    ]
    for command in attempts:
        result = _adb_shell(adb, serial, command, check=False, timeout=20)
        if result.returncode == 0:
            return
    raise RuntimeError("failed to disable lock screen via locksettings/cmd lock_settings")


def _list_installed_packages(adb: str, serial: str) -> set[str]:
    result = _adb_shell(adb, serial, "pm list packages", check=True, timeout=30)
    installed: set[str] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("package:"):
            installed.add(line.split(":", 1)[1])
    return installed


def _disable_or_uninstall_apps(adb: str, serial: str) -> list[str]:
    installed = _list_installed_packages(adb, serial)
    report: list[str] = []

    for app_name, package_candidates in APP_PACKAGE_CANDIDATES.items():
        target = next((pkg for pkg in package_candidates if pkg in installed), None)
        if target is None:
            report.append(f"{app_name}: not installed")
            continue

        uninstall = _adb_shell(
            adb,
            serial,
            f"pm uninstall --user 0 {shlex.quote(target)}",
            check=False,
            timeout=30,
        )
        if uninstall.returncode == 0 and "Success" in uninstall.stdout:
            report.append(f"{app_name}: uninstalled ({target})")
            continue

        disable = _adb_shell(
            adb,
            serial,
            f"pm disable-user --user 0 {shlex.quote(target)}",
            check=False,
            timeout=30,
        )
        if disable.returncode == 0:
            report.append(f"{app_name}: disabled ({target})")
            continue

        report.append(f"{app_name}: failed ({target})")

    return report


def _remove_apps_keep_data(adb: str, serial: str) -> list[str]:
    installed = _list_installed_packages(adb, serial)
    report: list[str] = []

    for app_name, package_candidates in APP_REMOVE_KEEP_DATA_CANDIDATES.items():
        target = next((pkg for pkg in package_candidates if pkg in installed), None)
        if target is None:
            report.append(f"{app_name}: not installed")
            continue

        uninstall = _adb_shell(
            adb,
            serial,
            f"pm uninstall -k --user 0 {shlex.quote(target)}",
            check=False,
            timeout=30,
        )
        if uninstall.returncode == 0 and "Success" in uninstall.stdout:
            report.append(f"{app_name}: removed for user 0 (data kept) ({target})")
            continue

        report.append(f"{app_name}: failed keep-data removal ({target})")

    return report


def _install_apk(adb: str, serial: str, apk_path: Path, label: str) -> None:
    if not apk_path.exists():
        raise RuntimeError(f"missing APK for {label}: {apk_path}")

    result = subprocess.run(
        [adb, "-s", serial, "install", "-r", str(apk_path)],
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    output = (result.stdout + "\n" + result.stderr).strip()
    if result.returncode != 0 and "Success" not in output:
        raise RuntimeError(f"failed to install {label} from {apk_path}: {output}")


def _push_to_device_downloads(adb: str, serial: str, local_path: Path) -> str:
    if not local_path.exists():
        raise RuntimeError(f"local file not found: {local_path}")

    remote_path = f"{DEVICE_DOWNLOADS_DIR}/{local_path.name}"
    _adb_shell(
        adb, serial, f"mkdir -p {shlex.quote(DEVICE_DOWNLOADS_DIR)}", check=False, timeout=20
    )
    subprocess.run(
        [adb, "-s", serial, "push", str(local_path), remote_path],
        check=True,
        timeout=120,
    )
    return remote_path


def _automate_obtainium_import(
    adb: str,
    device_serial: str,
    local_json_path: Path,
    *,
    cleanup_rpc: bool,
) -> None:
    try:
        import uiautomator2 as u2
    except Exception as exc:  # pragma: no cover - depends on dev shell
        raise RuntimeError(
            "uiautomator2 is required for Obtainium automation. "
            "Use the Nix dev shell with uiautomator2 available."
        ) from exc

    installed = _list_installed_packages(adb, device_serial)
    pkg_name = next(
        (pkg for pkg in APK_PERMISSION_PACKAGE_CANDIDATES["Obtainium"] if pkg in installed),
        None,
    )
    if pkg_name is None:
        raise RuntimeError("Obtainium package is not installed on device")

    _adb_shell(
        adb,
        device_serial,
        "cmd package install-existing --user 0 com.android.documentsui",
        check=False,
        timeout=20,
    )
    _adb_shell(
        adb,
        device_serial,
        f"pm grant {shlex.quote(pkg_name)} android.permission.POST_NOTIFICATIONS",
        check=False,
        timeout=20,
    )
    _adb_shell(
        adb,
        device_serial,
        f"appops set {shlex.quote(pkg_name)} POST_NOTIFICATION allow",
        check=False,
        timeout=20,
    )
    _adb_shell(
        adb,
        device_serial,
        f"pm grant {shlex.quote(pkg_name)} android.permission.REQUEST_INSTALL_PACKAGES",
        check=False,
        timeout=20,
    )
    _adb_shell(
        adb,
        device_serial,
        f"appops set {shlex.quote(pkg_name)} REQUEST_INSTALL_PACKAGES allow",
        check=False,
        timeout=20,
    )

    d = u2.connect(device_serial)
    try:
        d.healthcheck()
        d.service("uiautomator").start()
    except Exception:
        pass
    file_name = OBTAINIUM_EMULATION_PACK_LOCAL_FILENAME
    device_path = f"{DEVICE_DOWNLOADS_DIR}/{file_name}"

    d.push(str(local_json_path), device_path)
    _adb_shell(
        adb,
        device_serial,
        "am force-stop com.android.documentsui",
        check=False,
        timeout=20,
    )
    _adb_shell(adb, device_serial, "input keyevent KEYCODE_HOME", check=False, timeout=10)
    d.app_stop(pkg_name)
    launch_component_result = _adb_shell(
        adb,
        device_serial,
        f"cmd package resolve-activity --brief {shlex.quote(pkg_name)}",
        check=False,
        timeout=20,
    )
    launch_component = ""
    for line in launch_component_result.stdout.splitlines():
        if "/" in line and not line.startswith("priority="):
            launch_component = line.strip()
            break

    if launch_component:
        _adb_shell(
            adb,
            device_serial,
            f"am start -S -W -n {shlex.quote(launch_component)}",
            check=False,
            timeout=20,
        )
    else:
        d.app_start(pkg_name, stop=True)

    def _first_visible(candidates: list[object], timeout: float) -> object | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for candidate in candidates:
                try:
                    if candidate.exists:
                        return candidate
                except Exception:
                    try:
                        d.healthcheck()
                    except Exception:
                        pass
                    continue
            time.sleep(0.4)
        return None

    def _tap_if_visible(candidates: list[object], timeout: float = 2.0) -> bool:
        selector = _first_visible(candidates, timeout)
        if selector is None:
            return False
        selector.click()
        return True

    def _dismiss_first_run_popups() -> None:
        for _ in range(5):
            clicked = _tap_if_visible(
                [
                    d(resourceId="com.android.permissioncontroller:id/permission_allow_button"),
                    d(textMatches=r"(?i)^allow$"),
                    d(textMatches=r"(?i)^continue$"),
                    d(textMatches=r"(?i)^next$"),
                    d(textMatches=r"(?i)^ok$"),
                    d(textMatches=r"(?i)^got it$"),
                    d(textMatches=r"(?i)^close$"),
                    d(descriptionMatches=r"(?i)^allow$"),
                    d(descriptionMatches=r"(?i)^continue$"),
                    d(descriptionMatches=r"(?i)^okay$"),
                    d(descriptionMatches=r"(?i)^dismiss$"),
                    d(descriptionContains="Keep Android Open"),
                ],
                timeout=1.5,
            )
            if not clicked:
                break
            time.sleep(0.8)

    def _wait_for_obtainium_foreground(timeout: float = 20.0) -> bool:
        activity_focus_cmd = (
            "dumpsys activity activities | grep -E 'topResumedActivity|mFocusedApp' | head -n 2"
        )
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            focus = _adb_shell(
                adb,
                device_serial,
                activity_focus_cmd,
                check=False,
                timeout=10,
            )
            combined = (focus.stdout + "\n" + focus.stderr).lower()
            if pkg_name.lower() in combined and "mainactivity" in combined:
                return True
            time.sleep(0.5)
        return False

    def _documentsui_foreground() -> bool:
        activity_focus_cmd = (
            "dumpsys activity activities | grep -E 'topResumedActivity|mFocusedApp' | head -n 2"
        )
        focus = _adb_shell(
            adb,
            device_serial,
            activity_focus_cmd,
            check=False,
            timeout=10,
        )
        combined = (focus.stdout + "\n" + focus.stderr).lower()
        return "com.android.documentsui" in combined

    def _recover_documentsui_json_pick() -> bool:
        if not _documentsui_foreground():
            return True

        _tap_if_visible([d(descriptionContains="Clear query")], timeout=1.0)
        _tap_if_visible(
            [
                d(textMatches=r"(?i)^files$"),
                d(descriptionMatches=r"(?i)^files$"),
            ],
            timeout=3.0,
        )
        time.sleep(0.8)

        _tap_if_visible(
            [
                d(resourceId="com.android.documentsui:id/option_menu_search"),
                d(descriptionContains="Search"),
            ],
            timeout=3.0,
        )

        xml_text = d.dump_hierarchy()
        tapped_exact_row = False
        try:
            root = ET.fromstring(xml_text)
            for node in root.findall(".//node"):
                if node.attrib.get("resource-id") != "android:id/title":
                    continue
                if (node.attrib.get("text") or "").strip() != file_name:
                    continue
                bounds = (node.attrib.get("bounds") or "").strip()
                if not bounds.startswith("["):
                    continue
                points = bounds.replace("][", ",").replace("[", "").replace("]", "").split(",")
                if len(points) != 4:
                    continue
                x1, y1, x2, y2 = [int(p) for p in points]
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                _adb_shell(
                    adb,
                    device_serial,
                    f"input tap {center_x} {center_y}",
                    check=False,
                    timeout=10,
                )
                tapped_exact_row = True
                break
        except Exception:
            tapped_exact_row = False

        if not tapped_exact_row:
            _tap_if_visible(
                [
                    d(resourceId="com.android.documentsui:id/item_root"),
                    d(resourceId="android:id/title", text=file_name),
                    d(resourceId="android:id/title", textContains="obtainium-emulation-pack"),
                ],
                timeout=6.0,
            )

        _tap_if_visible([d(resourceId="com.android.documentsui:id/item_root")], timeout=2.0)
        _adb_shell(adb, device_serial, "input keyevent KEYCODE_ENTER", check=False, timeout=10)
        _adb_shell(
            adb,
            device_serial,
            "input keyevent KEYCODE_DPAD_CENTER",
            check=False,
            timeout=10,
        )
        time.sleep(1.0)
        return _wait_for_obtainium_foreground(timeout=12.0)

    if not _wait_for_obtainium_foreground(timeout=12.0):
        if launch_component:
            _adb_shell(
                adb,
                device_serial,
                f"am start -S -W -n {shlex.quote(launch_component)}",
                check=False,
                timeout=25,
            )
        else:
            _adb_shell(
                adb,
                device_serial,
                f"monkey -p {shlex.quote(pkg_name)} -c android.intent.category.LAUNCHER 1",
                check=False,
                timeout=20,
            )

        _adb_shell(adb, device_serial, "input keyevent KEYCODE_BACK", check=False, timeout=10)
        if not _wait_for_obtainium_foreground(timeout=10.0):
            raise RuntimeError("Obtainium did not reach foreground before import automation")

    _dismiss_first_run_popups()

    no_apps_initial = _first_visible(
        [
            d(textMatches=r"(?i)^no apps$"),
            d(descriptionMatches=r"(?i)^no apps$"),
        ],
        timeout=2.0,
    )
    if no_apps_initial is None and not _documentsui_foreground():
        already_populated = _first_visible(
            [d(textContains=hint) for hint in OBTAINIUM_APPS_POPULATED_HINTS]
            + [d(descriptionContains=hint) for hint in OBTAINIUM_APPS_POPULATED_HINTS],
            timeout=2.0,
        )
        if already_populated is not None:
            if cleanup_rpc:
                try:
                    d.service("uiautomator").stop()
                except Exception:
                    pass
            return

    import_export_selector = _first_visible(
        [
            d(textContains="Import/export"),
            d(textContains="Import/Export"),
            d(textContains="import/export"),
            d(descriptionContains="Import/export"),
            d(descriptionContains="Import/Export"),
            d(descriptionContains="import/export"),
            d(descriptionContains="Tab 3 of 4"),
        ],
        timeout=20.0,
    )
    if import_export_selector is None:
        _adb_shell(adb, device_serial, "input tap 775 940", check=False, timeout=10)
        time.sleep(1.0)
        import_export_selector = _first_visible(
            [
                d(textContains="Import/export"),
                d(textContains="Import/Export"),
                d(textContains="import/export"),
                d(descriptionContains="Import/export"),
                d(descriptionContains="Import/Export"),
                d(descriptionContains="import/export"),
                d(descriptionContains="Tab 3 of 4"),
            ],
            timeout=6.0,
        )
    if import_export_selector is None:
        raise RuntimeError("failed to find Obtainium 'Import/export' screen")
    import_export_selector.click()

    obtainium_import_selector = _first_visible(
        [
            d(textContains="Obtainium import"),
            d(textContains="Obtainium Import"),
            d(textContains="obtainium import"),
            d(descriptionContains="Obtainium import"),
            d(descriptionContains="Obtainium Import"),
            d(descriptionContains="obtainium import"),
        ],
        timeout=6.0,
    )

    if obtainium_import_selector is not None:
        obtainium_import_selector.click()
    else:
        raise RuntimeError("failed to find Obtainium 'Obtainium import' action")

    downloads_selector = _first_visible(
        [
            d(textContains="Download"),
            d(textContains="Downloads"),
            d(descriptionContains="Download"),
            d(descriptionContains="Downloads"),
        ],
        timeout=4.0,
    )
    if downloads_selector is not None:
        downloads_selector.click()
        time.sleep(0.8)
    else:
        roots_selector = _first_visible(
            [
                d(descriptionContains="Show roots"),
                d(descriptionContains="roots"),
            ],
            timeout=2.0,
        )
        if roots_selector is not None:
            roots_selector.click()
            time.sleep(0.6)
            downloads_root = _first_visible(
                [
                    d(textMatches=r"(?i)^downloads$"),
                    d(textContains="Downloads"),
                    d(descriptionContains="Downloads"),
                ],
                timeout=4.0,
            )
            if downloads_root is not None:
                downloads_root.click()
                time.sleep(0.8)

    file_selected = False
    for _ in range(10):
        result_selector = _first_visible(
            [
                d(resourceId="android:id/title", text=file_name),
                d(resourceId="android:id/title", textContains="obtainium-emulation-pack"),
            ],
            timeout=1.5,
        )
        if result_selector is not None:
            result_selector.click()
            file_selected = True
            break
        try:
            xml_text = d.dump_hierarchy()
            root = ET.fromstring(xml_text)
            for node in root.findall(".//node"):
                if node.attrib.get("resource-id") != "android:id/title":
                    continue
                title_text = (node.attrib.get("text") or "").strip()
                if title_text != file_name and "obtainium-emulation-pack" not in title_text:
                    continue
                bounds = (node.attrib.get("bounds") or "").strip()
                if not bounds.startswith("["):
                    continue
                points = bounds.replace("][", ",").replace("[", "").replace("]", "").split(",")
                if len(points) != 4:
                    continue
                x1, y1, x2, y2 = [int(p) for p in points]
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                _adb_shell(
                    adb,
                    device_serial,
                    f"input tap {center_x} {center_y}",
                    check=False,
                    timeout=10,
                )
                file_selected = True
                break
            if file_selected:
                break
        except Exception:
            pass
        try:
            d(scrollable=True).scroll.vert.forward(steps=60)
        except Exception:
            _adb_shell(
                adb,
                device_serial,
                "input swipe 520 1500 520 520 180",
                check=False,
                timeout=10,
            )
        time.sleep(0.5)

    if not file_selected:
        raise RuntimeError(f"failed to find imported JSON in picker: {file_name}")

    _tap_if_visible(
        [
            d(resourceId="com.android.documentsui:id/action_menu_select"),
            d(textMatches=r"(?i)^open$"),
            d(textMatches=r"(?i)^select$"),
            d(textMatches=r"(?i)^choose$"),
            d(descriptionMatches=r"(?i)^open$"),
            d(descriptionMatches=r"(?i)^select$"),
            d(descriptionMatches=r"(?i)^choose$"),
        ],
        timeout=3.0,
    )

    if _documentsui_foreground():
        _adb_shell(adb, device_serial, "input keyevent KEYCODE_ENTER", check=False, timeout=10)
        _adb_shell(
            adb,
            device_serial,
            "input keyevent KEYCODE_DPAD_CENTER",
            check=False,
            timeout=10,
        )

    _tap_if_visible(
        [
            d(textMatches=r"(?i)^continue$"),
            d(textMatches=r"(?i)^next$"),
            d(textMatches=r"(?i)^open$"),
            d(textMatches=r"(?i)^ok$"),
            d(textMatches=r"(?i)^import$"),
            d(textMatches=r"(?i)^select$"),
            d(textMatches=r"(?i)^choose$"),
            d(textMatches=r"(?i)^done$"),
            d(descriptionMatches=r"(?i)^continue$"),
            d(descriptionMatches=r"(?i)^next$"),
            d(descriptionMatches=r"(?i)^open$"),
            d(descriptionMatches=r"(?i)^ok$"),
            d(descriptionMatches=r"(?i)^import$"),
        ],
        timeout=3.0,
    )

    if not _wait_for_obtainium_foreground(timeout=15.0):
        _adb_shell(adb, device_serial, "input keyevent KEYCODE_BACK", check=False, timeout=10)
        _tap_if_visible(
            [
                d(textMatches=r"(?i)^continue$"),
                d(textMatches=r"(?i)^next$"),
                d(textMatches=r"(?i)^open$"),
                d(textMatches=r"(?i)^ok$"),
                d(textMatches=r"(?i)^import$"),
                d(textMatches=r"(?i)^select$"),
                d(textMatches=r"(?i)^choose$"),
                d(textMatches=r"(?i)^done$"),
            ],
            timeout=2.0,
        )

    if not _wait_for_obtainium_foreground(timeout=20.0):
        if not _recover_documentsui_json_pick():
            raise RuntimeError("Obtainium did not return to foreground after JSON file selection")

    if _documentsui_foreground():
        _adb_shell(adb, device_serial, "input keyevent KEYCODE_BACK", check=False, timeout=10)
        time.sleep(1.0)
        if not _wait_for_obtainium_foreground(timeout=10.0):
            raise RuntimeError("DocumentsUI remained foreground after Obtainium import")

    apps_tab = _first_visible(
        [
            d(descriptionMatches=r"(?i)^apps.*tab 1 of 4$"),
            d(textMatches=r"(?i)^apps$"),
            d(descriptionContains="Apps"),
            d(descriptionContains="Tab 1 of 4"),
        ],
        timeout=25.0,
    )
    if apps_tab is not None:
        apps_tab.click()

    _wait_for_obtainium_foreground(timeout=5.0)

    no_apps_selector = _first_visible(
        [
            d(textMatches=r"(?i)^no apps$"),
            d(descriptionMatches=r"(?i)^no apps$"),
        ],
        timeout=3.0,
    )
    if no_apps_selector is not None:
        raise RuntimeError("Obtainium import did not populate apps list")

    if cleanup_rpc:
        try:
            d.service("uiautomator").stop()
        except Exception:
            pass


def _grant_apk_install_permissions(adb: str, serial: str) -> list[str]:
    installed = _list_installed_packages(adb, serial)
    report: list[str] = []

    for app_name, candidates in APK_PERMISSION_PACKAGE_CANDIDATES.items():
        package_name = next((pkg for pkg in candidates if pkg in installed), None)
        if package_name is None:
            report.append(f"{app_name}: package not installed")
            continue

        _adb_shell(
            adb,
            serial,
            f"pm grant {shlex.quote(package_name)} android.permission.REQUEST_INSTALL_PACKAGES",
            check=False,
            timeout=20,
        )
        appops_result = _adb_shell(
            adb,
            serial,
            f"appops set {shlex.quote(package_name)} REQUEST_INSTALL_PACKAGES allow",
            check=False,
            timeout=20,
        )
        if appops_result.returncode == 0:
            report.append(f"{app_name}: REQUEST_INSTALL_PACKAGES allowed ({package_name})")
        else:
            report.append(f"{app_name}: unable to set appops ({package_name})")

        if app_name == "Obtainium":
            post_notifications = _adb_shell(
                adb,
                serial,
                f"pm grant {shlex.quote(package_name)} android.permission.POST_NOTIFICATIONS",
                check=False,
                timeout=20,
            )
            appops_notification = _adb_shell(
                adb,
                serial,
                f"appops set {shlex.quote(package_name)} POST_NOTIFICATION allow",
                check=False,
                timeout=20,
            )

            if post_notifications.returncode == 0 or appops_notification.returncode == 0:
                report.append(f"Obtainium: notifications allowed ({package_name})")
            else:
                report.append(f"Obtainium: unable to grant notifications ({package_name})")

    return report


def _deploy_audio_assets_to_device(adb: str, serial: str, profile: str) -> None:
    managed_audio_dir = _managed_audio_dir(profile)
    if not managed_audio_dir.exists():
        raise RuntimeError(
            f"managed audio directory not found: {managed_audio_dir}; "
            f"run `rhc import-audio-assets --profile {profile}` first"
        )

    _adb_shell(adb, serial, "mkdir -p /storage/emulated/0/media/audio", check=False, timeout=20)
    subprocess.run(
        [
            adb,
            "-s",
            serial,
            "push",
            str(managed_audio_dir) + "/.",
            "/storage/emulated/0/media/audio/",
        ],
        check=True,
        timeout=180,
    )


def _media_store_uri_for_audio_filename(adb: str, serial: str, filename: str) -> str | None:
    listing = _adb_shell(
        adb,
        serial,
        "content query --uri content://media/external/audio/media --projection _id:_display_name",
        check=False,
        timeout=30,
    )
    if listing.returncode != 0:
        return None

    for line in listing.stdout.splitlines():
        if f"_display_name={filename}" not in line:
            continue
        if "_id=" not in line:
            continue
        media_id = line.split("_id=", 1)[1].split(",", 1)[0].strip()
        if media_id:
            return f"content://media/external/audio/media/{media_id}"

    return None


def _configure_system_sounds(adb: str, serial: str) -> None:
    base_path = "/storage/emulated/0/media/audio"
    base_uri = f"file://{base_path}"
    configured_targets: dict[str, str] = {}

    for setting_name, relative_path in SYSTEM_SOUND_MAP.items():
        file_uri = f"{base_uri}/{relative_path}"
        media_store_uri = _media_store_uri_for_audio_filename(adb, serial, Path(relative_path).name)
        full_path = media_store_uri or file_uri
        configured_targets[setting_name] = full_path
        _adb_shell(
            adb,
            serial,
            f"settings put system {setting_name} {shlex.quote(full_path)}",
            check=False,
            timeout=20,
        )

    charging_path = f"{base_uri}/{CHARGING_SOUND_RELATIVE_PATH}"
    _adb_shell(
        adb,
        serial,
        "settings put global charging_sounds_enabled 1",
        check=False,
        timeout=20,
    )
    _adb_shell(
        adb,
        serial,
        f"settings put global charging_started_sound {shlex.quote(charging_path)}",
        check=False,
        timeout=20,
    )
    _adb_shell(
        adb,
        serial,
        f"settings put global wireless_charging_started_sound {shlex.quote(charging_path)}",
        check=False,
        timeout=20,
    )
    configured_targets["charging_started_sound"] = charging_path

    verify = {
        "alarm_alert": _adb_shell(
            adb,
            serial,
            "settings get system alarm_alert",
            check=False,
            timeout=15,
        ),
        "notification_sound": _adb_shell(
            adb, serial, "settings get system notification_sound", check=False, timeout=15
        ),
        "ringtone": _adb_shell(
            adb,
            serial,
            "settings get system ringtone",
            check=False,
            timeout=15,
        ),
        "charging_started_sound": _adb_shell(
            adb,
            serial,
            "settings get global charging_started_sound",
            check=False,
            timeout=15,
        ),
    }

    expected_suffix = {
        "alarm_alert": SYSTEM_SOUND_MAP["alarm_alert"],
        "notification_sound": SYSTEM_SOUND_MAP["notification_sound"],
        "ringtone": SYSTEM_SOUND_MAP["ringtone"],
        "charging_started_sound": CHARGING_SOUND_RELATIVE_PATH,
    }

    for key, result in verify.items():
        configured = result.stdout.strip().strip("'").strip('"')
        if not configured or configured == "null":
            raise RuntimeError(f"failed to configure system sound setting: {key}")
        target = configured_targets.get(key, "")
        if configured == target:
            continue
        if target.startswith("content://") and configured.startswith(f"{target}?"):
            continue
        if configured.endswith(expected_suffix[key]):
            continue
        if configured.startswith("content://") and key in {
            "alarm_alert",
            "notification_sound",
            "ringtone",
        }:
            continue
        if key == "charging_started_sound" and configured.startswith("file://"):
            continue
        if not configured.endswith(expected_suffix[key]):
            raise RuntimeError(f"failed to configure system sound setting: {key}")


def _disable_auto_rotate(adb: str, serial: str) -> None:
    _adb_shell(adb, serial, "settings put system accelerometer_rotation 0", check=False, timeout=20)
    _adb_shell(adb, serial, "settings put system user_rotation 0", check=False, timeout=20)

    current = _adb_shell(
        adb,
        serial,
        "settings get system accelerometer_rotation",
        check=False,
        timeout=15,
    )
    if current.stdout.strip() != "0":
        raise RuntimeError("failed to disable auto-rotate")


def cmd_customize_device(
    profile: str,
    serial: str | None,
    force: bool,
    auto_confirm_format_sd: bool,
    skip_format_sd: bool,
    targets: list[str] | None,
    cleanup_rpc: bool,
) -> int:
    try:
        adb = _adb_path()
        devices = _connected_devices(adb)
        _load_profile(profile)
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
        selected_targets = _normalize_customize_targets(targets)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    previous = read_device_state(_state_dir(), selected)
    customize_marker = previous.get("customize_device", {})
    profile_marker: dict = {}
    if isinstance(customize_marker, dict):
        profile_specific = customize_marker.get(profile)
        if isinstance(profile_specific, dict):
            profile_marker = profile_specific
        elif "last_applied_at" in customize_marker:
            profile_marker = customize_marker

    target_marker = profile_marker.get("targets", {})
    target_state: dict[str, dict[str, str]] = {}
    if isinstance(target_marker, dict):
        for key, value in target_marker.items():
            if isinstance(key, str) and isinstance(value, dict):
                target_state[key] = value

    pending_targets = [
        target
        for target in selected_targets
        if force or not isinstance(target_state.get(target, {}).get("last_applied_at"), str)
    ]

    skipped_targets = [target for target in selected_targets if target not in pending_targets]
    if skipped_targets:
        print(
            "Skipping already-applied targets: "
            + ", ".join(skipped_targets)
            + " (use --force to re-run)."
        )

    if not pending_targets:
        print(f"done: all requested targets already applied for profile '{profile}'.")
        return 0

    try:
        now_iso = datetime.now(tz=UTC).isoformat()

        if "format-sd" in pending_targets:
            print("step: formatting SD card as public storage")
            if skip_format_sd:
                print("warning: skipped format-sd target due to --skip-format-sd")
            else:
                _confirm_format_sd(auto_confirm=auto_confirm_format_sd)
                _format_sd_as_public(adb, selected)
                target_state["format-sd"] = {"last_applied_at": now_iso}

        if "apks" in pending_targets:
            print("step: installing and configuring APK targets")
            with tempfile.TemporaryDirectory(prefix="rhc-apks-") as apk_tmp_dir:
                downloaded_apks = _download_latest_apks(
                    force=True,
                    destination_dir=Path(apk_tmp_dir),
                )
                _install_apk(adb, selected, downloaded_apks["Obtainium"], label="Obtainium")
            install_permission_report = _grant_apk_install_permissions(adb, selected)
            for line in install_permission_report:
                print(f"info: perms: {line}")
            target_state["apks"] = {"last_applied_at": now_iso}

        if "obtainium-import" in pending_targets:
            print("step: downloading and importing Obtainium emulation pack")
            pack_path = _download_obtainium_emulation_pack(
                force=True,
                destination_dir=DEFAULT_DOWNLOADS_DIR,
            )
            remote_path = _push_to_device_downloads(adb, selected, pack_path)
            print(f"info: copied Obtainium pack to device: {remote_path}")
            _automate_obtainium_import(adb, selected, pack_path, cleanup_rpc=cleanup_rpc)
            print("done: Obtainium emulation pack import triggered")
            target_state["obtainium-import"] = {"last_applied_at": now_iso}

        if "rom-cleanup" in pending_targets:
            print("step: removing preloaded ROM files")
            scanned_count, removed_count = _remove_preloaded_roms(adb, selected)
            print(
                f"done: ROM cleanup: scanned {scanned_count}, removed {removed_count} "
                "(kept systeminfo.txt)."
            )
            target_state["rom-cleanup"] = {"last_applied_at": now_iso}

        if "audio-sync" in pending_targets:
            print("step: syncing managed audio assets")
            _deploy_audio_assets_to_device(adb, selected, profile=profile)
            print("done: audio assets synced")
            target_state["audio-sync"] = {"last_applied_at": now_iso}

        if "system-sounds" in pending_targets:
            print("step: configuring system sound settings")
            _configure_system_sounds(adb, selected)
            print("done: system sounds configured")
            target_state["system-sounds"] = {"last_applied_at": now_iso}

        if "auto-rotate" in pending_targets:
            print("step: disabling auto-rotate")
            _disable_auto_rotate(adb, selected)
            print("done: auto-rotate disabled")
            target_state["auto-rotate"] = {"last_applied_at": now_iso}

        if "timezone" in pending_targets:
            print("step: applying timezone America/New_York")
            _set_timezone_new_york(adb, selected)
            print("done: timezone set to America/New_York")
            target_state["timezone"] = {"last_applied_at": now_iso}

        if "lockscreen" in pending_targets:
            print("step: disabling lock screen")
            _disable_lock_screen(adb, selected)
            print("done: lock screen disabled")
            target_state["lockscreen"] = {"last_applied_at": now_iso}

        if "remove-apps-keep-data" in pending_targets:
            print("step: removing selected apps while preserving data")
            keep_data_removal_report = _remove_apps_keep_data(adb, selected)
            for line in keep_data_removal_report:
                print(f"info: keep-data removal: {line}")
            target_state["remove-apps-keep-data"] = {"last_applied_at": now_iso}

        if "remove-apps" in pending_targets:
            print("step: uninstalling/disabling selected stock apps")
            app_report = _disable_or_uninstall_apps(adb, selected)
            for line in app_report:
                print(f"info: app cleanup: {line}")
            target_state["remove-apps"] = {"last_applied_at": now_iso}

    except subprocess.TimeoutExpired as exc:
        print(f"error: operation timed out: {exc}", file=sys.stderr)
        return 1
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        print(f"error: customization failed: {exc}", file=sys.stderr)
        return 1

    write_device_state(
        _state_dir(),
        selected,
        command=f"customize-device:{profile}",
        metadata={
            "customize_device": {
                **(customize_marker if isinstance(customize_marker, dict) else {}),
                profile: {
                    **(profile_marker if isinstance(profile_marker, dict) else {}),
                    "targets": target_state,
                    "last_applied_at": datetime.now(tz=UTC).isoformat(),
                },
            },
        },
    )
    print("done: customization complete")
    return 0


def cmd_verify_device_settings(serial: str | None) -> int:
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

    settings_to_check = [
        ("ringtone", "system"),
        ("alarm_alert", "system"),
        ("notification_sound", "system"),
        ("charging_started_sound", "global"),
        ("accelerometer_rotation", "system"),
    ]

    failed = False
    for setting_name, namespace in settings_to_check:
        result = _adb_shell(
            adb,
            selected,
            f"settings get {namespace} {setting_name}",
            check=False,
            timeout=15,
        )
        value = result.stdout.strip() if result.returncode == 0 else "<error>"
        print(f"{namespace}.{setting_name}={value}")
        if result.returncode != 0:
            failed = True

    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rhc",
        description="Retro handheld config manager.",
    )
    parser.add_argument(
        "--output",
        choices=sorted(OUTPUT_MODES),
        default=_default_output_mode(),
        help="Output mode: human-readable text (default) or JSON lines.",
    )
    parser.add_argument(
        "--log-file",
        default=os.environ.get("RHC_LOG_FILE"),
        help="Optional path to append structured JSON log events.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color output in text mode.",
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

    import_audio_parser = subparsers.add_parser(
        "import-audio-assets",
        help="Copy local audio assets into managed/<profile>/media/audio preserving structure.",
    )
    import_audio_parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        help="Profile name in configs/devices/<profile>.toml used for managed asset foldering.",
    )
    import_audio_parser.add_argument(
        "--source",
        default=DEFAULT_AUDIO_IMPORT_SOURCE,
        help="Source directory containing audio assets.",
    )
    import_audio_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files in managed/<profile>/media/audio.",
    )

    download_apks_parser = subparsers.add_parser(
        "download-apks",
        help="Download latest Obtainium APK into managed/apks.",
    )
    download_apks_parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download even when local APK files already exist.",
    )
    download_apks_parser.add_argument(
        "--destination",
        default=str(DEFAULT_APK_CACHE_DIR),
        help="Directory used to store downloaded APKs (outside repository by default).",
    )

    customize_parser = subparsers.add_parser(
        "customize-device",
        help="Apply device customization over ADB (SD format, ROM cleanup, settings, app removal).",
    )
    customize_parser.add_argument(
        "--profile",
        default=DEFAULT_PROFILE,
        help="Profile name in configs/devices/<profile>.toml used for managed assets.",
    )
    customize_parser.add_argument(
        "--serial",
        help="ADB serial to target. Defaults to first connected device.",
    )
    customize_parser.add_argument(
        "--force",
        action="store_true",
        help="Force customization even if state marker indicates prior completion.",
    )
    customize_parser.add_argument(
        "--yes-format-sd",
        action="store_true",
        help="Automatically confirm SD card formatting (destructive).",
    )
    customize_parser.add_argument(
        "--skip-format-sd",
        action="store_true",
        help="Skip SD card formatting step.",
    )
    customize_parser.add_argument(
        "--target",
        action="append",
        choices=["all", *CUSTOMIZE_TARGETS_ORDER],
        help=(
            "Run only specific customization targets. Repeat for multiple values "
            "(default: all targets)."
        ),
    )
    customize_parser.add_argument(
        "--cleanup-rpc",
        action="store_true",
        help="Stop uiautomator RPC service after Obtainium import automation completes.",
    )

    verify_settings_parser = subparsers.add_parser(
        "verify-device-settings",
        help="Print key sound and rotation settings from a connected ADB device.",
    )
    verify_settings_parser.add_argument(
        "--serial",
        help="ADB serial to target. Defaults to first connected device.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parsed_argv = list(argv) if argv is not None else sys.argv[1:]
    if parsed_argv and parsed_argv[0] == "pull-vanilla":
        parsed_argv[0] = "pull-backup"
    args = parser.parse_args(parsed_argv)
    configure_output(mode=args.output, log_file=args.log_file, no_color=args.no_color)

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
    if args.command == "import-audio-assets":
        return cmd_import_audio_assets(
            profile=args.profile,
            source=args.source,
            overwrite=args.overwrite,
        )
    if args.command == "download-apks":
        return cmd_download_apks(force=args.force, destination=args.destination)
    if args.command == "customize-device":
        return cmd_customize_device(
            profile=args.profile,
            serial=args.serial,
            force=args.force,
            auto_confirm_format_sd=args.yes_format_sd,
            skip_format_sd=args.skip_format_sd,
            targets=args.target,
            cleanup_rpc=args.cleanup_rpc,
        )
    if args.command == "verify-device-settings":
        return cmd_verify_device_settings(serial=args.serial)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
