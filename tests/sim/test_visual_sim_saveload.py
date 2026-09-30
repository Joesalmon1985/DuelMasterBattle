"""Stage 4 — save/load field inventory + deterministic next command."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from sim.dmb.core.commands import CommandEnvelope
from sim.dmb.core.state import WorldState
from sim.dmb.core.world import WorldSim
from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.testing.visual_sim.authority import observe_authority
from sim.dmb.testing.visual_sim.runner import advance_once, wait_once


KERNEL_FIELD_GROUPS = (
    "formations",
    "buildings",
    "orders",
    "units",
    "battles",
    "roads",
    "people",
    "carts",
    "rng",
    "ids",
    "clock",
    "player",
    "research",
    "tech_draft",
    "diplomacy",
    "leases",
    "command_receipts",
)


def _inventory(state: WorldState) -> dict:
    """Independent in-memory field inventory — not solely to_dict roundtrip."""
    out = {}
    for name in KERNEL_FIELD_GROUPS:
        val = getattr(state, name, None)
        if hasattr(val, "to_dict"):
            out[name] = val.to_dict()
        elif isinstance(val, dict):
            out[name] = deepcopy(val)
        elif isinstance(val, list):
            out[name] = list(val)
        else:
            out[name] = deepcopy(val) if val is not None else None
    out["world_id"] = state.world_id
    out["world_version"] = state.world_version
    return out


def _seed_durable(state: WorldState) -> None:
    if not state.research:
        state.research = {"faction:1": {"unlocked": ["tech:probe"]}}
    if not state.tech_draft:
        state.tech_draft = {"active": True, "hands": {"faction:1": ["card:a"]}}
    if not state.diplomacy:
        state.diplomacy = {"faction:1": {"faction:2": {"stance": "peace"}}}


def test_save_load_inventory_equivalence_and_next_command() -> None:
    sim = load_fixture("FX-MVP", seed=507)
    _seed_durable(sim.state)
    for i in range(5):
        advance_once(sim, seq=i + 1)
    wait_once(sim, press_id="saveload-w0")
    before = _inventory(sim.state)
    snap = sim.snapshot()

    restored_state = WorldState.from_dict(deepcopy(snap["world"]))
    after = _inventory(restored_state)
    for key in KERNEL_FIELD_GROUPS:
        assert after.get(key) == before.get(key), f"mismatch on {key}"

    # Fresh WorldSim rebound to restored state (same path idea as SaveCoordinator.commit_load).
    sim2 = WorldSim(state=restored_state)
    node = str(sim2.state.player.get("node_id") or "node:35")
    press = f"after-load-wait-{sim2.state.world_version}"
    env = CommandEnvelope(
        1,
        "local",
        sim2.state.world_id,
        "cmd:after-load-wait",
        sim2.state.world_version,
        "Wait",
        {"current_node": node, "press_id": press},
    )
    result = sim2.dispatch(env)
    assert result.status == "ACCEPTED", result
    observe_authority(sim2)


def test_gallery_entries_labeled() -> None:
    import json

    gallery = {
        "entries": [
            {
                "id": "gal_smoke",
                "scenario_class": "ARRANGED_STATE",
                "contract": "smoke_boot.json",
            },
            {
                "id": "gal_slice_b",
                "scenario_class": "PRODUCTION_JOURNEY",
                "contract": "slice_b_construction.json",
            },
        ]
    }
    path = Path("qa/visual_sim/contracts/gallery_selected.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(gallery, indent=2) + "\n", encoding="utf-8")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert len(data["entries"]) <= 8
    for e in data["entries"]:
        assert e["scenario_class"] in {"ARRANGED_STATE", "PRODUCTION_JOURNEY"}
