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
  just fmt
  just lint
  just test
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

customize serial="" force="false" profile="retroid-pocket-classic-6-button-gammaos-next" yes_format_sd="false" skip_format_sd="false" targets="all" cleanup_rpc="false" output="text" log_file="" no_color="false":
  @printf "\033[1;36m==>\033[0m rhc customize-device\n"
  nix develop -c rhc --output {{output}} {{if no_color == "true" {"--no-color"} else {""}}} {{if log_file != "" {"--log-file " + log_file} else {""}}} customize-device --profile {{profile}} {{if serial == "" {""} else {if serial == "--force" {""} else {"--serial " + serial}}}} {{if force == "true" {"--force"} else {if serial == "--force" {"--force"} else {""}}}} {{if yes_format_sd == "true" {"--yes-format-sd"} else {""}}} {{if skip_format_sd == "true" {"--skip-format-sd"} else {""}}} {{if targets != "" {"--target " + targets} else {""}}} {{if cleanup_rpc == "true" {"--cleanup-rpc"} else {""}}}

customize-auto serial="" force="false" profile="retroid-pocket-classic-6-button-gammaos-next" format_sd="false" output="text" log_file="" no_color="false":
  @printf "\033[1;36m==>\033[0m rhc customize-device (auto)\n"
  nix develop -c rhc --output {{output}} {{if no_color == "true" {"--no-color"} else {""}}} {{if log_file != "" {"--log-file " + log_file} else {""}}} customize-device --profile {{profile}} {{if serial == "" {""} else {if serial == "--force" {""} else {"--serial " + serial}}}} {{if force == "true" {"--force"} else {if serial == "--force" {"--force"} else {""}}}} --yes-format-sd {{if format_sd == "true" {""} else {"--skip-format-sd"}}}

customize-target target="apks" serial="" force="false" profile="retroid-pocket-classic-6-button-gammaos-next" yes_format_sd="false" cleanup_rpc="false" output="text" log_file="" no_color="false":
  @printf "\033[1;36m==>\033[0m rhc customize-device --target {{target}}\n"
  nix develop -c rhc --output {{output}} {{if no_color == "true" {"--no-color"} else {""}}} {{if log_file != "" {"--log-file " + log_file} else {""}}} customize-device --profile {{profile}} {{if serial != "" {"--serial " + serial} else {""}}} {{if force == "true" {"--force"} else {""}}} {{if yes_format_sd == "true" {"--yes-format-sd"} else {""}}} {{if cleanup_rpc == "true" {"--cleanup-rpc"} else {""}}} --target {{target}}

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
customize-device serial="" force="false" profile="retroid-pocket-classic-6-button-gammaos-next" yes_format_sd="false" skip_format_sd="false" targets="all" cleanup_rpc="false" output="text" log_file="" no_color="false":
  just customize serial="{{serial}}" force="{{force}}" profile="{{profile}}" yes_format_sd="{{yes_format_sd}}" skip_format_sd="{{skip_format_sd}}" targets="{{targets}}" cleanup_rpc="{{cleanup_rpc}}" output="{{output}}" log_file="{{log_file}}" no_color="{{no_color}}"

customize-device-auto serial="" force="false" profile="retroid-pocket-classic-6-button-gammaos-next" format_sd="false" output="text" log_file="" no_color="false":
  just customize-auto serial="{{serial}}" force="{{force}}" profile="{{profile}}" format_sd="{{format_sd}}" output="{{output}}" log_file="{{log_file}}" no_color="{{no_color}}"

docs-serve:
  nix develop -c mkdocs serve

docs-build:
  nix develop -c mkdocs build

scrub-firebase:
  find backups -iname '*firebase*' -print -exec rm -rf {} +
