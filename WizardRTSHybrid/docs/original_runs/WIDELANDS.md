# Widelands source run

Pin: master `47c5cae8c6cb080e4bf86163a3873bd0847bc0e4`.

| | |
| --- | --- |
| Command | `"C:\Program Files\CMake\bin\cmake.exe" -S . -B build` |
| CMake | 4.4.4, installed with `winget install Kitware.CMake` because `cmake` was not on PATH |
| Compiler | Not installed. `cl`, `gcc`, and `clang` were absent. `vswhere.exe` was absent. |
| Result | Configure failed. Log: `docs/original_runs/logs/widelands_cmake.txt` (gitignored). |

Exact error:

```
-- Building for: NMake Makefiles
CMake Error at CMakeLists.txt:3 (project):
  Running 'nmake' '-?' failed with: no such file or directory
CMake Error: CMAKE_C_COMPILER not set, after EnableLanguage
CMake Error: CMAKE_CXX_COMPILER not set, after EnableLanguage
-- Configuring incomplete, errors occurred!
```

No Widelands binary was produced. No prebuilt binary was substituted. Roads, carriers, and stock changes were not observed in a Widelands window. The warehouse functions used by the hybrid were read from source and ported. See blocker B1. This is an environment gap, not an engine incompatibility.

Repairs used: confirm the compiler is missing, install CMake, rerun configure. A fourth repair (installing Visual Studio Build Tools or MSYS2) is the next step and was not started.
