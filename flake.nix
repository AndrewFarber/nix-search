{
  description = "nix-search – TUI for searching Nix packages";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python314;

        nix-search = python.pkgs.buildPythonApplication {
          pname = "nix-search";
          version = "0.0.1";
          pyproject = true;
          src = ./.;
          build-system = [ python.pkgs.setuptools ];
          dependencies = [
            python.pkgs.pydantic
            python.pkgs.pydantic-settings
            python.pkgs.textual
          ];

          nativeCheckInputs = [
            python.pkgs.pytest
            python.pkgs.pytest-asyncio
            python.pkgs.pytest-cov
          ];

          checkPhase = ''
            runHook preCheck
            pytest src/tests/ -v
            runHook postCheck
          '';

          meta = {
            description = "TUI for searching Nix packages";
            mainProgram = "nix-search";
          };
        };
      in
      {
        packages = {
          default = nix-search;
          nix-search = nix-search;
        };

        devShells.default = pkgs.mkShell {
          packages = [
            (python.withPackages (ps: [
              ps.pydantic
              ps.pydantic-settings
              ps.textual
              ps.pytest
              ps.pytest-asyncio
              ps.pytest-cov
              ps.ruff
            ]))
            pkgs.just
            pkgs.brotli
          ];
        };
      }
    );
}
