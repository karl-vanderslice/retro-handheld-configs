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
        python = pkgs.python312;
        rhc = pkgs.writeShellScriptBin "rhc" ''
          export PYTHONPATH="$PWD/src''${PYTHONPATH:+:$PYTHONPATH}"
          exec ${python}/bin/python -m rhc.cli "$@"
        '';

        conventionalCommitCheck = pkgs.writeShellApplication {
          name = "conventional-commit-check";
          runtimeInputs = [
            pkgs.gnugrep
            pkgs.coreutils
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
            pkgs.android-tools
            pkgs.just
            pkgs.git
            pkgs.mkdocs
            pkgs.python312Packages.pytest
            pkgs.python312Packages.mkdocs-material
            pkgs.pre-commit
            pkgs.ruff
            python
            rhc
          ];

          env = {
            RHC_STATE_DIR = ".rhc-state";
          };
        };
      }
    );
}
