"""Regression: rockfall quest installs on non-south exits; seed 507 unchanged."""

from __future__ import annotations

from sim.dmb.testing.fixtures import load_fixture
from sim.dmb.world.boulder_quest import get_rockfall, rockfall_blocks_travel


def test_seed_507_still_blocks_south() -> None:
    sim = load_fixture("FX-MVP", seed=507)
    meta = ((sim.state.board.get("g05") or {}).get("boulder_quest") or {})
    assert meta["from_node"] == "node:35"
    assert meta["exit_id"] == "node:35.south"
    assert meta.get("direction") == "south"
    assert rockfall_blocks_travel(sim.state, "node:35", meta["to_node"])


def test_non_south_seed_installs_legal_exit() -> None:
    """Seed that previously crashed with 'no south exit' must now boot."""
    sim = load_fixture("FX-MVP", seed=10007)
    rockfall = get_rockfall(sim.state)
    assert rockfall is not None
    direction = str(rockfall.get("direction") or "")
    assert direction
    from_node = str(rockfall["node_id"])
    to_node = str(rockfall["target_node_id"])
    assert rockfall_blocks_travel(sim.state, from_node, to_node)
    # Prefer south when present; otherwise any cardinal.
    assert direction in {"north", "east", "south", "west"}


def test_fx_era_promotion_seed_boots() -> None:
    sim = load_fixture("FX-ERA", seed=10007)
    assert get_rockfall(sim.state) is not None
