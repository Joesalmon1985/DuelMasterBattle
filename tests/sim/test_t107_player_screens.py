"""T107 inventory / grimoire / knowledge screens."""

from __future__ import annotations

from sim.dmb.core.commands import CommandEnvelope
from sim.dmb.narrative.knowledge import export_knowledge_list
from sim.dmb.player.grimoire import export_grimoire
from sim.dmb.player.inventory import InventoryService
from sim.dmb.testing.fixtures import load_fixture


def test_inventory_grimoire_knowledge_views() -> None:
    sim = load_fixture("FX-ERA", seed=507)
    state = sim.state
    inv = InventoryService(state).player_view()
    assert inv["can_manage_remotely"] is False
    assert "items" in inv
    grim = export_grimoire(state)
    assert grim["remote_cast_allowed"] is False
    assert grim["spells"]
    know = export_knowledge_list(state)
    assert isinstance(know, list)
    view = state.read_view("player", ["inventory", "grimoire", "knowledge"])
    assert "inventory" in view and "grimoire" in view and "knowledge" in view


def test_prepare_spell_does_not_remote_cast() -> None:
    sim = load_fixture("FX-ERA", seed=507)
    env = CommandEnvelope(
        protocol_version=1,
        session_id="t107",
        world_id=sim.state.world_id,
        command_id="t107-prep",
        expected_world_version=sim.state.world_version,
        kind="Interact",
        payload={"action": "prepare_spell", "spell_id": "ward"},
    )
    result = sim.dispatch(env)
    assert result.status == "ACCEPTED"
    assert sim.state.player.get("prepared_spell") == "ward"
    grim = export_grimoire(sim.state)
    assert grim["prepared_spell"] == "ward"
    assert grim["remote_cast_allowed"] is False
