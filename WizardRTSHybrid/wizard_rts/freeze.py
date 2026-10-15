"""The frozen content roster (decision D33): what exists in the game, recorded once and checked on every test run.

`data/content_freeze.json` is the oracle. `live_roster()` recomputes the same lists from the registries the game actually
uses, `check()` reports every difference, and `scripts/freeze_content.py --bump` is the only sanctioned way to change the
manifest (it needs a reason and the owner's approval; see docs/CONTENT_FREEZE.md).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROSTER_VERSION = "roster-1.0.0"
MANIFEST = Path(__file__).with_name("data") / "content_freeze.json"
DATA_DIR = Path(__file__).with_name("data")
SOURCES = Path(__file__).resolve().parents[1] / "sources" / "manifest.json"
DATA_FILES = ("widelands_defs.json", "openra_rules.json", "mindustry_defs.json", "mindustry_full.json", "mindustry_overrides.json", "tech_cards.json", "terrain_defs.json")
HASHED_LISTS = ("entities", "units", "cards", "hand_cards", "wares", "mdy_items", "mdy_liquids")

_cache: dict = {}


def live_roster() -> dict:
    """Sorted id lists from the live registries: entities (graph.entities), units (unit:* ids), cards (graph.generated_cards),
    hand_cards (tech.cards), wares (wl_defs.defs()['wares']), mdy_items, mdy_liquids (mindustry_defs.json), and
    excluded {id: reason} from coverage.build() rows with status 'excluded'. Also 'counts'."""
    from . import coverage, tech, wl_defs
    from .content import graph
    entities = graph.entities()
    mdy = json.loads((DATA_DIR / "mindustry_defs.json").read_text(encoding="utf-8"))
    roster = {
        "entities": sorted(entities),
        "units": sorted(k for k, e in entities.items() if e["type"] == "unit"),
        "cards": sorted(graph.generated_cards()),
        "hand_cards": sorted(tech.cards()),
        "wares": sorted(wl_defs.defs()["wares"]),
        "mdy_items": sorted(mdy["items"]),
        "mdy_liquids": sorted(mdy["liquids"]),
        "excluded": {r["key"]: r["blocker"] for r in sorted(coverage.build(), key=lambda r: r["key"]) if r["status"] == "excluded"},
    }
    roster["counts"] = {
        "entities": len(roster["entities"]), "buildings": len(roster["entities"]) - len(roster["units"]), "units": len(roster["units"]),
        "cards": len(roster["cards"]), "hand_cards": len(roster["hand_cards"]), "wares": len(roster["wares"]),
        "mdy_items": len(roster["mdy_items"]), "mdy_liquids": len(roster["mdy_liquids"]),
    }
    return roster


def data_hashes() -> dict[str, str]:
    """sha256 per DATA_FILES entry; line endings are normalised so a CRLF checkout hashes like an LF one."""
    out = {}
    for name in DATA_FILES:
        raw = (DATA_DIR / name).read_bytes().replace(b"\r\n", b"\n")
        out[name] = "sha256:" + hashlib.sha256(raw).hexdigest()
    return out


def source_pins() -> dict[str, str]:
    """Pinned upstream commits from sources/manifest.json: {source id: commit}."""
    return {s["id"]: s["commit"] for s in json.loads(SOURCES.read_text(encoding="utf-8"))["sources"]}


def roster_hash(roster: dict | None = None) -> str:
    roster = live_roster() if roster is None else roster
    return hashlib.sha256(json.dumps({k: roster[k] for k in HASHED_LISTS}, sort_keys=True).encode()).hexdigest()


def build_manifest(base_commit: str, frozen_on: str) -> dict:
    """A complete manifest from the live registries (used by scripts/freeze_content.py only)."""
    roster = live_roster()
    return {"roster_version": ROSTER_VERSION, "frozen_on": frozen_on, "base_commit": base_commit, "counts": roster["counts"],
            **{k: roster[k] for k in HASHED_LISTS}, "excluded": roster["excluded"], "data_files": data_hashes(),
            "source_pins": source_pins(), "roster_sha256": roster_hash(roster)}


def manifest() -> dict:
    if "manifest" not in _cache:
        _cache["manifest"] = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return _cache["manifest"]


def _diff_lists(name: str, frozen: list, live: list, out: list[str]) -> None:
    added, removed = sorted(set(live) - set(frozen)), sorted(set(frozen) - set(live))
    if added:
        out.append(f"{name}: {len(added)} added: {', '.join(added[:20])}{' ...' if len(added) > 20 else ''}")
    if removed:
        out.append(f"{name}: {len(removed)} removed: {', '.join(removed[:20])}{' ...' if len(removed) > 20 else ''}")


def check() -> list[str]:
    """Human-readable differences between the live registries and the manifest; [] means the roster is exactly the frozen one."""
    m, live, out = manifest(), live_roster(), []
    if m["roster_version"] != ROSTER_VERSION:
        out.append(f"roster_version: manifest says {m['roster_version']}, freeze.py says {ROSTER_VERSION}")
    for name in HASHED_LISTS:
        _diff_lists(name, m[name], live[name], out)
    for key in sorted(m["excluded"]):
        if key not in live["excluded"]:
            out.append(f"excluded: {key} is no longer excluded")
    for key in sorted(set(live["excluded"]) - set(m["excluded"])):
        out.append(f"excluded: {key} is newly excluded")
    now = data_hashes()
    for name in DATA_FILES:
        if now[name] != m["data_files"].get(name):
            out.append(f"data file changed: {name}")
    if not out and roster_hash(live) != m["roster_sha256"]:
        out.append("roster_sha256 differs although every list matches (manifest was edited by hand?)")
    return out
