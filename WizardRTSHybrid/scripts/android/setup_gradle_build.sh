#!/usr/bin/env bash
# Install Godot's Android gradle build template into godot_project/android/build and apply the DuelMasterBattle overlay
# (Chaquopy CPython, the DmbPySim plugin, the staged Python sources). Thin wrapper around setup_gradle_build.py, which is
# the cross-platform implementation (Windows uses scripts/android/build_apk.ps1, which calls the Python directly).
#   scripts/android/setup_gradle_build.sh            # uses ~/.local/share/godot/export_templates/<GODOT_VERSION>/android_source.zip
#   GODOT_VERSION=4.5.1.stable  CHAQUOPY_VERSION=17.1.0  PYTHON_VERSION=<this python's major.minor>  BUILD_PYTHON=python3
set -euo pipefail
HYB="$(cd "$(dirname "$0")/../.." && pwd)"
PY="${BUILD_PYTHON:-python3}"
exec "$PY" "$HYB/scripts/android/setup_gradle_build.py" --build-python "$(command -v "$PY")" "$@"
