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

docs-serve:
  nix develop -c mkdocs serve

docs-build:
  nix develop -c mkdocs build

scrub-firebase:
  find backups -iname '*firebase*' -print -exec rm -rf {} +
