"""Stage-1 Visual Sim QA kernel unit tests + oracle negatives."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sim.dmb.testing.visual_sim.contracts import load_contract, validate_contract
from sim.dmb.testing.visual_sim.images import check_image
from sim.dmb.testing.visual_sim.oracle import OracleFailure, run_oracle
from sim.dmb.testing.visual_sim.runner import run_sim_smoke

ROOT = Path(__file__).resolve().parents[2]


def test_smoke_contract_loads_and_sim_authority_independent() -> None:
    contract = load_contract("smoke_boot.json")
    assert contract["scenario_class"] == "ARRANGED_STATE"
    packed = run_sim_smoke(contract)
    authority = packed["authority"]
    # Expected contract is not derived from authority observation.
    assert contract["expectations"]["authority"]["player_node_id"] == "node:35"
    assert authority["player_node_id"] == "node:35"
    assert authority["counts"]["buildings"] >= 1
    result = run_oracle(contract, authority=authority)
    assert result["status"] == "PASS"
    assert result["scenario_class"] == "ARRANGED_STATE"


def test_oracle_missing_render_entity() -> None:
    contract = {
        "scenario_id": "neg_missing",
        "scenario_class": "ARRANGED_STATE",
        "fixture": "FX-MVP",
        "seed": 507,
        "expectations": {"render": {"require_sim_ids": ["unit:missing"]}},
    }
    validate_contract(contract)
    render = {"entities": [{"sim_id": "unit:1", "role": "body", "visible_in_tree": True, "in_viewport": True}]}
    result = run_oracle(contract, render=render)
    assert result["status"] == "FAIL"
    assert result["failures"][0]["code"] == "missing_render_entity"


def test_oracle_duplicate_render_entity() -> None:
    contract = {
        "scenario_id": "neg_dup",
        "scenario_class": "ARRANGED_STATE",
        "fixture": "FX-MVP",
        "seed": 507,
        "expectations": {"render": {"require_sim_ids": ["unit:1"]}},
    }
    render = {
        "entities": [
            {"sim_id": "unit:1", "role": "body"},
            {"sim_id": "unit:1", "role": "body"},
        ]
    }
    result = run_oracle(contract, render=render)
    assert result["status"] == "FAIL"
    assert result["failures"][0]["code"] == "duplicate_render_entity"


def test_oracle_stale_and_wrong_location_and_hidden() -> None:
    base = {
        "scenario_class": "ARRANGED_STATE",
        "fixture": "FX-MVP",
        "seed": 507,
    }
    stale = {
        **base,
        "scenario_id": "neg_stale",
        "expectations": {"render": {"forbid_sim_ids": ["order:old"]}},
    }
    render_stale = {"entities": [{"sim_id": "order:old", "role": "body"}]}
    assert run_oracle(stale, render=render_stale)["failures"][0]["code"] == "stale_render_entity"

    wrong = {
        **base,
        "scenario_id": "neg_wrong",
        "expectations": {"render": {"grid_near": [{"sim_id": "unit:1", "grid": [10, 10], "tol": 0.5}]}},
    }
    render_wrong = {"entities": [{"sim_id": "unit:1", "role": "body", "grid": [0, 0]}]}
    assert run_oracle(wrong, render=render_wrong)["failures"][0]["code"] == "wrong_location"

    hidden = {
        **base,
        "scenario_id": "neg_hidden",
        "expectations": {"render": {"entity_visible": ["unit:1"]}},
    }
    render_hidden = {
        "entities": [{"sim_id": "unit:1", "role": "body", "visible_in_tree": False, "in_viewport": True}]
    }
    assert run_oracle(hidden, render=render_hidden)["failures"][0]["code"] == "hidden_or_off_viewport"


def test_oracle_blank_image(tmp_path: Path) -> None:
    # Minimal near-blank PNG via PIL if available.
    pytest.importorskip("PIL")
    from PIL import Image

    blank = tmp_path / "blank.png"
    Image.new("RGB", (64, 64), (128, 128, 128)).save(blank)
    checked = check_image(blank)
    contract = {
        "scenario_id": "neg_blank",
        "scenario_class": "ARRANGED_STATE",
        "fixture": "FX-MVP",
        "seed": 507,
        "expectations": {"image": {"require_nonblank": True}},
    }
    result = run_oracle(contract, image=checked)
    assert result["status"] == "FAIL"
    assert result["failures"][0]["code"] == "blank_or_missing_screenshot"


def test_oracle_missing_image_file() -> None:
    contract = {
        "scenario_id": "neg_missing_img",
        "scenario_class": "ARRANGED_STATE",
        "fixture": "FX-MVP",
        "seed": 507,
        "expectations": {"image": {"require_nonblank": True}},
    }
    result = run_oracle(contract, image={"status": "FAIL", "code": "blank_or_missing_screenshot"})
    assert result["failures"][0]["code"] == "blank_or_missing_screenshot"


def test_positive_render_and_image(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    from PIL import Image

    shot = tmp_path / "ok.png"
    img = Image.new("RGB", (128, 128), (20, 40, 200))
    for x in range(20, 80):
        for y in range(20, 80):
            img.putpixel((x, y), (200, 40, 20))
    img.save(shot)
    checked = check_image(shot)
    assert checked["status"] == "PASS"
    contract = {
        "scenario_id": "pos",
        "scenario_class": "PRODUCTION_JOURNEY",
        "fixture": "FX-MVP",
        "seed": 507,
        "expectations": {
            "render": {"require_sim_ids": ["unit:1"], "entity_visible": ["unit:1"]},
            "image": {"require_nonblank": True, "min_bytes": 100},
        },
    }
    render = {
        "entities": [
            {
                "sim_id": "unit:1",
                "role": "body",
                "visible_in_tree": True,
                "in_viewport": True,
                "grid": [5, 5],
            }
        ]
    }
    result = run_oracle(contract, render=render, image=checked)
    assert result["status"] == "PASS"
    assert result["scenario_class"] == "PRODUCTION_JOURNEY"
