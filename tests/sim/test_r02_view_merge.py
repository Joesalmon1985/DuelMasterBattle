"""R02: omitted view fields must not delete; empty collections must."""

from __future__ import annotations

from copy import deepcopy


def merge_player_view(cache: dict, incoming: dict, requested_fields: list[str] | None = None) -> dict:
    """Mirror of DmbWorldClient.merge_player_view for oracle tests."""
    out = deepcopy(cache)
    base_keys = {
        "world_id",
        "world_version",
        "clock",
        "player",
        "board",
        "people",
        "presentation",
        "scope",
    }
    fields = list(requested_fields or [])
    for key, value in incoming.items():
        apply = True
        if fields and key not in base_keys:
            apply = key in fields
        if apply:
            out[key] = deepcopy(value)
    return out


def test_omitted_hazards_preserved():
    cache = {
        "world_id": "w1",
        "clock": {"game_ms": 1},
        "hazards": {"catastrophe": {"cubes": {"cube:a": {"active": True}}}},
        "people": {"p1": {"name": "A"}},
    }
    lean = {
        "world_id": "w1",
        "world_version": 2,
        "clock": {"game_ms": 2},
        "player": {},
        "board": {},
        "people": {"p1": {"name": "A"}},
        "presentation": {},
        "scope": "player",
    }
    merged = merge_player_view(cache, lean, requested_fields=[])
    assert "cube:a" in merged["hazards"]["catastrophe"]["cubes"]
    assert merged["clock"]["game_ms"] == 2


def test_explicit_empty_hazards_removes():
    cache = {
        "hazards": {"catastrophe": {"cubes": {"cube:a": {"active": True}}}},
        "clock": {"game_ms": 1},
    }
    incoming = {
        "hazards": {"catastrophe": {"cubes": {}}},
        "clock": {"game_ms": 3},
    }
    merged = merge_player_view(cache, incoming, requested_fields=["hazards", "clock"])
    assert merged["hazards"]["catastrophe"]["cubes"] == {}
    assert merged["clock"]["game_ms"] == 3


def test_filtered_fields_do_not_clobber_unrequested():
    cache = {
        "units": {"u1": {}},
        "hazards": {"catastrophe": {"cubes": {"c1": {}}}},
        "clock": {"game_ms": 1},
    }
    incoming = {
        "world_id": "w",
        "clock": {"game_ms": 9},
        "player": {},
        "board": {},
        "people": {},
        "presentation": {},
        "scope": "player",
        "units": {"u2": {}},
        # hazards omitted from this filtered reply
    }
    merged = merge_player_view(cache, incoming, requested_fields=["units", "clock"])
    assert "c1" in merged["hazards"]["catastrophe"]["cubes"]
    assert "u2" in merged["units"]
    assert "u1" not in merged["units"]


def test_fx_hazard_fixture_returns_hazards_when_requested():
    from sim.dmb.testing.fixtures import load_fixture

    world = load_fixture("FX-HAZARD", seed=408)
    lean = dict(world.state.read_view("player", fields=None))
    assert "hazards" not in lean
    focused = dict(
        world.state.read_view(
            "player",
            fields=["hazards", "fx_hazard", "player", "clock", "board", "leases"],
        )
    )
    assert "hazards" in focused
    cubes = focused["hazards"]["catastrophe"]["cubes"]
    assert len(cubes) >= 3
    # Simulate interleaving: lean reply must not wipe hazards in the client merge.
    # Convert nested MappingProxy to plain dicts for the oracle.
    def thaw(obj):
        if isinstance(obj, dict) or hasattr(obj, "keys"):
            return {k: thaw(obj[k]) for k in obj.keys()}
        if isinstance(obj, (list, tuple)):
            return [thaw(x) for x in obj]
        return obj

    merged = merge_player_view(thaw(focused), thaw(lean), requested_fields=[])
    assert len(merged["hazards"]["catastrophe"]["cubes"]) >= 3
