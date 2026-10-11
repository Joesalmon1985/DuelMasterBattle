"""M2 pipeline: pinned Mindustry source -> importer -> versioned JSON -> hybrid overrides -> registry (D06)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from wizard_rts.industry import registry as R

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "sources" / "manifest.json").read_text())
PIN = next(s for s in MANIFEST["sources"] if s["id"] == "mindustry")
DEFS = json.loads((ROOT / "wizard_rts" / "data" / "mindustry_defs.json").read_text())


def test_manifest_pin_and_provenance():
    assert PIN["url"] == "https://github.com/Anuken/Mindustry" and PIN["license"].startswith("GPL-3.0")
    assert len(PIN["commit"]) == 40 and PIN["tag"] == "v146"
    prov = DEFS["_provenance"]
    assert prov["commit"] == PIN["commit"] and prov["license"] == "GPL-3.0"
    for f in ("Items.java", "Liquids.java", "Blocks.java", "UnitTypes.java"):
        assert f in prov["files"]


def test_setup_scripts_pin_mindustry():
    sh = (ROOT / "scripts" / "setup_external.sh").read_text()
    assert PIN["commit"] in sh and "mindustry" in sh and "MINDUSTRY_FULL" in sh
    ps = (ROOT / "scripts" / "setup_external.ps1").read_text()
    assert "$Manifest.sources" in ps  # the PowerShell script walks the manifest, so the Mindustry entry is created there too
    assert "git -C $dest checkout $source.commit" in ps


@pytest.mark.skipif(not (ROOT / "external" / "mindustry" / ".git").exists(), reason="external/mindustry not cloned (scripts/setup_external.sh mindustry)")
def test_checkout_matches_pin_and_json_is_current():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "verify_pins.py")], capture_output=True, text=True)
    assert "PIN_OK mindustry " + PIN["commit"] in r.stdout, r.stdout
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "import_mindustry_defs.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


# Values below were read by hand from the pinned v146 files (file: line of the definition).
@pytest.mark.parametrize("block,expect", [
    ("mechanical-drill", {"requirements": {"copper": 12}, "size": 2}),          # Blocks.java: mechanicalDrill (tier 2, drillTime 600)
    ("pneumatic-drill", {"requirements": {"copper": 18, "graphite": 10}, "size": 2}),
    ("conveyor", {"requirements": {"copper": 1}, "size": 1}),
    ("silicon-smelter", {"requirements": {"copper": 30, "lead": 25}, "consume_items": {"coal": 1, "sand": 2}, "output_item": {"silicon": 1}}),
    ("graphite-press", {"requirements": {"copper": 75, "lead": 30}, "consume_items": {"coal": 2}, "output_item": {"graphite": 1}}),
    ("combustion-generator", {"requirements": {"copper": 25, "lead": 15}, "power_production_per_second": 60.0}),
    ("battery", {"requirements": {"copper": 5, "lead": 20}, "power_buffer": 4000.0}),
    ("power-node", {"requirements": {"copper": 1, "lead": 3}}),
    ("ground-factory", {"requirements": {"copper": 50, "lead": 120, "silicon": 80}, "consume_power_per_second": 72.0, "size": 3}),
])
def test_imported_block_values(block, expect):
    b = DEFS["blocks"][block]
    for k, v in expect.items():
        assert b[k] == v, (block, k, b[k], v)


def test_imported_timings_items_units():
    b = DEFS["blocks"]
    assert b["mechanical-drill"]["fields"]["drillTime"] == 600 and b["mechanical-drill"]["fields"]["tier"] == 2
    assert b["pneumatic-drill"]["fields"]["drillTime"] == 400 and b["pneumatic-drill"]["fields"]["tier"] == 3
    assert b["silicon-smelter"]["fields"]["craftTime"] == 40 and b["graphite-press"]["fields"]["craftTime"] == 90
    assert b["conveyor"]["conveyor"] == {"speed": 0.03, "displayed_items_per_second": 4.2, "tiles_per_second": 1.8, "item_space": 0.4, "capacity": 3}
    assert b["power-node"]["power_node"] == {"laser_range": 6, "max_nodes": 10}
    plans = {p["unit"]: p for p in b["ground-factory"]["plans"]}
    assert plans["dagger"]["time_ticks"] == 900 and plans["dagger"]["requirements"] == {"silicon": 10, "lead": 10}
    assert plans["crawler"]["time_ticks"] == 600 and plans["nova"]["requirements"] == {"silicon": 30, "lead": 20, "titanium": 20}
    assert DEFS["items"]["copper"]["hardness"] == 1 and DEFS["items"]["titanium"]["hardness"] == 3 and DEFS["items"]["coal"]["hardness"] == 2
    assert DEFS["items"]["coal"]["flammability"] == 1.0
    d = DEFS["units"]["dagger"]
    assert d["health"] == 150 and d["speed"] == 0.5 and d["weapons"][0]["damage"] == 9.0 and d["weapons"][0]["reload_ticks"] == 13
    assert DEFS["units"]["flare"]["flying"] is True and DEFS["units"]["flare"]["health"] == 70


def test_drill_rate_formula_matches_drill_getdrilltime():
    drill = DEFS["blocks"]["mechanical-drill"]["drill"]
    # Drill.getDrillTime = drillTime + 50 * hardness; a 2x2 drill on 4 ore tiles: 60 * 4 / time items per second
    for item, hardness in (("copper", 1), ("coal", 2), ("sand", 0)):
        assert drill["items_per_second"][item] == pytest.approx(60 * 4 / (600 + 50 * hardness), abs=1e-4)
    assert "titanium" not in drill["items_per_second"]  # tier 2 cannot drill titanium (hardness 3)
    assert "titanium" in DEFS["blocks"]["pneumatic-drill"]["drill"]["items_per_second"]


def test_overrides_are_labelled_adaptation_and_registry_keeps_source_cost():
    o = R.overrides()
    assert "adapt" in o["_doc"].lower() or "our decision" in o["_doc"].lower()
    spec = R.block("mdy:mechanical_drill")
    assert spec["source_cost"] == {"copper": 12} and spec["cost"] == {"plank": 4, "granite": 3}
    assert "hybrid adaptation" in spec["cost_source"]
    assert R.ware("copper") == "mdy.copper" and R.ware("coal") == "coal"  # coal is the shared Widelands ware
    for k in R.kinds():
        s = R.block(k)
        assert s["card"].startswith("dmb.card.") and s["definition"].startswith("mindustry.")
        assert all(g in ("plank", "granite", "iron", "log") for g in s["cost"]), k  # paid in Widelands goods only


def test_unit_adaptation_scales_recorded():
    actors, weapons = R.unit_rules()
    a, w = actors["mdy_dagger"], weapons["MDY_dagger_gun"]
    assert a["hp"] == 150 * R.overrides()["units"]["hp_scale"]
    assert w["warheads"][0]["damage"] == round(9 * R.overrides()["units"]["damage_scale"])
    assert "Mindustry v146" in a["source"] and "Mindustry v146" in w["source"]


def test_no_new_deposit_kinds_exist():
    """The owner clarification: advanced extraction reads the Widelands resource layer; there is no Mindustry ore layer."""
    from wizard_rts import terrain as T

    assert T.RES_NAMES == ("", "coal", "iron", "gold", "stones", "fish", "water")
    rules = R.extraction()["deposit_rules"]
    assert set(rules) <= set(T.RES_NAMES)
    assert not any(k in R.extraction() for k in ("new_ores", "ore_tiles", "overlay"))
