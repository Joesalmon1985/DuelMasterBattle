#!/usr/bin/env python3
"""Install Godot's Android gradle build template into godot_project/android/build and apply the DuelMasterBattle overlay:
the Chaquopy Python plugin (CPython inside the app, so a phone can host the world), the DmbPySim Godot plugin (Kotlin,
registered through the host activity) and the staged Python sources. Works on Windows, Linux and macOS; idempotent
(run again after changing the overlay or the Python sources).

    python3 scripts/android/setup_gradle_build.py [--templates DIR] [--sdk DIR] [--python-version 3.14] [--build-python EXE]

Defaults: the templates directory is Godot's own for this platform and version (``%APPDATA%/Godot/export_templates/4.5.1.stable``
on Windows, ``~/.local/share/godot/export_templates/4.5.1.stable`` on Linux); the Android SDK is ``ANDROID_HOME`` /
``ANDROID_SDK_ROOT`` or the platform default; the Python version packaged into the APK is the version of the interpreter
running this script (Chaquopy requires the build machine's Python to have the same major.minor as the app's), and the build
Python is that interpreter. Environment overrides: GODOT_VERSION, CHAQUOPY_VERSION, PYTHON_VERSION, GODOT_TEMPLATES.
Prints ``ANDROID_GRADLE_READY <build dir>`` on success."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

HYB = Path(__file__).resolve().parents[2]
ROOT = HYB.parent
OVERLAY = HYB / "scripts" / "android" / "overlay"
SUPPORTED_PYTHON = ("3.11", "3.12", "3.13", "3.14", "3.15")  # Chaquopy 17.1 targets
DEFAULT_PYTHON = "3.12"


def default_templates_dir(godot_version: str) -> Path:
    env = os.environ.get("GODOT_TEMPLATES")
    if env:
        return Path(env)
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "Godot"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "Godot"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "godot"
    return base / "export_templates" / godot_version


def default_sdk_dir() -> Path:
    for key in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if os.environ.get(key):
            return Path(os.environ[key])
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Android" / "Sdk"
    return Path.home() / "Android"


def running_python_version() -> str:
    v = "%d.%d" % (sys.version_info.major, sys.version_info.minor)
    return v if v in SUPPORTED_PYTHON else DEFAULT_PYTHON


def gradle_string(path: str | Path) -> str:
    """A path as a Groovy double-quoted string body (forward slashes work on every platform)."""
    return str(path).replace("\\", "/").replace('"', '\\"')


def install_template(templates: Path, godot_version: str, android_dir: Path, build: Path, log=print) -> bool:
    """Unpack android_source.zip into the build dir unless the installed template already has this version. Returns True if installed."""
    src = templates / "android_source.zip"
    if not src.is_file():
        sys.exit(f"missing {src} (install the Godot {godot_version} export templates; on Windows run 'Setup Android Build Tools.bat')")
    version_file = android_dir / ".build_version"
    android_dir.mkdir(parents=True, exist_ok=True)
    installed = False
    if not version_file.is_file() or version_file.read_text(encoding="utf-8").strip() != godot_version or not (build / "build.gradle").is_file():
        if build.exists():
            shutil.rmtree(build)
        build.mkdir(parents=True)
        with zipfile.ZipFile(src) as z:
            z.extractall(build)
        version_file.write_text(godot_version + "\n", encoding="utf-8")
        log(f"installed gradle template {godot_version}")
        installed = True
    # Godot 4.5 keeps the template's version id in android/.build_version (the parent of the build dir) and ignores the build
    # dir for the editor's resource scan with android/build/.gdignore (editor/export/export_template_manager.cpp)
    for stale in (build / ".build_version", android_dir / ".gdignore"):
        if stale.exists():
            stale.unlink()
    (build / ".gdignore").write_text("\n", encoding="utf-8")
    (android_dir / ".gitignore").write_text("build/\nplugins/\n*.apk\n*.aab\n.build_version\n", encoding="utf-8")
    return installed


def apply_overlay(build: Path, chaquopy_version: str, python_version: str, build_python: str | None, sdk: Path, overlay: Path = OVERLAY, log=print) -> None:
    settings = build / "settings.gradle"
    s = settings.read_text(encoding="utf-8")
    if "com.chaquo.python" not in s:
        anchor = "        id 'org.jetbrains.kotlin.android' version versions.kotlinVersion\n"
        if anchor not in s:
            sys.exit(f"unexpected settings.gradle (no kotlin plugin line) in {settings}")
        s = s.replace(anchor, anchor + "        id 'com.chaquo.python' version '%s'\n" % chaquopy_version, 1)
        settings.write_text(s, encoding="utf-8")

    gradle = build / "build.gradle"
    g = gradle.read_text(encoding="utf-8")
    if "com.chaquo.python" not in g:
        anchor = "    id 'org.jetbrains.kotlin.android'\n}"
        if anchor not in g:
            sys.exit(f"unexpected build.gradle (no kotlin plugin block) in {gradle}")
        g = g.replace(anchor, "    id 'org.jetbrains.kotlin.android'\n    id 'com.chaquo.python'  // DuelMasterBattle: CPython in the app (the LAN host)\n}", 1)
        build_python_line = ('        buildPython "%s"\n' % gradle_string(build_python)) if build_python else ""
        g += '''

// DuelMasterBattle: the authoritative Python world runs inside the app (wizard_rts/net/android_entry.py via Chaquopy).
chaquopy {
    defaultConfig {
        version "%s"
%s    }
    sourceSets {
        main {
            srcDir "python_src"
        }
    }
}
''' % (python_version, build_python_line)
        gradle.write_text(g, encoding="utf-8")

    # the template pins an NDK the SDK may not have; AGP only needs *an* NDK (to strip the prebuilt Godot libraries)
    cfg = build / "config.gradle"
    if cfg.is_file():
        c = cfg.read_text(encoding="utf-8")
        ndks = sorted(p.name for p in (sdk / "ndk").glob("*") if p.is_dir()) if (sdk / "ndk").is_dir() else []
        m = re.search(r"ndkVersion\s*:\s*'([^']+)'", c)
        if m and ndks and m.group(1) not in ndks:
            c = c.replace(m.group(0), "ndkVersion         : '%s'" % ndks[-1])
            cfg.write_text(c, encoding="utf-8")
            log("config.gradle: using installed NDK %s instead of %s" % (ndks[-1], m.group(1)))

    # the plugin class and its registration through the host activity (no manifest edits: Godot regenerates the manifest)
    dst = build / "src" / "com" / "duelmasterbattle" / "pysim"
    dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(overlay / "PySimPlugin.kt", dst / "PySimPlugin.kt")
    app = build / "src" / "com" / "godot" / "game" / "GodotApp.java"
    a = app.read_text(encoding="utf-8")
    if "PySimPlugin" not in a:
        imp = "import org.godotengine.godot.GodotActivity;\n"
        marker = "public class GodotApp extends GodotActivity {\n"
        if imp not in a or marker not in a:
            sys.exit(f"unexpected GodotApp.java in {app}")
        a = a.replace(imp, imp + "import org.godotengine.godot.plugin.GodotPlugin;\nimport com.duelmasterbattle.pysim.PySimPlugin;\nimport java.util.HashSet;\nimport java.util.Set;\n", 1)
        a = a.replace(marker, marker + '''	/** DuelMasterBattle: the Python host plugin, registered by the host activity (Godot 4.2+ GodotHost API). */
	@Override
	public Set<GodotPlugin> getHostPlugins(Godot engine) {
		Set<GodotPlugin> plugins = new HashSet<>(super.getHostPlugins(engine));
		plugins.add(new PySimPlugin(engine));
		return plugins;
	}

''', 1)
        app.write_text(a, encoding="utf-8")
    log("overlay applied")


def stage(build: Path, build_python: str) -> None:
    subprocess.run([build_python, str(HYB / "scripts" / "android" / "stage_python.py"), "--out", str(build / "python_src")], check=True)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--godot-version", default=os.environ.get("GODOT_VERSION", "4.5.1.stable"))
    ap.add_argument("--chaquopy-version", default=os.environ.get("CHAQUOPY_VERSION", "17.1.0"))
    ap.add_argument("--python-version", default=os.environ.get("PYTHON_VERSION", running_python_version()), choices=SUPPORTED_PYTHON,
                    help="the CPython packaged into the APK; must equal the build Python's major.minor (Chaquopy rule)")
    ap.add_argument("--build-python", default=sys.executable, help="the interpreter gradle runs for the Python packaging step (default: this one)")
    ap.add_argument("--templates", default=None, help="directory holding android_source.zip (default: Godot's export_templates/<version>)")
    ap.add_argument("--sdk", default=None, help="Android SDK root (default: ANDROID_HOME, ANDROID_SDK_ROOT or the platform default)")
    ap.add_argument("--project", default=str(ROOT / "godot_project"), help="the Godot project (default: the repository's)")
    ap.add_argument("--no-stage", action="store_true", help="skip staging the Python sources (tests)")
    args = ap.parse_args(argv)

    templates = Path(args.templates) if args.templates else default_templates_dir(args.godot_version)
    sdk = Path(args.sdk) if args.sdk else default_sdk_dir()
    android_dir = Path(args.project) / "android"
    build = android_dir / "build"
    bp = Path(args.build_python)
    probe = subprocess.run([str(bp), "-c", "import sys; print('%d.%d' % sys.version_info[:2])"], capture_output=True, text=True)
    if probe.returncode != 0 or probe.stdout.strip() != args.python_version:
        sys.exit(f"the build Python {bp} is {probe.stdout.strip() or 'not runnable'} but the APK targets Python {args.python_version}; "
                 f"Chaquopy needs the same major.minor (pass --build-python / --python-version)")
    install_template(templates, args.godot_version, android_dir, build)
    apply_overlay(build, args.chaquopy_version, args.python_version, str(bp), sdk)
    if not args.no_stage:
        stage(build, str(bp))
    print(f"python {args.python_version} via {bp}; sdk {sdk}; templates {templates}")
    print(f"ANDROID_GRADLE_READY {build}")


if __name__ == "__main__":
    main()
