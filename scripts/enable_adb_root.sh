#!/usr/bin/env bash
set -euo pipefail

SERIAL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --serial)
      SERIAL="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if ! command -v adb >/dev/null 2>&1; then
  echo "adb is required in PATH" >&2
  exit 1
fi

if [[ -z "${SERIAL}" ]]; then
  SERIAL="$(adb devices | awk '/\tdevice$/{print $1; exit}')"
fi

if [[ -z "${SERIAL}" ]]; then
  echo "No connected ADB device found" >&2
  exit 1
fi

current_uid="$(adb -s "${SERIAL}" shell id -u 2>/dev/null | tr -d '\r' || true)"
if [[ "${current_uid}" == "0" ]]; then
  echo "ADB root already enabled on ${SERIAL}"
  exit 0
fi

root_output="$(adb -s "${SERIAL}" root 2>&1 || true)"
echo "${root_output}"

if printf '%s' "${root_output}" | grep -qi "disabled by system setting"; then
  echo "WARNING: ADB root access is not enabled on ${SERIAL}." >&2
  echo "Enable it on device: Settings -> System -> Developer options -> ADB Root access (or Rooted debugging), then rerun 'just adb-root'." >&2
fi

adb wait-for-device
sleep 1

current_uid="$(adb -s "${SERIAL}" shell id -u 2>/dev/null | tr -d '\r' || true)"
if [[ "${current_uid}" == "0" ]]; then
  echo "ADB root enabled on ${SERIAL}"
  exit 0
fi

adb -s "${SERIAL}" shell su -c "setprop service.adb.root 1; setprop persist.adb.root 1; stop adbd; start adbd" >/dev/null 2>&1 || true
adb wait-for-device
sleep 1

current_uid="$(adb -s "${SERIAL}" shell id -u 2>/dev/null | tr -d '\r' || true)"
if [[ "${current_uid}" == "0" ]]; then
  echo "ADB root enabled on ${SERIAL} (via su property toggle)"
  exit 0
fi

echo "Failed to enable root adbd on ${SERIAL}. Device may not support adb root builds." >&2
echo "If available on your ROM: Settings -> System -> Developer options -> ADB Root access / Rooted debugging." >&2
echo "For this Retroid Pocket Classic 6-Button workflow (Sega/DOS/Arcade), keep root shell available via su for private-data operations." >&2
exit 1
