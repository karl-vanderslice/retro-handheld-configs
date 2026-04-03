{
  description = "Retro handheld config toolkit (ADB + SD workflows)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    git-hooks.url = "github:cachix/git-hooks.nix";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
      git-hooks,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
        inherit (pkgs)
          age
          android-tools
          bitwarden-cli
          coreutils
          git
          gnugrep
          just
          mkdocs
          pre-commit
          ruff
          ;
        python = pkgs.python312;
        pythonPackages = pkgs.python312Packages;

        retry2 = pythonPackages.buildPythonPackage rec {
          pname = "retry2";
          version = "0.9.5";
          format = "wheel";

          src = pythonPackages.fetchPypi {
            inherit pname version format;
            python = "py2.py3";
            abi = "none";
            platform = "any";
            hash = "sha256-9/7hOx4V0GEcRikQpqpyqJGYI5iN0EEhUrw3GciaTlU=";
          };

          propagatedBuildInputs = [ pythonPackages.decorator ];

          doCheck = false;
        };

        adbutils = pythonPackages.buildPythonPackage rec {
          pname = "adbutils";
          version = "2.12.0";
          pyproject = true;
          build-system = [
            pythonPackages.setuptools
            pythonPackages.pbr
          ];

          src = pythonPackages.fetchPypi {
            inherit pname version;
            hash = "sha256-NlOo85c1YgvEWxXuLnoA5QLJ8aJZRS4fsru6PqWdDmg=";
          };

          propagatedBuildInputs = [
            pythonPackages.deprecation
            pythonPackages.pillow
            pythonPackages.requests
            retry2
          ];

          doCheck = false;
        };

        uiautomator2 = pythonPackages.buildPythonPackage rec {
          pname = "uiautomator2";
          version = "3.5.0";
          pyproject = true;
          build-system = [
            pythonPackages.poetry-core
            pythonPackages.poetry-dynamic-versioning
          ];

          src = pythonPackages.fetchPypi {
            inherit pname version;
            hash = "sha256-9vXkAjgsOmYtvaCs6JxpHI0/mqNAQS+Lv89fCCSaIaY=";
          };

          propagatedBuildInputs = [
            adbutils
            pythonPackages.lxml
            pythonPackages.pillow
            pythonPackages.requests
            retry2
          ];

          doCheck = false;
        };

        rhc = pkgs.writeShellScriptBin "rhc" ''
          export PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}"
          exec ${python}/bin/python -m rhc.cli "$@"
        '';

        conventionalCommitCheck = pkgs.writeShellApplication {
          name = "conventional-commit-check";
          runtimeInputs = [
            gnugrep
            coreutils
          ];
          text = ''
            set -euo pipefail
            msgFile="$1"
            firstLine="$(head -n1 "$msgFile")"
            pattern='^(build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)(\([a-z0-9._/-]+\))?(!)?: .+'
            if ! printf "%s" "$firstLine" | grep -Eq "$pattern"; then
              echo "Conventional Commit required." >&2
              echo "Expected: type(scope?): description" >&2
              echo "Allowed types: build,chore,ci,docs,feat,fix,perf,refactor,revert,style,test" >&2
              echo "Got: $firstLine" >&2
              exit 1
            fi
          '';
        };

        encryptedBackupCheck = pkgs.writeShellApplication {
          name = "ensure-encrypted-backups";
          runtimeInputs = [
            git
            gnugrep
            coreutils
          ];
          text = ''
            set -euo pipefail

            tracked_files="$(git ls-files -- backups/Android backups/Android/aurora-store/current || true)"
            if [[ -z "$tracked_files" ]]; then
              exit 0
            fi

            if printf '%s\n' "$tracked_files" | grep -E '\.(tar|zip|tgz|gz|7z)$' >/dev/null; then
              echo "Archive files are not allowed under backups/Android." >&2
              printf '%s\n' "$tracked_files" | grep -E '\.(tar|zip|tgz|gz|7z)$' >&2 || true
              exit 1
            fi

            aurora_tracked="$(printf '%s\n' "$tracked_files" | grep '^backups/Android/aurora-store/current/' || true)"
            if [[ -z "$aurora_tracked" ]]; then
              exit 0
            fi

            invalid_files="$(
              printf '%s\n' "$aurora_tracked" | grep -Ev \
                '^backups/Android/aurora-store/current/metadata\.json$|^backups/Android/aurora-store/current/encrypted/.+\.age$' \
                || true
            )"

            if [[ -n "$invalid_files" ]]; then
              echo "Unencrypted Aurora backup files detected; only metadata.json and .age files are allowed:" >&2
              printf '%s\n' "$invalid_files" >&2
              exit 1
            fi
          '';
        };

        preCommitCheck = git-hooks.lib.${system}.run {
          src = ./.;
          hooks = {
            nixfmt.enable = true;
            ruff = {
              enable = true;
              excludes = [ "^backups/" ];
            };
            ruff-format = {
              enable = true;
              excludes = [ "^backups/" ];
            };
            end-of-file-fixer = {
              enable = true;
              excludes = [ "^backups/" ];
            };
            trim-trailing-whitespace = {
              enable = true;
              excludes = [ "^backups/" ];
            };

            conventional-commits = {
              enable = true;
              name = "conventional-commits";
              entry = "${conventionalCommitCheck}/bin/conventional-commit-check";
              pass_filenames = true;
              stages = [ "commit-msg" ];
              always_run = true;
            };

            encrypted-backups = {
              enable = true;
              name = "encrypted-backups";
              entry = "${encryptedBackupCheck}/bin/ensure-encrypted-backups";
              pass_filenames = false;
              always_run = true;
            };
          };
        };
      in
      {
        checks = {
          pre-commit-check = preCommitCheck;
        };

        devShells.default = pkgs.mkShell {
          inherit (preCommitCheck) shellHook;

          packages = [
            android-tools
            age
            bitwarden-cli
            just
            git
            mkdocs
            pythonPackages.pytest
            pythonPackages.mkdocs-material
            pre-commit
            ruff
            python
            uiautomator2
            rhc
          ];

          env = {
            RHC_STATE_DIR = ".rhc-state";
          };
        };
      }
    );
}
