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

hello serial="":
  nix develop -c rhc hello {{if serial != "" {"--serial " + serial} else {""}}}

pull-stock profile="retroid-pocket-classic-6-button-gammaos-next" serial="" force="false":
  nix develop -c rhc pull-stock --profile {{profile}} {{if serial != "" {"--serial " + serial} else {""}}} {{if force == "true" {"--force"} else {""}}}

pull-stock-root profile="retroid-pocket-classic-6-button-gammaos-next" serial="" force="false":
  nix develop -c rhc pull-stock --root --profile {{profile}} {{if serial != "" {"--serial " + serial} else {""}}} {{if force == "true" {"--force"} else {""}}}

migrate-state dry_run="true":
  nix develop -c rhc migrate-state {{if dry_run == "true" {"--dry-run"} else {""}}}

state-doctor:
  nix develop -c rhc state-doctor

import-audio-assets profile="retroid-pocket-classic-6-button-gammaos-next" source="/Volumes/media-emulation/Devices/Retroid Pocket Classic/6 Button/sdcard/media/audio" overwrite="false":
  nix develop -c rhc import-audio-assets --profile {{profile}} --source {{source}} {{if overwrite == "true" {"--overwrite"} else {""}}}

download-apks force="false" destination="$HOME/.cache/rhc/apks":
  nix develop -c rhc download-apks {{if force == "true" {"--force"} else {""}}} --destination {{destination}}

customize serial="" force="false" profile="retroid-pocket-classic-6-button-gammaos-next" yes_format_sd="false" skip_format_sd="false":
  nix develop -c rhc customize-device --profile {{profile}} {{if serial == "" {""} else {if serial == "--force" {""} else {"--serial " + serial}}}} {{if force == "true" {"--force"} else {if serial == "--force" {"--force"} else {""}}}} {{if yes_format_sd == "true" {"--yes-format-sd"} else {""}}} {{if skip_format_sd == "true" {"--skip-format-sd"} else {""}}}

customize-auto serial="" force="false" profile="retroid-pocket-classic-6-button-gammaos-next" format_sd="false":
  nix develop -c rhc customize-device --profile {{profile}} {{if serial == "" {""} else {if serial == "--force" {""} else {"--serial " + serial}}}} {{if force == "true" {"--force"} else {if serial == "--force" {"--force"} else {""}}}} --yes-format-sd {{if format_sd == "true" {""} else {"--skip-format-sd"}}}

# Legacy aliases (kept for compatibility)
customize-device serial="" force="false" profile="retroid-pocket-classic-6-button-gammaos-next" yes_format_sd="false" skip_format_sd="false":
  just customize serial="{{serial}}" force="{{force}}" profile="{{profile}}" yes_format_sd="{{yes_format_sd}}" skip_format_sd="{{skip_format_sd}}"

customize-device-auto serial="" force="false" profile="retroid-pocket-classic-6-button-gammaos-next" format_sd="false":
  just customize-auto serial="{{serial}}" force="{{force}}" profile="{{profile}}" format_sd="{{format_sd}}"

docs-serve:
  nix develop -c mkdocs serve

docs-build:
  nix develop -c mkdocs build

scrub-firebase:
  find backups -iname '*firebase*' -print -exec rm -rf {} +
