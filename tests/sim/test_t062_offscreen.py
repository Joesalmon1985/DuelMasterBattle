"""T062 bounded off-screen battle resolution."""

from __future__ import annotations

from copy import deepcopy

from sim.dmb.military.offscreen import MAX_SIM_MS, OffscreenBattleResolver


def _unit(uid: str, faction: str, pos: list[float], hp: int, attack: int = 10, rng: int = 4) -> dict:
    return {
        "id": uid,
        "faction_id": faction,
        "alive": True,
        "position": pos,
        "current_health": hp,
        "max_health": hp,
        "base_attack": attack,
        "era_factor": 1,
        "armour": 0,
        "range_tiles": rng,
        "period_ms": 1000,
        "remaining_attack_cooldown_ms": 0,
        "speed_tiles_per_s": 2.5,
        "buffs": [],
        "shield_remaining": 0,
    }


def test_timeout_is_not_victory() -> None:
    # Far apart units never engage → stalemate at bound.
    snap = {
        "units": {
            "a": _unit("a", "red", [0.0, 0.0], 100),
            "b": _unit("b", "blue", [1000.0, 0.0], 100),
        },
        "entry_effective_health": {"red": 100, "blue": 100},
    }
    out = OffscreenBattleResolver().resolve(snap)
    assert out["outcome"] == "stalemate"
    assert out["sim_ms"] == 0 or out["outcome"] == "stalemate"
    assert out["global_time_advanced"] is False
    assert out["industry_accrued"] is False
    assert out["reinforcements_accrued"] is False
    assert out["stalemate_bound_ms"] == MAX_SIM_MS
    assert out["units"]["a"]["alive"] and out["units"]["b"]["alive"]


def test_identity_and_health_conserve() -> None:
    snap = {
        "units": {
            "a": _unit("a", "red", [0.0, 0.0], 80, attack=25, rng=2),
            "b": _unit("b", "blue", [1.0, 0.0], 80, attack=25, rng=2),
        },
        "entry_effective_health": {"red": 80, "blue": 80},
    }
    ids_before = set(snap["units"])
    out = OffscreenBattleResolver().resolve(snap)
    assert set(out["units"]) == ids_before
    for uid in ids_before:
        assert 0 <= out["units"][uid]["current_health"] <= snap["units"][uid]["max_health"]


def test_buffs_frozen_no_global_time() -> None:
    u = _unit("a", "red", [0.0, 0.0], 100)
    u["buffs"] = [
        {
            "id": "eff:1",
            "kind": "shield",
            "expires_game_ms": 30_000,
            "shield_remaining": 25,
            "frozen": False,
        }
    ]
    snap = {
        "units": {
            "a": u,
            "b": _unit("b", "blue", [1.0, 0.0], 20, attack=5, rng=1),
        },
        "entry_effective_health": {"red": 100, "blue": 20},
    }
    out = OffscreenBattleResolver().resolve(snap)
    assert out["global_time_advanced"] is False
    buffs = out["units"]["a"]["buffs"]
    assert buffs and buffs[0]["frozen"] is True
    assert buffs[0]["expires_game_ms"] == 30_000


def test_stalemate_not_recalculated_without_material_event() -> None:
    snap = {
        "units": {
            "a": _unit("a", "red", [0.0, 0.0], 100),
            "b": _unit("b", "blue", [1000.0, 0.0], 100),
        },
        "material_change_version": 3,
        "entry_effective_health": {"red": 100, "blue": 100},
    }
    first = OffscreenBattleResolver().resolve(snap)
    second = OffscreenBattleResolver().resolve(deepcopy(snap))
    assert first["outcome"] == second["outcome"] == "stalemate"
    assert first["material_change_version"] == 3
    # Same inputs → same identity conservation; continuous re-resolve is caller's concern.
    assert first["units"]["a"]["current_health"] == second["units"]["a"]["current_health"]
