"""Imported art on the phone: the audit that fails when an existing imported asset would not be in the package, the guard that keeps run-time image loading
export-safe, and the player-facing menu rules that can be checked without Godot.

A Godot export does not ship source PNGs (it ships imported `.ctex` textures behind a `<name>.png.import` remap), so `Image.load("res://x.png")` worked on the PC and
drew nothing on the phones. The client now loads through `client/scripts/asset_loader.gd`; these tests keep that true."""

from __future__ import annotations

import configparser
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

HYB = Path(__file__).resolve().parents[1]
ROOT = HYB.parent
PROJECT = ROOT / "godot_project"
sys.path.insert(0, str(HYB / "scripts" / "android"))

import asset_audit  # noqa: E402
import inspect_apk  # noqa: E402


# ------------------------------------------------------------------ the repository holds every file the client will ask for

def test_every_catalogued_and_literal_asset_exists_in_the_repository():
    problems, stats = asset_audit.audit(None)
    assert problems == [], problems[:10]
    assert stats["catalogue_items"] > 2500 and stats["catalogue_files"] > 4000, stats


def test_the_audit_enumerates_what_hybrid_art_registers():
    cat = asset_audit.catalogue_paths()
    # a sheet, a 32-facing unit with layers, an OpenRA building with states: each contributes the files the GDScript loads
    assert cat["widelands.meadow1"] and all(p.startswith("res://") for p in cat["widelands.meadow1"])
    data = json.loads(asset_audit.CATALOGUE.read_text(encoding="utf-8"))
    layered = next(i for i in data["items"] if i.get("layers"))
    assert len(cat[layered["id"]]) >= 2 * int(layered["layers"].get("facings", 32))
    staged = next(i for i in data["items"] if i.get("states"))
    for state in staged["states"].values():
        assert set(state["files"]) <= cat[staged["id"]]
    assert data.get("missing_required") in ([], None), "the catalogue itself reports art that never had an image: %s" % data.get("missing_required")


# ------------------------------------------------------------------ what the package must hold for each kind of file

def fake_apk(entries: dict[str, bytes]) -> tuple[set[str], dict[str, bytes]]:
    names = set(entries)
    return names, {n: b for n, b in entries.items() if n.endswith(".import")}


REMAP = b'[remap]\n\nimporter="texture"\ntype="CompressedTexture2D"\npath="res://.godot/imported/a.png-123.ctex"\n'


def test_a_png_needs_its_import_remap_and_imported_texture_in_the_package():
    path = "res://client/hybrid/art/openra/a.png"
    names, imports = fake_apk({"assets/client/hybrid/art/openra/a.png": b"png"})  # only the source file: not loadable in an export
    assert asset_audit.in_apk(path, names, imports) is not None
    names, imports = fake_apk({"assets/client/hybrid/art/openra/a.png.import": REMAP})  # remap without the texture it names
    assert "not in the package" in asset_audit.in_apk(path, names, imports)
    names, imports = fake_apk({"assets/client/hybrid/art/openra/a.png.import": REMAP, "assets/.godot/imported/a.png-123.ctex": b"x"})
    assert asset_audit.in_apk(path, names, imports) is None


def test_data_files_and_scenes_must_travel_as_files():
    names, imports = fake_apk({"assets/client/hybrid/art/catalogue.json": b"{}", "assets/client/scenes/main_menu.tscn.remap": b"x"})
    assert asset_audit.in_apk("res://client/hybrid/art/catalogue.json", names, imports) is None
    assert asset_audit.in_apk("res://client/scenes/main_menu.tscn", names, imports) is None
    assert asset_audit.in_apk("res://client/scenes/missing.tscn", names, imports) is not None
    assert "data file" in asset_audit.in_apk("res://client/hybrid/art/other.json", names, imports)


def test_the_audit_fails_an_apk_that_lacks_imported_art(tmp_path: Path):
    cat = asset_audit.catalogue_paths()
    some = sorted({p for paths in cat.values() for p in paths})[:5]
    apk = tmp_path / "bare.apk"
    with zipfile.ZipFile(apk, "w") as z:
        z.writestr("assets/client/hybrid/art/catalogue.json", "{}")
        for p in some:
            z.writestr("assets/" + p[len("res://"):], b"png")  # source files only
    problems, stats = asset_audit.audit(apk)
    assert any(p.startswith("APK: catalogue") for p in problems), problems[:3]
    assert any("imported textures" in p for p in problems)
    assert stats["apk_ctex"] == 0


def test_the_packed_python_check_names_a_staged_file_the_package_lacks():
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as imy:
        imy.writestr("STAGED.json", json.dumps({"sha1": {"wizard_rts/net/ai_wizard.py": "a", "wizard_rts/data/ai_wizards.json": "b", "wizard_rts/narrative/party.py": "c",
                                                         "wizard_rts/net/pvp.py": "d", "wizard_rts/data/narrative/config.json": "e"}}))
        imy.writestr("wizard_rts/net/ai_wizard.pyc", b"x")
        imy.writestr("wizard_rts/narrative/party.pyc", b"x")
        imy.writestr("wizard_rts/net/pvp.pyc", b"x")
        imy.writestr("wizard_rts/data/narrative/config.json", b"{}")
        # ai_wizards.json is staged but absent from the package
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as z:
        z.writestr("assets/chaquopy/app.imy", inner.getvalue())
    with zipfile.ZipFile(io.BytesIO(outer.getvalue())) as z:
        problems = inspect_apk.packed_python_problems(z)
    assert problems and "ai_wizards.json" in problems[0]


# ------------------------------------------------------------------ run-time image loading stays export-safe

CLIENT_SCRIPTS = [p for p in (PROJECT / "client").rglob("*.gd")
                  if "/tests/" not in p.as_posix() and "/tools/" not in p.as_posix() and p.name != "asset_loader.gd"]


@pytest.mark.parametrize("pattern,why", [
    (r"Image\.load_from_file\(", "reads a source image from disk: absent from an export"),
    (r"\bImage\.new\(\)[\s\S]{0,120}\.load\(", "Image.load of a res:// path: absent from an export"),
    (r"FileAccess\.file_exists\(\s*ProjectSettings\.globalize_path\(\s*\"res://", "a filesystem path to res:// art: absent from an export"),
])
def test_no_client_script_loads_art_from_a_source_file(pattern: str, why: str):
    bad = [p.relative_to(PROJECT).as_posix() for p in CLIENT_SCRIPTS if re.search(pattern, p.read_text(encoding="utf-8", errors="replace"))]
    assert bad == [], (why, bad)


def test_hybrid_art_and_the_duel_art_go_through_the_package_safe_loader():
    for rel in ("client/hybrid/hybrid_art.gd", "client/scripts/art.gd"):
        text = (PROJECT / rel).read_text(encoding="utf-8")
        assert "asset_loader.gd" in text and "AssetLoader." in text, rel
    loader = (PROJECT / "client/scripts/asset_loader.gd").read_text(encoding="utf-8")
    assert loader.index("ResourceLoader.exists") < loader.index("Image.load_from_file"), "the imported resource is tried first; the source file is only a development fallback"


# ------------------------------------------------------------------ the Android identity and version

def test_the_new_apk_updates_the_installed_one():
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(PROJECT / "export_presets.cfg", encoding="utf-8")
    from wizard_rts.net import protocol

    for section in (s for s in cfg.sections() if s.endswith(".options") and "package/unique_name" in cfg[s]):
        opts = cfg[section]
        assert opts["package/unique_name"] == '"com.duelmasterbattle.game"'  # the identity the phones already have
        assert opts["package/signed"] == "true"
        assert int(opts["version/code"]) >= 2, "an update must have a higher version code than the build already installed (1)"
        assert opts["version/name"].strip('"') == protocol.GAME_VERSION


# ------------------------------------------------------------------ one game: the menu and the project

def test_the_player_menu_is_wizard_world_only():
    lines = (PROJECT / "client/scripts/main_menu.gd").read_text(encoding="utf-8").splitlines()
    main = chr(10).join(l for l in lines if not l.strip().startswith("#"))  # the header comment names what was removed; the code must not
    for needle in ("overworld.tscn", "game_board.tscn", "g01_shell", "Adventure", "has_save", "EncounterSession", "NEW GAME", "RESUME", "Quick Duel"):
        assert needle not in main, needle
    for label in ("Play Single Player", "Host Multiplayer", "Join Multiplayer", "Settings"):
        assert '"%s"' % label in main
    project = (PROJECT / "project.godot").read_text(encoding="utf-8")
    assert 'run/main_scene="res://client/scenes/main_menu.tscn"' in project
    # the developer menu is only entered through the dev switch
    users = [p.relative_to(PROJECT).as_posix() for p in (PROJECT / "client").rglob("*.gd") if "dev_menu.tscn" in p.read_text(encoding="utf-8", errors="replace")
             and "/tests/" not in p.as_posix() and "/tools/" not in p.as_posix()]
    assert users == ["client/scripts/main_menu.gd"], users
    assert "_DevMode.enabled()" in main
    dev_mode = (PROJECT / "client/scripts/dev_mode.gd").read_text(encoding="utf-8")
    assert 'OS.has_feature("mobile")' in dev_mode.split("static func enabled")[1].split("static func")[0], "a phone can never turn the developer menu on"


def test_the_wizard_world_launch_never_touches_the_old_adventure_save():
    hw = (PROJECT / "client/scenes/hybrid_world.gd").read_text(encoding="utf-8")
    assert "adv.test_mode = true" in hw.split("adv.new_game()")[0][-300:], "the old adventure's autoload must not write its save when Wizard World starts"
