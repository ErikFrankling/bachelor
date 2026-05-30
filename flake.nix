{
  description = "kex";

  inputs = {
    # nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
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
        pkgs = import nixpkgs { inherit system; };

        pyPkgs =
          pythonPackages: with pythonPackages; [
            pandas
            matplotlib
            lxml
          ];
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            sumo
            (python3.withPackages pyPkgs)
          ];

          shellHook = ''
            export SUMO_HOME="${pkgs.sumo}/share/sumo"
          '';
        };
      }
    );
}
