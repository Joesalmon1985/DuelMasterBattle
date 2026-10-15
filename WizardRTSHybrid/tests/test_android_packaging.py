"""The Android packaging steps that can be checked without an Android SDK: the gradle template install and the Chaquopy /
DmbPySim overlay (on a synthetic template shaped like Godot 4.5's android_source.zip), their idempotency, the Python
version rule, and the export presets a phone install needs (signed APKs, a host-capable and a client-only preset)."""

from __future__ import annotations

import configparser
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

HYB = Path(__file__).resolve().parents[1]
ROOT = HYB.parent
SCRIPT = HYB / "scripts" / "android" / "setup_gradle_build.py"
sys.path.insert(0, str(HYB / "scripts" / "android"))

import setup_gradle_build as sgb  # noqa: E402

SETTINGS = "pluginManagement {\n    plugins {\n        id 'com.android.application' version versions.androidGradlePlugin\n        id 'org.jetbrains.kotlin.android' version versions.kotlinVersion\n    }\n}\n"
BUILD = "plugins {\n    id 'com.android.application'\n    id 'org.jetbrains.kotlin.android'\n}\n\nandroid {\n    defaultConfig {\n    }\n}\n"
CONFIG = (
    "ext.versions = [\n    ndkVersion         : '28.1.13356709',\n]\n"
    "ext.getExportEnabledABIs = { ->\n    if (enabledABIs == null || enabledABIs.isEmpty()) {\n"
    '        enabledABIs = "armeabi-v7a|arm64-v8a|x86|x86_64|"\n    }\n}\n'
)
APP = "package com.godot.game;\n\nimport org.godotengine.godot.GodotActivity;\n\npublic class GodotApp extends GodotActivity {\n}\n"


def make_template(tmp_path: Path) -> Path:
    templates = tmp_path / "templates"
    templates.mkdir()
    with zipfile.ZipFile(templates / "android_source.zip", "w") as z:
        z.writestr("settings.gradle", SETTINGS)
        z.writestr("build.gradle", BUILD)
        z.writestr("config.gradle", CONFIG)
        z.writestr("gradle.properties", "org.gradle.jvmargs=-Xmx4536m\norg.gradle.warning.mode=all\n")
        z.writestr("src/com/godot/game/GodotApp.java", APP)
        z.writestr("libs/debug/godot-lib.template_debug.aar", "stub")
    return templates


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, cwd=str(HYB))


def test_template_install_and_overlay_are_idempotent(tmp_path: Path) -> None:
    templates = make_template(tmp_path)
    project = tmp_path / "godot_project"
    project.mkdir()
    sdk = tmp_path / "sdk"
    (sdk / "ndk" / "27.0.12077973").mkdir(parents=True)
    version = "%d.%d" % sys.version_info[:2]
    if version not in sgb.SUPPORTED_PYTHON:
        pytest.skip("the running Python is outside Chaquopy's range")
    args = ["--templates", str(templates), "--sdk", str(sdk), "--project", str(project), "--no-stage", "--python-version", version]
    r = run(args)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ANDROID_GRADLE_READY" in r.stdout
    build = project / "android" / "build"
    assert (project / "android" / ".build_version").read_text(encoding="utf-8").strip() == "4.5.1.stable"
    assert (build / ".gdignore").is_file() and not (project / "android" / ".gdignore").exists()
    assert "build/" in (project / "android" / ".gitignore").read_text(encoding="utf-8")
    settings = (build / "settings.gradle").read_text(encoding="utf-8")
    gradle = (build / "build.gradle").read_text(encoding="utf-8")
    cfg_text = (build / "config.gradle").read_text(encoding="utf-8")
    app = (build / "src" / "com" / "godot" / "game" / "GodotApp.java").read_text(encoding="utf-8")
    assert settings.count("com.chaquo.python") == 1 and "17.1.0" in settings
    assert gradle.count("id 'com.chaquo.python'") == 1 and gradle.count("chaquopy {") == 1
    assert ('version "%s"' % version) in gradle
    assert 'buildPython "' in gradle and "\\" not in gradle.split('buildPython "', 1)[1].split('"', 1)[0]
    assert 'srcDir "python_src"' in gradle
    assert "ndkVersion         : '27.0.12077973'" in cfg_text
    # Godot's copy-and-rename gradle call passes no ABI list; the template default must not include the 32-bit ABIs
    # (Chaquopy: "Python is not available for the ABI 'armeabi-v7a'")
    assert 'enabledABIs = "arm64-v8a|x86_64|"' in cfg_text and "armeabi-v7a|arm64-v8a" not in cfg_text
    props = (build / "gradle.properties").read_text(encoding="utf-8")
    assert props.count("org.gradle.daemon=false") == 1 and props.startswith("org.gradle.jvmargs"), "a lingering gradle daemon holds the export's output pipe"
    assert app.count("public Set<GodotPlugin> getHostPlugins") == 1 and "import com.duelmasterbattle.pysim.PySimPlugin;" in app
    assert (build / "src" / "com" / "duelmasterbattle" / "pysim" / "PySimPlugin.kt").read_text(encoding="utf-8") == (HYB / "scripts" / "android" / "overlay" / "PySimPlugin.kt").read_text(encoding="utf-8")
    # second run: same template version, nothing duplicated, the template is not re-extracted
    marker = build / "python_src_marker"
    marker.write_text("keep", encoding="utf-8")
    r = run(args)
    assert r.returncode == 0, r.stdout + r.stderr
    assert marker.is_file(), "an unchanged template must not be re-extracted"
    assert (build / "settings.gradle").read_text(encoding="utf-8") == settings
    assert (build / "build.gradle").read_text(encoding="utf-8") == gradle
    assert (build / "config.gradle").read_text(encoding="utf-8") == cfg_text
    assert (build / "gradle.properties").read_text(encoding="utf-8") == props
    assert (build / "src" / "com" / "godot" / "game" / "GodotApp.java").read_text(encoding="utf-8") == app
    # a different Godot version re-extracts
    r = run(args + ["--godot-version", "4.6.0.stable"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert not marker.exists()
    assert (project / "android" / ".build_version").read_text(encoding="utf-8").strip() == "4.6.0.stable"


def test_build_python_must_match_the_target_version(tmp_path: Path) -> None:
    templates = make_template(tmp_path)
    project = tmp_path / "godot_project"
    project.mkdir()
    other = next(v for v in sgb.SUPPORTED_PYTHON if v != "%d.%d" % sys.version_info[:2])
    r = run(["--templates", str(templates), "--sdk", str(tmp_path), "--project", str(project), "--no-stage", "--python-version", other])
    assert r.returncode != 0
    assert "same major.minor" in r.stdout + r.stderr
    assert not (project / "android" / "build").exists()


def test_missing_template_is_a_clear_error(tmp_path: Path) -> None:
    project = tmp_path / "godot_project"
    project.mkdir()
    r = run(["--templates", str(tmp_path / "nowhere"), "--sdk", str(tmp_path), "--project", str(project), "--no-stage"])
    assert r.returncode != 0
    assert "android_source.zip" in r.stdout + r.stderr


def test_python_version_default_follows_the_running_interpreter() -> None:
    v = sgb.running_python_version()
    assert v in sgb.SUPPORTED_PYTHON
    if "%d.%d" % sys.version_info[:2] in sgb.SUPPORTED_PYTHON:
        assert v == "%d.%d" % sys.version_info[:2]
    assert sgb.gradle_string(r"C:\Users\me\python.exe") == "C:/Users/me/python.exe"


def test_export_presets_for_phones() -> None:
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(ROOT / "godot_project" / "export_presets.cfg", encoding="utf-8")
    presets = {cfg[s]["name"].strip('"'): s for s in cfg.sections() if not s.endswith(".options") and "name" in cfg[s]}
    assert "Android" in presets and "Android Client" in presets
    host = cfg[presets["Android"] + ".options"]
    client = cfg[presets["Android Client"] + ".options"]
    for opts in (host, client):
        assert opts["package/signed"] == "true", "an unsigned APK cannot be installed on a phone"
        assert opts["architectures/arm64-v8a"] == "true"
        assert opts["permissions/internet"] == "true" and opts["permissions/access_wifi_state"] == "true"
        assert opts["package/unique_name"] == '"com.duelmasterbattle.game"'
    assert host["gradle_build/use_gradle_build"] == "true", "the host-capable APK needs the gradle build (Chaquopy)"
    assert client["gradle_build/use_gradle_build"] == "false"
    assert cfg[presets["Android"]]["export_path"] == '"build/android/DuelMasterBattle-debug.apk"'
    assert cfg[presets["Android Client"]]["export_path"] == '"build/android/DuelMasterBattle-client.apk"'
    # the app version the phones compare in `hello`
    from wizard_rts.net import protocol

    assert host["version/name"].strip('"') == protocol.GAME_VERSION
