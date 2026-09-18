"""R04: SemanticResolver + MagicService range / forged observed_ids."""

from __future__ import annotations

from sim.dmb.narrative.semantic import SemanticResolver, in_interaction_range
from sim.dmb.player.magic import MagicService
from sim.dmb.testing.fixtures import load_fixture


def test_far_observe_near_actions():
    sim = load_fixture("FX-BATTLE", seed=404)
    state = sim.state
    resolver = SemanticResolver(state)
    # Pick a blue unit far from wizard spawn [4,5].
    target = next(
        u for u in state.units.values() if u["faction_id"] == "faction:blue" and u.get("status") != "reserve"
    )
    far_poses = {"wizard": [4.0, 5.0], target["id"]: list(target["position"])}
    far = resolver.inspect(target["id"], local_poses=far_poses)
    assert far["ok"]
    assert far["label"].startswith("Blue")
    assert far["nearby"] is False
    assert [a["id"] for a in resolver.available_actions(target["id"], local_poses=far_poses)] == ["observe"]

    near_poses = {
        "wizard": [target["position"][0], target["position"][1]],
        target["id"]: list(target["position"]),
    }
    near = resolver.inspect(target["id"], local_poses=near_poses)
    assert near["nearby"] is True
    ids = [a["id"] for a in resolver.available_actions(target["id"], local_poses=near_poses)]
    assert "observe" in ids and "buff" in ids and "destroy" in ids


def test_forged_observed_ids_cannot_bypass_distance():
    sim = load_fixture("FX-BATTLE", seed=404)
    state = sim.state
    magic = MagicService(state)
    target = next(
        u for u in state.units.values() if u["faction_id"] == "faction:blue" and u.get("status") != "reserve"
    )
    # Wizard still at spawn; unit far away — even with forged observed_ids.
    forged = {target["id"], "everything"}
    out = magic.destroy(
        target["id"],
        observed_local_ids=forged,
        command_id="forge-1",
        local_poses={"wizard": [4.0, 5.0], target["id"]: list(target["position"])},
    )
    assert out["status"] == "rejected"
    assert out.get("reason") == "out_of_range"


def test_synced_moving_pose_allows_cast():
    sim = load_fixture("FX-BATTLE", seed=404)
    state = sim.state
    magic = MagicService(state)
    target = next(
        u for u in state.units.values() if u["faction_id"] == "faction:red" and u.get("status") != "reserve"
    )
    # Authoritative unit may still be far, but synchronised local poses are adjacent.
    out = magic.validate_destroy(
        target["id"],
        observed_local_ids=set(),
        local_poses={"wizard": [5.0, 5.0], target["id"]: [5.5, 5.0]},
    )
    assert out.get("ok") is True
    assert in_interaction_range([5.0, 5.0], [5.5, 5.0])
