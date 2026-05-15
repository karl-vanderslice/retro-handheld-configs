#!/usr/bin/env bash
set -euo pipefail

RBW_ITEM="${RHC_RBW_AGE_ITEM:-}"
OUT_FILE="${RHC_AGE_IDENTITY_FILE:-.rhc-secrets/age-identity.txt}"
FORCE="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --rbw-item)
      RBW_ITEM="$2"
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

if [[ -z "${RBW_ITEM}" ]]; then
  echo "rbw item is required. Set RHC_RBW_AGE_ITEM or pass --rbw-item." >&2
  exit 1
fi

if ! command -v rbw >/dev/null 2>&1; then
  echo "rbw is required in PATH" >&2
  exit 1
fi

if ! rbw unlock >/dev/null 2>&1; then
  echo "rbw unlock failed. Ensure rbw-agent is running and credentials are configured." >&2
  exit 1
fi

if ! rbw sync >/dev/null 2>&1; then
  echo "rbw sync failed." >&2
  exit 1
fi

if [[ -e "${OUT_FILE}" && "${FORCE}" != "true" ]]; then
  echo "Output file already exists at ${OUT_FILE}. Use --force to overwrite." >&2
  exit 1
fi

AGE_IDENTITY="$(rbw get --field notes "${RBW_ITEM}" 2>/dev/null || rbw get "${RBW_ITEM}" 2>/dev/null || true)"
if [[ -z "${AGE_IDENTITY}" ]]; then
  echo "Failed to read age identity from rbw item: ${RBW_ITEM}" >&2
  exit 1
fi

if ! printf '%s' "${AGE_IDENTITY}" | grep -q '^AGE-SECRET-KEY-'; then
  echo "rbw item ${RBW_ITEM} does not contain an age identity key (AGE-SECRET-KEY-...)." >&2
  exit 1
fi

mkdir -p "$(dirname "${OUT_FILE}")"
printf '%s\n' "${AGE_IDENTITY}" > "${OUT_FILE}"
chmod 600 "${OUT_FILE}"

echo "Bootstrapped age identity to ${OUT_FILE}"
