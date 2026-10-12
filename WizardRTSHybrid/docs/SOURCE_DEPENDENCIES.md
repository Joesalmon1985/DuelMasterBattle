# Source dependencies

Pinned commits are in `sources/manifest.json`. Clones are gitignored under `external/`.

| Lab | Needs | Present on this machine |
| --- | --- | --- |
| OpenRA bleed | .NET 10 SDK, PowerShell | .NET SDK 10.0.401 installed with winget. `dotnet build OpenRA.slnx` succeeded. |
| OpenRA Mod SDK | .NET SDK, network fetch of the engine zip named in `mod.config` | .NET SDK present. The fetch is the SDK's own step, not a hybrid runtime download. |
| Widelands | CMake, a C++ compiler (MSVC, GCC, or Clang), and the libraries in the upstream compiling guide | CMake was installed for the configure attempt. No MSVC, GCC, or Clang was on PATH, and `vswhere` was absent. Configure cannot finish without a compiler. |

Hybrid runtime dependencies, which are not the labs:

- Python 3. `py -3` is 3.14 on this machine. The repo `.venv` interpreter is blocked by Windows Application Control.
- Godot 4.5.1 for presentation. Headed screenshots need Forward+.
- The existing `sim/dmb` package. The hybrid does not reimplement the duel lease.

The packaged game must not download these labs and must not open `external/`.
