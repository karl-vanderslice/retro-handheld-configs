#!/usr/bin/env bash
set -euo pipefail

PACKAGE_NAME="com.aurora.store"
BACKUP_ROOT="backups/Android/aurora-store/current"
SERIAL=""
BW_ITEM="${RHC_BW_AGE_ITEM:-}"
IDENTITY_FILE="${RHC_AGE_IDENTITY_FILE:-}"
FORCE="false"

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
    --force)
      FORCE="true"
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

if [[ -n "${IDENTITY_FILE}" && ! -f "${IDENTITY_FILE}" ]]; then
  echo "Identity file not found: ${IDENTITY_FILE}" >&2
  exit 1
fi

LOCAL_IDENTITY_FILE="${IDENTITY_FILE}"

if ! command -v adb >/dev/null 2>&1; then
  echo "adb is required in PATH" >&2
  exit 1
fi

if ! command -v age >/dev/null 2>&1; then
  echo "age is required in PATH" >&2
  exit 1
fi

if ! command -v age-keygen >/dev/null 2>&1; then
  echo "age-keygen is required in PATH" >&2
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
if [[ -e "${BACKUP_ROOT}" ]]; then
  if [[ "${FORCE}" != "true" ]]; then
    echo "Backup already exists at ${BACKUP_ROOT}. Use --force to overwrite." >&2
    exit 1
  fi
  rm -rf "${BACKUP_ROOT}"
fi

mkdir -p "${ENCRYPTED_ROOT}"

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

if [[ -z "${IDENTITY_FILE}" ]]; then
  if [[ -z "${BW_ITEM}" ]]; then
    echo "Bitwarden item is required. Set RHC_BW_AGE_ITEM, pass --bw-item, or provide --identity-file." >&2
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

RECIPIENT="$(age-keygen -y "${IDENTITY_FILE}")"
if [[ -z "${RECIPIENT}" ]]; then
  echo "Failed to derive age recipient from identity file: ${IDENTITY_FILE}" >&2
  exit 1
fi

mkdir -p "${TMP_DIR}/plain"

LOCAL_PRIVATE_TARGET="${TMP_DIR}/plain/data/user/0/${PACKAGE_NAME}"
LOCAL_EXTERNAL_TARGET="${TMP_DIR}/plain/storage/emulated/0/Android/data/${PACKAGE_NAME}"
PRIVATE_TAR="${TMP_DIR}/private.tar"

APP_UID="$(adb -s "${SERIAL}" shell dumpsys package "${PACKAGE_NAME}" | sed -n 's/.*userId=\([0-9][0-9]*\).*/\1/p' | head -n 1 | tr -d '\r')"
if [[ -z "${APP_UID}" ]]; then
  echo "Could not determine app UID for ${PACKAGE_NAME}" >&2
  exit 1
fi

adb -s "${SERIAL}" exec-out su "${APP_UID}" -c "tar -C / -cf - data/user/0/${PACKAGE_NAME} 2>/dev/null" > "${PRIVATE_TAR}"
mkdir -p "${LOCAL_PRIVATE_TARGET}"
tar -xf "${PRIVATE_TAR}" --ignore-zeros -C "${TMP_DIR}/plain" || true

if [[ -z "$(find "${LOCAL_PRIVATE_TARGET}" -type f -print -quit 2>/dev/null || true)" ]]; then
  echo "Failed to extract private app data for ${PACKAGE_NAME}" >&2
  exit 1
fi

mkdir -p "${LOCAL_EXTERNAL_TARGET}"
adb -s "${SERIAL}" pull "/storage/emulated/0/Android/data/${PACKAGE_NAME}/." "${LOCAL_EXTERNAL_TARGET}/" >/dev/null || true

FILE_COUNT=0

while IFS= read -r -d '' file_path; do
  rel_path="${file_path#"${TMP_DIR}/plain/"}"
  out_path="${ENCRYPTED_ROOT}/${rel_path}.age"
  mkdir -p "$(dirname "${out_path}")"
  age -r "${RECIPIENT}" -o "${out_path}" "${file_path}"
  FILE_COUNT=$((FILE_COUNT + 1))
done < <(find "${TMP_DIR}/plain" -type f -print0 | sort -z)

cat > "${BACKUP_ROOT}/metadata.json" <<EOF
{
  "package": "${PACKAGE_NAME}",
  "serial": "${SERIAL}",
  "backup_dir": "current",
  "encrypted_with": "age-identity",
  "bitwarden_item": "${BW_ITEM}",
  "identity_file": "${LOCAL_IDENTITY_FILE}",
  "file_count": ${FILE_COUNT}
}
EOF

find "${BACKUP_ROOT}" -type f \( -name '*.tar' -o -name '*.zip' -o -name '*.tgz' -o -name '*.gz' -o -name '*.7z' \) -delete

echo "Secure Aurora backup complete: ${BACKUP_ROOT} (${FILE_COUNT} encrypted files)"
