"""T066 stacking support buffs and pause-safe expiry."""

from __future__ import annotations

from sim.dmb.core.state import WorldState
from sim.dmb.core.types import WorldId
from sim.dmb.military.buffs import FREQUENCY_CAP_MULT, RANGE_EXTRA_CAP, BuffService
from sim.dmb.military.units import MilitaryService
from sim.dmb.player.magic import MagicService


def _world() -> WorldState:
    state = WorldState(world_id=WorldId("world:t066"))
    state.player["node_id"] = "n1"
    state.clock["game_ms"] = 0
    return state


def test_caps_shield_frequency_range() -> None:
    state = _world()
    mil = MilitaryService(state)
    buffs = BuffService(state)
    u = mil.spawn("unit.ancient.line", home_node_id="n1", faction_id="a", era="prehistoric", factory_id="f")
    # Line max HP 100 → shield 25 each; cap 2× = 200
    for i in range(10):
        buffs.apply(u["id"], "shield", game_ms=0, command_id=f"s{i}")
    assert state.units[u["id"]]["shield_remaining"] == 200
    for i in range(10):
        buffs.apply(u["id"], "frequency", game_ms=0, command_id=f"f{i}")
    mods = buffs.modifiers(u["id"])
    assert mods["attack_frequency_mult"] == float(FREQUENCY_CAP_MULT)
    for i in range(10):
        buffs.apply(u["id"], "range", game_ms=0, command_id=f"r{i}")
    assert buffs.modifiers(u["id"])["extra_range"] == RANGE_EXTRA_CAP


def test_expiry_removes_unused_shield_only() -> None:
    state = _world()
    mil = MilitaryService(state)
    buffs = BuffService(state)
    u = mil.spawn("unit.ancient.heavy", home_node_id="n1", faction_id="a", era="prehistoric", factory_id="f")
    buffs.apply(u["id"], "shield", game_ms=0, command_id="s1")
    assert state.units[u["id"]]["shield_remaining"] == 45
    before_hp = state.units[u["id"]]["current_health"]
    buffs.tick(game_ms=30_000, paused=False)
    assert state.units[u["id"]]["shield_remaining"] == 0
    assert state.units[u["id"]]["current_health"] == before_hp


def test_duel_pause_freezes_and_duplicate_receipt() -> None:
    state = _world()
    mil = MilitaryService(state)
    magic = MagicService(state)
    u = mil.spawn("unit.ancient.line", home_node_id="n1", faction_id="a", era="prehistoric", factory_id="f")
    first = magic.apply_buff(u["id"], "shield", command_id="buff:1", game_ms=0)
    second = magic.apply_buff(u["id"], "shield", command_id="buff:1", game_ms=0)
    assert first["status"] == "buffed"
    assert second["status"] == "idempotent" or second["result"]["status"] == "idempotent"
    buffs = BuffService(state)
    buffs.set_frozen(True)
    buffs.tick(game_ms=60_000, paused=True)
    assert len(state.units[u["id"]]["buffs"]) == 1
    assert state.units[u["id"]]["shield_remaining"] > 0
