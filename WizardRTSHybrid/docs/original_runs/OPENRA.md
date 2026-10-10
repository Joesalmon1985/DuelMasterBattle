# OpenRA source run

Pin: bleed `e7e9e4ad270221d7fb9725b348c75504d48c1ebd`.

| | |
| --- | --- |
| Command | `dotnet build OpenRA.slnx -c Debug` |
| SDK | .NET SDK 10.0.401, installed with `winget install Microsoft.DotNet.SDK.10` because `dotnet` was not on PATH |
| Result | Build succeeded. 0 warnings, 0 errors. About 54 seconds. Output under `external/openra/bin/`. |
| Tests | `dotnet test OpenRA.Test\OpenRA.Test.csproj -c Debug` — Passed 508, skipped 2, failed 0. Includes `OrderTest` and `CoordinateTest`. |
| Launch | `dotnet bin\OpenRA.dll -- Engine.EngineDir=".." Game.Mod=ra` from `external/openra`. The process printed Windows x64, .NET CLR 10.0.12, SDL 2.32.10, OpenGL on the NVIDIA GeForce RTX 3060, desktop 1920x1080, and `Loading mod: ra`. It was stopped after that line. A skirmish was not played, and no OpenRA screenshot was saved. |

This is a source build. No prebuilt OpenRA binary was used.
