"""The God World art roster resolves: every id in `data/god_world/asset_manifest.json` and in the ruleset's age table is a catalogue item with its image in
the repository (export-pack inclusion is `test_android_assets.py`'s audit, which covers the whole catalogue)."""

from __future__ import annotations

import json
from pathlib import Path

from wizard_rts.god_world import rules

HYB = Path(__file__).resolve().parents[1]
ROOT = HYB.parent
CATALOGUE = ROOT / "godot_project" / "client" / "hybrid" / "art" / "catalogue.json"
MANIFEST = HYB / "wizard_rts" / "data" / "god_world" / "asset_manifest.json"


def _items():
    data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    return {i["id"]: i for i in data["items"]}


def _files(item) -> list[str]:
    out = []
    if item.get("godot"):
        out.append(item["godot"])
    out += list(item.get("frames_godot", []))
    for p in item.get("parts", []):
        if p.get("file"):
            out.append(p["file"])
    return out


def _exists(res_path: str) -> bool:
    return (ROOT / "godot_project" / res_path.replace("res://", "")).exists()


def test_manifest_ids_exist_are_imported_and_their_files_are_present():
    items = _items()
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ids = set(man["warehouse"]) | set(man["scenery"])
    for group in ("production", "military"):
        for lst in man[group].values():
            ids.update(lst)
    for wid in man["workers"]:
        found = [k for k in items if k == wid or k.startswith(wid + ".")]
        assert found, f"no sheets for worker family {wid}"
        ids.update(found[:7])
    missing = sorted(i for i in ids if i not in items)
    assert missing == [], missing
    aliased = sorted(i for i in ids if items[i].get("status") != "imported")
    assert aliased == [], f"manifest claims art that is only an alias/placeholder: {aliased}"
    absent = sorted(f for i in ids for f in _files(items[i]) if not _exists(f))
    assert absent == [], absent[:10]


def test_every_art_id_in_the_ruleset_is_in_the_manifest():
    man = json.loads(MANIFEST.read_text(encoding="utf-8"))
    listed = set(man["warehouse"])
    for group in ("production", "military"):
        for lst in man[group].values():
            listed.update(lst)
    workers = set(man["workers"])
    for age in (1, 2, 3, 4):
        for role in rules.ROLES:
            for art in rules.role_buildings(age, role):
                assert art in listed, (age, role, art)
            assert rules.role_worker(age, role) in workers
        mil = rules.military_spec(age)
        for key in ("facility", "unit", "city_facility", "city_unit"):
            if mil.get(key):
                assert mil[key] in listed, (age, key, mil[key])
    assert rules.data()["warehouse"] in listed
    for m in rules.data()["expedition_party"]:
        assert m["art"] in workers
    assert set(man["aliases_not_claimed"]).isdisjoint(listed)
