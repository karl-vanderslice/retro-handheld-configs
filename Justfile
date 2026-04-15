set shell := ["bash", "-cu"]

default:
  @just --list

shell:
  nix develop

fmt:
  nix develop -c ruff format src tests

lint:
  nix develop -c ruff check src tests

test:
  nix develop -c env PYTHONPATH=src pytest -q

check:
  nix develop -c just fmt
  nix develop -c just lint
  nix develop -c just test
  nix flake check

precommit:
  nix develop -c pre-commit run --all-files

clean:
  nix develop -c git clean -fdx -e .pre-commit-config.yml -e .pre-commit-config.yaml -e backups/ -e tests_cli.py -e tests/tests_cli.py -e .direnv/

hello serial="" output="text" log_file="" no_color="false":
  @printf "\033[1;36m==>\033[0m rhc hello\n"
  nix develop -c rhc --output {{output}} {{if no_color == "true" {"--no-color"} else {""}}} {{if log_file != "" {"--log-file " + log_file} else {""}}} hello {{if serial != "" {"--serial " + serial} else {""}}}

pull-stock profile="retroid-pocket-classic-6-button-gammaos-next" serial="" force="false" output="text" log_file="" no_color="false":
  @printf "\033[1;36m==>\033[0m rhc pull-stock\n"
  nix develop -c rhc --output {{output}} {{if no_color == "true" {"--no-color"} else {""}}} {{if log_file != "" {"--log-file " + log_file} else {""}}} pull-stock --profile {{profile}} {{if serial != "" {"--serial " + serial} else {""}}} {{if force == "true" {"--force"} else {""}}}

pull-stock-root profile="retroid-pocket-classic-6-button-gammaos-next" serial="" force="false" output="text" log_file="" no_color="false":
  @printf "\033[1;36m==>\033[0m rhc pull-stock --root\n"
  nix develop -c rhc --output {{output}} {{if no_color == "true" {"--no-color"} else {""}}} {{if log_file != "" {"--log-file " + log_file} else {""}}} pull-stock --root --profile {{profile}} {{if serial != "" {"--serial " + serial} else {""}}} {{if force == "true" {"--force"} else {""}}}

migrate-state dry_run="true" output="text" log_file="" no_color="false":
  @printf "\033[1;36m==>\033[0m rhc migrate-state\n"
  nix develop -c rhc --output {{output}} {{if no_color == "true" {"--no-color"} else {""}}} {{if log_file != "" {"--log-file " + log_file} else {""}}} migrate-state {{if dry_run == "true" {"--dry-run"} else {""}}}

state-doctor output="text" log_file="" no_color="false":
  @printf "\033[1;36m==>\033[0m rhc state-doctor\n"
  nix develop -c rhc --output {{output}} {{if no_color == "true" {"--no-color"} else {""}}} {{if log_file != "" {"--log-file " + log_file} else {""}}} state-doctor

import-audio-assets profile="retroid-pocket-classic-6-button-gammaos-next" source="/Volumes/media-emulation/Devices/Retroid Pocket Classic/6 Button/sdcard/media/audio" overwrite="false" output="text" log_file="" no_color="false":
  @printf "\033[1;36m==>\033[0m rhc import-audio-assets\n"
  nix develop -c rhc --output {{output}} {{if no_color == "true" {"--no-color"} else {""}}} {{if log_file != "" {"--log-file " + log_file} else {""}}} import-audio-assets --profile {{profile}} --source {{source}} {{if overwrite == "true" {"--overwrite"} else {""}}}

download-apks force="false" destination="$HOME/.cache/rhc/apks" output="text" log_file="" no_color="false":
  @printf "\033[1;36m==>\033[0m rhc download-apks\n"
  nix develop -c rhc --output {{output}} {{if no_color == "true" {"--no-color"} else {""}}} {{if log_file != "" {"--log-file " + log_file} else {""}}} download-apks {{if force == "true" {"--force"} else {""}}} --destination {{destination}}

customize *args:
  @printf "\033[1;36m==>\033[0m rhc customize-device\n"
  profile="retroid-pocket-classic-6-button-gammaos-next"; \
  output="text"; \
  log_file=""; \
  serial=""; \
  no_color="false"; \
  force="false"; \
  yes_format_sd="false"; \
  skip_format_sd="false"; \
  cleanup_rpc="false"; \
  targets="all"; \
  passthrough_flags=(); \
  for token in {{args}}; do \
    case "$token" in \
      profile=*) profile="${token#profile=}" ;; \
      output=*) output="${token#output=}" ;; \
      log_file=*) log_file="${token#log_file=}" ;; \
      serial=*) serial="${token#serial=}" ;; \
      no_color=*) no_color="${token#no_color=}" ;; \
      force=*) force="${token#force=}" ;; \
      yes_format_sd=*) yes_format_sd="${token#yes_format_sd=}" ;; \
      skip_format_sd=*) skip_format_sd="${token#skip_format_sd=}" ;; \
      cleanup_rpc=*) cleanup_rpc="${token#cleanup_rpc=}" ;; \
      targets=*) targets="${token#targets=}" ;; \
      --profile|--output|--log-file|--serial|--target) passthrough_flags+=("$token") ;; \
      --no-color) no_color="true" ;; \
      --force) force="true" ;; \
      --yes-format-sd) yes_format_sd="true" ;; \
      --skip-format-sd) skip_format_sd="true" ;; \
      --cleanup-rpc) cleanup_rpc="true" ;; \
      --*) passthrough_flags+=("$token") ;; \
      *) ;; \
    esac; \
  done; \
  cmd=(nix develop -c rhc --output "$output"); \
  if [[ "$no_color" == "true" ]]; then cmd+=(--no-color); fi; \
  if [[ -n "$log_file" ]]; then cmd+=(--log-file "$log_file"); fi; \
  cmd+=(customize-device --profile "$profile"); \
  if [[ -n "$serial" ]]; then cmd+=(--serial "$serial"); fi; \
  if [[ "$force" == "true" ]]; then cmd+=(--force); fi; \
  if [[ "$yes_format_sd" == "true" ]]; then cmd+=(--yes-format-sd); fi; \
  if [[ "$skip_format_sd" == "true" ]]; then cmd+=(--skip-format-sd); fi; \
  if [[ "$cleanup_rpc" == "true" ]]; then cmd+=(--cleanup-rpc); fi; \
  if [[ -n "$targets" ]]; then \
    IFS=',' read -r -a target_array <<< "$targets"; \
    for target in "${target_array[@]}"; do \
      if [[ -n "$target" ]]; then cmd+=(--target "$target"); fi; \
    done; \
  fi; \
  if [[ "${#passthrough_flags[@]}" -gt 0 ]]; then cmd+=("${passthrough_flags[@]}"); fi; \
  "${cmd[@]}"

customize-workflow *args:
  just customize {{args}}

customize-auto serial="" force="false" profile="retroid-pocket-classic-6-button-gammaos-next" format_sd="false" output="text" log_file="" no_color="false":
  @printf "\033[1;36m==>\033[0m rhc customize-device (auto)\n"
  nix develop -c rhc --output {{output}} {{if no_color == "true" {"--no-color"} else {""}}} {{if log_file != "" {"--log-file " + log_file} else {""}}} customize-device --profile {{profile}} {{if serial == "" {""} else {if serial == "--force" {""} else {"--serial " + serial}}}} {{if force == "true" {"--force"} else {if serial == "--force" {"--force"} else {""}}}} --yes-format-sd {{if format_sd == "true" {""} else {"--skip-format-sd"}}}

customize-target *args:
  target="apks"; \
  profile="retroid-pocket-classic-6-button-gammaos-next"; \
  serial=""; \
  force="false"; \
  yes_format_sd="false"; \
  cleanup_rpc="false"; \
  output="text"; \
  log_file=""; \
  no_color="false"; \
  for token in {{args}}; do \
    case "$token" in \
      target=*) target="${token#target=}" ;; \
      target_name=*) target="${token#target_name=}" ;; \
      profile=*) profile="${token#profile=}" ;; \
      serial=*) serial="${token#serial=}" ;; \
      force=*) force="${token#force=}" ;; \
      yes_format_sd=*) yes_format_sd="${token#yes_format_sd=}" ;; \
      cleanup_rpc=*) cleanup_rpc="${token#cleanup_rpc=}" ;; \
      output=*) output="${token#output=}" ;; \
      log_file=*) log_file="${token#log_file=}" ;; \
      no_color=*) no_color="${token#no_color=}" ;; \
      *) ;; \
    esac; \
  done; \
  just customize profile="$profile" serial="$serial" force="$force" yes_format_sd="$yes_format_sd" cleanup_rpc="$cleanup_rpc" output="$output" log_file="$log_file" no_color="$no_color" targets="$target"

format-sd serial="" force="false" profile="retroid-pocket-classic-6-button-gammaos-next" yes_format_sd="false" output="text" log_file="" no_color="false":
  just customize-target target="format-sd" serial="{{serial}}" force="{{force}}" profile="{{profile}}" yes_format_sd="{{yes_format_sd}}" output="{{output}}" log_file="{{log_file}}" no_color="{{no_color}}"

configure-apks serial="" force="false" profile="retroid-pocket-classic-6-button-gammaos-next" output="text" log_file="" no_color="false":
  just customize-target target="apks" serial="{{serial}}" force="{{force}}" profile="{{profile}}" output="{{output}}" log_file="{{log_file}}" no_color="{{no_color}}"

import-obtainium-pack force="false" cleanup_rpc="true" serial="" profile="retroid-pocket-classic-6-button-gammaos-next" output="text" log_file="" no_color="false":
  @printf "\033[1;36m==>\033[0m rhc customize-device --target obtainium-import\n"
  nix develop -c rhc --output {{output}} {{if no_color == "true" {"--no-color"} else {""}}} {{if log_file != "" {"--log-file " + log_file} else {""}}} customize-device --profile {{profile}} {{if serial != "" {"--serial " + serial} else {""}}} {{if force == "true" {"--force"} else {if force == "force=true" {"--force"} else {""}}}} {{if cleanup_rpc == "true" {"--cleanup-rpc"} else {if cleanup_rpc == "cleanup_rpc=true" {"--cleanup-rpc"} else {""}}}} --target obtainium-import

verify-settings serial="" output="text" log_file="" no_color="false":
  @printf "\033[1;36m==>\033[0m rhc verify-device-settings\n"
  nix develop -c rhc --output {{output}} {{if no_color == "true" {"--no-color"} else {""}}} {{if log_file != "" {"--log-file " + log_file} else {""}}} verify-device-settings {{if serial != "" {"--serial " + serial} else {""}}}

# Legacy aliases (kept for compatibility)
customize-device *args:
  just customize {{args}}

customize-device-auto *args:
  just customize-auto {{args}}

docs-serve:
  nix develop -c zensical serve

docs-build:
  nix develop -c zensical build

scrub-firebase:
  nix develop -c find backups -iname '*firebase*' -print -exec rm -rf {} +

adb-root serial="":
  @printf "\033[1;36m==>\033[0m enable adb root\n"
  nix develop -c bash scripts/enable_adb_root.sh {{if serial != "" {"--serial " + serial} else {""}}}

backup-aurora-secure *args:
  @printf "\033[1;36m==>\033[0m encrypted Aurora backup\n"
  bw_item=""; \
  identity_file=""; \
  for token in {{args}}; do \
    case "$token" in \
      bw_item=*) bw_item="${token#bw_item=}" ;; \
      identity_file=*) identity_file="${token#identity_file=}" ;; \
      --bw-item=*) bw_item="${token#--bw-item=}" ;; \
      --identity-file=*) identity_file="${token#--identity-file=}" ;; \
      *) ;; \
    esac; \
  done; \
  cmd=(nix develop -c bash scripts/backup_aurora_secure.sh --force); \
  if [[ -n "$bw_item" ]]; then cmd+=(--bw-item "$bw_item"); fi; \
  if [[ -n "$identity_file" ]]; then cmd+=(--identity-file "$identity_file"); fi; \
  "${cmd[@]}"

restore-aurora-secure *args:
  @printf "\033[1;36m==>\033[0m encrypted Aurora restore\n"
  bw_item=""; \
  identity_file=""; \
  for token in {{args}}; do \
    case "$token" in \
      bw_item=*) bw_item="${token#bw_item=}" ;; \
      identity_file=*) identity_file="${token#identity_file=}" ;; \
      --bw-item=*) bw_item="${token#--bw-item=}" ;; \
      --identity-file=*) identity_file="${token#--identity-file=}" ;; \
      *) ;; \
    esac; \
  done; \
  cmd=(nix develop -c bash scripts/restore_aurora_secure.sh); \
  if [[ -n "$bw_item" ]]; then cmd+=(--bw-item "$bw_item"); fi; \
  if [[ -n "$identity_file" ]]; then cmd+=(--identity-file "$identity_file"); fi; \
  "${cmd[@]}"

bootstrap-age-key *args:
  @printf "\033[1;36m==>\033[0m bootstrap age key from Bitwarden\n"
  bw_item=""; \
  out_file=".rhc-secrets/age-identity.txt"; \
  force="false"; \
  for token in {{args}}; do \
    case "$token" in \
      bw_item=*) bw_item="${token#bw_item=}" ;; \
      out_file=*) out_file="${token#out_file=}" ;; \
      force=*) force="${token#force=}" ;; \
      --bw-item=*) bw_item="${token#--bw-item=}" ;; \
      --out-file=*) out_file="${token#--out-file=}" ;; \
      --force) force="true" ;; \
      *) ;; \
    esac; \
  done; \
  cmd=(nix develop -c bash scripts/bootstrap_age_key_from_bitwarden.sh --out-file "$out_file"); \
  if [[ -n "$bw_item" ]]; then cmd+=(--bw-item "$bw_item"); fi; \
  if [[ "$force" == "true" ]]; then cmd+=(--force); fi; \
  "${cmd[@]}"
