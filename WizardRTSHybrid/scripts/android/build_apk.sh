#!/usr/bin/env bash
# Build the Android debug APK (host-capable: Godot client + CPython world via Chaquopy) with a headless Godot gradle export.
#   scripts/android/build_apk.sh [debug|release]      output: build/android/DuelMasterBattle-<kind>.apk (repo root, gitignored)
# Needs: Godot 4.5.1 editor (GODOT), its Android export templates, Android SDK (ANDROID_HOME), JDK 17, python3.12 on PATH,
# internet for the first gradle run (Gradle, AGP, Chaquopy and the Android CPython runtime are downloaded once).
set -euo pipefail
HYB="$(cd "$(dirname "$0")/../.." && pwd)"
REPO="$(dirname "$HYB")"
GODOT="${GODOT:-$HOME/godot451/Godot_v4.5.1-stable_linux.x86_64}"
KIND="${1:-debug}"
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Android}"
export JAVA_HOME="${JAVA_HOME:-/usr/lib/jvm/java-17-openjdk-amd64}"
export PATH="$JAVA_HOME/bin:$PATH"
"$HYB/scripts/android/setup_gradle_build.sh"
mkdir -p "$REPO/build/android"
OUT="$REPO/build/android/DuelMasterBattle-$KIND.apk"
rm -f "$OUT"
LOG="$REPO/build/android/export-$KIND.log"
echo "exporting with $GODOT (log: $LOG)"
set +e
timeout "${TIMEOUT:-3600}" "$GODOT" --headless --path "$REPO/godot_project" --export-$KIND "Android" "$OUT" > "$LOG" 2>&1
code=$?
set -e
grep -E "error|Error|FAIL|BUILD|warning: unused" "$LOG" | grep -v "^$" | tail -30 || true
if [ -f "$OUT" ]; then
  ls -la "$OUT"
  python3 - "$OUT" <<'EOF'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1])
names = z.namelist()
py = [n for n in names if n.startswith("assets/chaquopy/")]
libs = [n for n in names if n.startswith("lib/")]
print("APK entries:", len(names), "chaquopy assets:", len(py), "native libs:", len(libs))
print("python runtime:", [n for n in libs if "python" in n][:4])
print("godot:", [n for n in libs if "godot" in n][:2])
print("has wizard_rts:", any("app.imy" in n or "requirements" in n for n in py) or "assets/chaquopy/app.imy" in names)
EOF
  echo "ANDROID_APK_OK $OUT"
  exit 0
fi
echo "ANDROID_APK_FAILED exit=$code (see $LOG)"
tail -40 "$LOG"
exit 1
