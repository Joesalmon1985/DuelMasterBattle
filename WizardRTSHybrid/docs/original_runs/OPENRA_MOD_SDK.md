# OpenRA Mod SDK

Pin: master `df103939c7e472e715b9fce7cbaf7e35b54dc037`.

`mod.config` sets `ENGINE_VERSION` to `release-20250330` and `MOD_ID` to `example`. `make.cmd all` downloads that engine into the SDK tree and builds the example mod. The extension path is data and assemblies on top of the engine, not a fork.

First attempt: `make.cmd all` downloaded the engine, then failed because `cmd.exe` could not see `dotnet` (the SDK had been installed in the same session and was not on that process PATH):

```
The 'dotnet' tool is required to compile OpenRA.
```

Repair: rerun `make.cmd all` with `C:\Program Files\dotnet` on `PATH`.

Result: the engine and `OpenRA.Mods.Example` built. 0 errors. `OpenRA.Mods.Example.dll` is under `external/openra-mod-sdk/engine/bin/`. `launch-game.cmd` looks for `bin\OpenRA.exe` inside the fetched engine. The .NET 10 build emits `OpenRA.dll`, so that launcher does not start the example mod on this SDK pin. The extension path is still the one `make.ps1` uses: fetch the engine named in `mod.config`, then `dotnet build` the mod project `OpenRA.Mods.Example`.
