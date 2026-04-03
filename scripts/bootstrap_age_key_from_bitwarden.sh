#!/usr/bin/env bash
set -euo pipefail

BW_ITEM="${RHC_BW_AGE_ITEM:-}"
OUT_FILE="${RHC_AGE_IDENTITY_FILE:-.rhc-secrets/age-identity.txt}"
FORCE="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bw-item)
      BW_ITEM="$2"
      shift 2
      ;;
    --out-file)
      OUT_FILE="$2"
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

if [[ -z "${BW_ITEM}" ]]; then
  echo "Bitwarden item is required. Set RHC_BW_AGE_ITEM or pass --bw-item." >&2
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

if [[ -e "${OUT_FILE}" && "${FORCE}" != "true" ]]; then
  echo "Output file already exists at ${OUT_FILE}. Use --force to overwrite." >&2
  exit 1
fi

AGE_IDENTITY="$(bw get notes "${BW_ITEM}" --session "${BW_SESSION}" 2>/dev/null || true)"
if [[ -z "${AGE_IDENTITY}" ]]; then
  echo "Failed to read age identity from Bitwarden item: ${BW_ITEM}" >&2
  exit 1
fi

if ! printf '%s' "${AGE_IDENTITY}" | grep -q '^AGE-SECRET-KEY-'; then
  echo "Bitwarden item ${BW_ITEM} does not contain an age identity key (AGE-SECRET-KEY-...)." >&2
  exit 1
fi

mkdir -p "$(dirname "${OUT_FILE}")"
printf '%s\n' "${AGE_IDENTITY}" > "${OUT_FILE}"
chmod 600 "${OUT_FILE}"

echo "Bootstrapped age identity to ${OUT_FILE}"
