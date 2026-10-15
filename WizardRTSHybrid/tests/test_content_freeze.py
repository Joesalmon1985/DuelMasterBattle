"""The content roster is frozen (D33): the live registries must equal data/content_freeze.json."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from wizard_rts import coverage, freeze

HYB = Path(__file__).resolve().parents[1]
IMPORTERS = sorted((HYB / "scripts").glob("import_*.py"))


def test_manifest_matches_live_registries():
    assert freeze.check() == []


def test_counts():
    assert freeze.manifest()["counts"] == {"entities": 582, "buildings": 486, "units": 96, "cards": 168, "hand_cards": 33, "wares": 128, "mdy_items": 22, "mdy_liquids": 11}
    assert freeze.live_roster()["counts"] == freeze.manifest()["counts"]


def test_excluded_stay_excluded():
    excluded = freeze.manifest()["excluded"]
    assert len(excluded) >= 99
    assert len([k for k in excluded if k.startswith("openra:") and "D27" in excluded[k]]) == 11  # the decoy buildings
    status = {r["key"]: r["status"] for r in coverage.build()}
    not_excluded = sorted(k for k in excluded if status.get(k) != "excluded")
    assert not_excluded == []


def test_data_files_unchanged():
    assert freeze.data_hashes() == freeze.manifest()["data_files"]


def test_source_pins_unchanged():
    pins = json.loads((HYB / "sources" / "manifest.json").read_text(encoding="utf-8"))["sources"]
    assert {s["id"]: s["commit"] for s in pins} == freeze.manifest()["source_pins"]


def test_roster_hash_matches_manifest():
    assert freeze.roster_hash() == freeze.manifest()["roster_sha256"]


def test_importers_exist():
    assert len(IMPORTERS) >= 20


@pytest.mark.parametrize("script", IMPORTERS, ids=lambda p: p.name)
def test_importers_refuse_without_unfreeze(script):
    env = {k: v for k, v in os.environ.items() if k != "DMB_UNFREEZE"}
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 3, f"{script.name} exited {r.returncode}: {r.stdout[-300:]}{r.stderr[-300:]}"
    assert "content is frozen" in r.stdout + r.stderr
