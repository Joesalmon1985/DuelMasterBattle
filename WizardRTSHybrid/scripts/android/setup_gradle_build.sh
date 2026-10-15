#!/usr/bin/env bash
# Install Godot's Android gradle build template into godot_project/android/build and apply the DuelMasterBattle overlay:
# the Chaquopy Python plugin (CPython inside the app), the DmbPySim Godot plugin (Kotlin), the staged Python sources.
# Idempotent: run again after changing the overlay or the Python sources.
#   scripts/android/setup_gradle_build.sh            # uses ~/.local/share/godot/export_templates/<GODOT_VERSION>/android_source.zip
#   GODOT_VERSION=4.5.1.stable  CHAQUOPY_VERSION=17.1.0  PYTHON_VERSION=3.12  (defaults)
set -euo pipefail
HYB="$(cd "$(dirname "$0")/../.." && pwd)"
REPO="$(dirname "$HYB")"
GODOT_VERSION="${GODOT_VERSION:-4.5.1.stable}"
CHAQUOPY_VERSION="${CHAQUOPY_VERSION:-17.1.0}"
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
TEMPLATES="${GODOT_TEMPLATES:-$HOME/.local/share/godot/export_templates/$GODOT_VERSION}"
BUILD="$REPO/godot_project/android/build"
OVERLAY="$HYB/scripts/android/overlay"
[ -f "$TEMPLATES/android_source.zip" ] || { echo "missing $TEMPLATES/android_source.zip (install the Godot $GODOT_VERSION export templates)" >&2; exit 1; }

ANDROID_DIR="$REPO/godot_project/android"
mkdir -p "$ANDROID_DIR"
# Godot 4.5 keeps the template's version id in android/.build_version (the parent of the build dir) and ignores the build dir
# for the editor's resource scan with android/build/.gdignore (editor/export/export_template_manager.cpp).
if [ ! -f "$ANDROID_DIR/.build_version" ] || [ "$(cat "$ANDROID_DIR/.build_version")" != "$GODOT_VERSION" ] || [ ! -f "$BUILD/build.gradle" ]; then
  rm -rf "$BUILD"
  mkdir -p "$BUILD"
  (cd "$BUILD" && unzip -q -o "$TEMPLATES/android_source.zip")
  echo "$GODOT_VERSION" > "$ANDROID_DIR/.build_version"
  echo "installed gradle template $GODOT_VERSION"
fi
rm -f "$BUILD/.build_version" "$ANDROID_DIR/.gdignore"
printf '\n' > "$BUILD/.gdignore"
printf '%s\n' 'build/' 'plugins/' '*.apk' '*.aab' '.build_version' > "$ANDROID_DIR/.gitignore"

# ---- overlay: Chaquopy + the plugin class, applied with python so the edits are exact and repeatable
python3 - "$BUILD" "$CHAQUOPY_VERSION" "$PYTHON_VERSION" "$OVERLAY" <<'EOF'
import re, shutil, sys
from pathlib import Path
build, chaq, pyver, overlay = Path(sys.argv[1]), sys.argv[2], sys.argv[3], Path(sys.argv[4])

settings = build / "settings.gradle"
s = settings.read_text()
if "com.chaquo.python" not in s:
    s = s.replace("        id 'org.jetbrains.kotlin.android' version versions.kotlinVersion\n",
                  "        id 'org.jetbrains.kotlin.android' version versions.kotlinVersion\n        id 'com.chaquo.python' version '%s'\n" % chaq)
    settings.write_text(s)

gradle = build / "build.gradle"
g = gradle.read_text()
if "com.chaquo.python" not in g:
    g = g.replace("    id 'org.jetbrains.kotlin.android'\n}", "    id 'org.jetbrains.kotlin.android'\n    id 'com.chaquo.python'  // DuelMasterBattle: CPython in the app (the LAN host)\n}", 1)
    g += '''

// DuelMasterBattle: the authoritative Python world runs inside the app (wizard_rts/net/android_entry.py via Chaquopy).
chaquopy {
    defaultConfig {
        version "%s"
        buildPython "python3"
    }
    sourceSets {
        main {
            srcDir "python_src"
        }
    }
}
''' % pyver
    gradle.write_text(g)

# the template pins an NDK the SDK may not have; AGP only needs *an* NDK (to strip the prebuilt Godot libraries)
cfg = build / "config.gradle"
c = cfg.read_text()
import os
sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT") or str(Path.home() / "Android")
ndks = sorted(p.name for p in (Path(sdk) / "ndk").glob("*")) if (Path(sdk) / "ndk").is_dir() else []
m = re.search(r"ndkVersion\s*:\s*'([^']+)'", c)
if m and ndks and m.group(1) not in ndks:
    c = c.replace(m.group(0), "ndkVersion         : '%s'" % ndks[-1])
    cfg.write_text(c)
    print("config.gradle: using installed NDK %s instead of %s" % (ndks[-1], m.group(1)))

# the plugin class and its registration through the host activity (no manifest edits: Godot regenerates the manifest)
dst = build / "src" / "com" / "duelmasterbattle" / "pysim"
dst.mkdir(parents=True, exist_ok=True)
shutil.copy2(overlay / "PySimPlugin.kt", dst / "PySimPlugin.kt")
app = build / "src" / "com" / "godot" / "game" / "GodotApp.java"
a = app.read_text()
if "PySimPlugin" not in a:
    a = a.replace("import org.godotengine.godot.GodotActivity;\n", "import org.godotengine.godot.GodotActivity;\nimport org.godotengine.godot.plugin.GodotPlugin;\nimport com.duelmasterbattle.pysim.PySimPlugin;\nimport java.util.HashSet;\nimport java.util.Set;\n", 1)
    marker = "public class GodotApp extends GodotActivity {\n"
    a = a.replace(marker, marker + '''	/** DuelMasterBattle: the Python host plugin, registered by the host activity (Godot 4.2+ GodotHost API). */
	@Override
	public Set<GodotPlugin> getHostPlugins(Godot engine) {
		Set<GodotPlugin> plugins = new HashSet<>(super.getHostPlugins(engine));
		plugins.add(new PySimPlugin(engine));
		return plugins;
	}

''', 1)
    app.write_text(a)
print("overlay applied")
EOF

python3 "$HYB/scripts/android/stage_python.py" --out "$BUILD/python_src"
echo "ANDROID_GRADLE_READY $BUILD"
