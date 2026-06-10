{
  description = "Home Assistant custom component dev env (with uv)";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
  };

  outputs = { nixpkgs, ... }: let
    lib = nixpkgs.lib;

    forAllSystems = f: lib.genAttrs lib.systems.flakeExposed (system: f {
      inherit system;
      pkgs = nixpkgs.legacyPackages.${system};
    });
  in {
    devShells = forAllSystems ({ system, pkgs }: {
      default = (pkgs.mkShell {
        name = "ha-custom-component-${system}";

        packages = with pkgs; [
          # Integration dev
          python314
          uv
          just
          pyright

          # APK download / decompile toolchain
          # (the only tools tools/apk/switchbot-apk.sh invokes)
          apkeep  # download APKs
          unzip   # unpack XAPK / extract DEX
          jq      # read version from manifest
          jadx    # decompile DEX -> Java
        ];
      });
    });
  };
}
