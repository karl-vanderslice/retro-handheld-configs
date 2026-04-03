#!/usr/bin/env bash
set -euo pipefail

PACKAGE_NAME="com.aurora.store"
BACKUP_ROOT="backups/Android/aurora-store/current"
SERIAL=""
BW_ITEM="${RHC_BW_AGE_ITEM:-}"
IDENTITY_FILE="${RHC_AGE_IDENTITY_FILE:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --serial)
      SERIAL="$2"
      shift 2
      ;;
    --bw-item)
      BW_ITEM="$2"
      shift 2
      ;;
    --identity-file)
      IDENTITY_FILE="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -z "${IDENTITY_FILE}" && -f "${BACKUP_ROOT}/metadata.json" ]]; then
  IDENTITY_FILE="$(sed -n 's/.*"identity_file"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${BACKUP_ROOT}/metadata.json" | head -n 1)"
fi

if [[ -n "${IDENTITY_FILE}" && ! -f "${IDENTITY_FILE}" ]]; then
  echo "Identity file not found: ${IDENTITY_FILE}" >&2
  exit 1
fi

if [[ -z "${BW_ITEM}" && -f "${BACKUP_ROOT}/metadata.json" ]]; then
  BW_ITEM="$(sed -n 's/.*"bitwarden_item"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "${BACKUP_ROOT}/metadata.json" | head -n 1)"
fi

if [[ -z "${IDENTITY_FILE}" ]]; then
  if [[ -z "${BW_ITEM}" ]]; then
    echo "Bitwarden item is required. Set RHC_BW_AGE_ITEM, pass --bw-item, provide --identity-file, or include metadata hints." >&2
    exit 1
  fi

  if ! command -v bw >/dev/null 2>&1; then
    echo "bw (Bitwarden CLI) is required in PATH" >&2
    exit 1
  fi

  if [[ -z "${BW_SESSION:-}" ]]; then
    echo "BW_SESSION is not set. Unlock Bitwarden first (for example: export BW_SESSION=\"\$(bw unlock --raw)\")." >&2
    exit 1
  fi

  BW_STATUS="$(bw status --session "${BW_SESSION}" 2>/dev/null || true)"
  if ! printf '%s' "${BW_STATUS}" | grep -q '"status":"unlocked"'; then
    echo "Bitwarden vault is not unlocked for this shell session. Run bw unlock and export BW_SESSION." >&2
    exit 1
  fi
fi

if ! command -v adb >/dev/null 2>&1; then
  echo "adb is required in PATH" >&2
  exit 1
fi

if ! command -v age >/dev/null 2>&1; then
  echo "age is required in PATH" >&2
  exit 1
fi

if [[ -z "${SERIAL}" ]]; then
  SERIAL="$(adb devices | awk '/\tdevice$/{print $1; exit}')"
fi

if [[ -z "${SERIAL}" ]]; then
  echo "No connected ADB device found" >&2
  exit 1
fi

ENCRYPTED_ROOT="${BACKUP_ROOT}/encrypted"
if [[ ! -d "${ENCRYPTED_ROOT}" ]]; then
  echo "Encrypted backup not found: ${ENCRYPTED_ROOT}" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

mkdir -p "${TMP_DIR}/plain"

if [[ -z "${IDENTITY_FILE}" ]]; then
  IDENTITY_FILE="${TMP_DIR}/bitwarden-age-identity.txt"
  AGE_IDENTITY="$(bw get notes "${BW_ITEM}" --session "${BW_SESSION}" 2>/dev/null || true)"
  if [[ -z "${AGE_IDENTITY}" ]]; then
    echo "Failed to read age identity from Bitwarden item: ${BW_ITEM}" >&2
    exit 1
  fi

  if ! printf '%s' "${AGE_IDENTITY}" | grep -q '^AGE-SECRET-KEY-'; then
    echo "Bitwarden item ${BW_ITEM} does not contain an age identity key (AGE-SECRET-KEY-...)." >&2
    exit 1
  fi

  printf '%s\n' "${AGE_IDENTITY}" > "${IDENTITY_FILE}"
  chmod 600 "${IDENTITY_FILE}"
fi

while IFS= read -r -d '' encrypted_file; do
  rel_path="${encrypted_file#${ENCRYPTED_ROOT}/}"
  rel_path="${rel_path%.age}"
  out_file="${TMP_DIR}/plain/${rel_path}"
  mkdir -p "$(dirname "${out_file}")"
  age -d -i "${IDENTITY_FILE}" -o "${out_file}" "${encrypted_file}"
done < <(find "${ENCRYPTED_ROOT}" -type f -name '*.age' -print0 | sort -z)

adb -s "${SERIAL}" shell am force-stop "${PACKAGE_NAME}"

PRIVATE_SRC="${TMP_DIR}/plain/data/user/0/${PACKAGE_NAME}"
if [[ -d "${PRIVATE_SRC}" ]]; then
  REMOTE_STAGE_PRIVATE="/sdcard/Download/rhc-restore-private-${PACKAGE_NAME}"
  adb -s "${SERIAL}" shell "rm -rf ${REMOTE_STAGE_PRIVATE} && mkdir -p ${REMOTE_STAGE_PRIVATE}"
  adb -s "${SERIAL}" push "${PRIVATE_SRC}/." "${REMOTE_STAGE_PRIVATE}/"

  adb -s "${SERIAL}" shell su -c "mkdir -p /data/user/0/${PACKAGE_NAME}"
  adb -s "${SERIAL}" shell su -c "cp -a ${REMOTE_STAGE_PRIVATE}/. /data/user/0/${PACKAGE_NAME}/"

  APP_UID="$(adb -s "${SERIAL}" shell dumpsys package "${PACKAGE_NAME}" | sed -n 's/.*userId=\([0-9][0-9]*\).*/\1/p' | head -n 1 | tr -d '\r')"
  if [[ -n "${APP_UID}" ]]; then
    adb -s "${SERIAL}" shell su -c "chown -R ${APP_UID}:${APP_UID} /data/user/0/${PACKAGE_NAME}"
  fi

  adb -s "${SERIAL}" shell "rm -rf ${REMOTE_STAGE_PRIVATE}"
fi

EXTERNAL_SRC="${TMP_DIR}/plain/storage/emulated/0/Android/data/${PACKAGE_NAME}"
if [[ -d "${EXTERNAL_SRC}" ]]; then
  REMOTE_STAGE_EXTERNAL="/sdcard/Download/rhc-restore-external-${PACKAGE_NAME}"
  adb -s "${SERIAL}" shell "rm -rf ${REMOTE_STAGE_EXTERNAL} && mkdir -p ${REMOTE_STAGE_EXTERNAL}"
  adb -s "${SERIAL}" push "${EXTERNAL_SRC}/." "${REMOTE_STAGE_EXTERNAL}/"
  adb -s "${SERIAL}" shell "mkdir -p /storage/emulated/0/Android/data/${PACKAGE_NAME}"
  adb -s "${SERIAL}" shell "cp -a ${REMOTE_STAGE_EXTERNAL}/. /storage/emulated/0/Android/data/${PACKAGE_NAME}/"
  adb -s "${SERIAL}" shell "rm -rf ${REMOTE_STAGE_EXTERNAL}"
fi

echo "Secure Aurora restore complete from ${BACKUP_ROOT} on device ${SERIAL}"
