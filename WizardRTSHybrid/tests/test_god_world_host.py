"""God World through the real host route: `host.build` on the `god_catan_v1` profile, the session's hello/start/state/inspect/pause/speed ops, saves in
their own folder, and `HostServer.step` driving the clock without sockets' timing (the loop body is called directly)."""

from __future__ import annotations

import json

from wizard_rts.god_world import persist
from wizard_rts.god_world.world import GodWorld
from wizard_rts.net import host as host_mod
from wizard_rts.net import protocol


def _hello(session, conn, **extra):
    return session.handle(conn, {"op": "hello", "protocol": protocol.PROTOCOL_VERSION, "game": protocol.GAME_VERSION, "name": "Joe", **extra}, 0.0)


def test_host_build_selects_the_god_world_and_the_session_serves_the_board_and_state(tmp_path, monkeypatch):
    monkeypatch.setenv("DMB_RUNS", str(tmp_path))
    args = host_mod.parse_args(["--profile", "god_catan_v1", "--seed", "21", "--max-players", "1", "--no-discovery", "--port", "0", "--secret", "s", "--code", "1234", "--runs-dir", str(tmp_path)])
    h = host_mod.build(args)
    assert isinstance(h.world, GodWorld) and h.session.world is h.world
    assert not hasattr(h.world, "dmb")  # no legacy WorldState anywhere in this profile
    conn = object()
    r = _hello(h.session, conn, secret="s")
    assert r["status"] == "ok" and r["host"] and r["profile"] == "god_catan_v1"
    assert h.session.handle(conn, {"op": "move", "dx": 1}, 0.0)["reason"] == "not_allowed_in_god_world"
    assert h.session.handle(conn, {"op": "start"}, 0.0)["status"] == "ok"
    st = h.session.handle(conn, {"op": "state", "seq": 1}, 0.0)
    assert st["status"] == "ok" and "board" in st and len(st["board"]["hexes"]) == 30
    assert st["snapshot"]["profile"] == "god_catan_v1" and st["snapshot"]["phase"] == "SETUP"
    st2 = h.session.handle(conn, {"op": "state", "seq": 2}, 0.0)
    assert "board" not in st2  # sent once
    # the clock is the host's: advancing moves game time, speed and pause act on the one clock
    h.last_tick = 0.0
    h._advance(0.5)
    assert h.world.game_ms == 500 and h.stats["quanta"] == 5
    assert h.session.handle(conn, {"op": "speed", "scale": 4}, 0.0)["speed"] == 4
    h._advance(1.0)
    assert h.world.game_ms == 2500
    assert h.session.handle(conn, {"op": "pause", "on": True}, 0.0)["paused"] is True
    h._advance(1.5)
    assert h.world.game_ms == 2500
    assert h.session.handle(conn, {"op": "pause", "on": False}, 0.0)["paused"] is False
    assert h.session.handle(conn, {"op": "speed", "scale": 3}, 0.0)["status"] == "rejected"
    h.session.handle(conn, {"op": "speed", "scale": 1}, 0.0)
    # inspect and label answer in game language
    while h.world.phase == "SETUP":
        h.last_tick = 0.0
        h._advance(0.5)
    v = next(iter(h.world.villages.values()))
    d = h.session.handle(conn, {"op": "inspect", "id": f"village:{v['id']}"}, 0.0)["details"]
    assert d["title"] == v["name"] and any("Touches" in line for line in d["lines"])
    lab = h.session.handle(conn, {"op": "label", "id": f"hex:{h.world.board.hexes[0][4:]}"}, 0.0)["label"]
    assert lab["title"]
    # save lands in the god_world folder, never the wizard's
    s = h.session.handle(conn, {"op": "save", "slot": "manual"}, 0.0)
    assert s["status"] == "ok" and "god_world" in s["path"] and (tmp_path / "god_world" / "saves" / "god_world.manual.json").exists()
    assert not (tmp_path / "saves").exists()
    # a second build continues the save
    h2 = host_mod.build(args)
    assert h2.prepared["loaded"] and h2.world.game_ms == h.world.game_ms and h2.world.state_hash() == h.world.state_hash()


def test_a_wizard_save_is_refused_by_the_god_world_loader(tmp_path, monkeypatch):
    monkeypatch.setenv("DMB_RUNS", str(tmp_path))
    p = persist.slot_path("manual")
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"kind": "wizard", "world": {}}), encoding="utf-8")
    try:
        persist.load_world(p)
    except persist.SaveError as exc:
        assert "not a God World save" in str(exc)
    else:
        raise AssertionError("a foreign save must be refused")


def test_boundary_checkpoints_are_written_by_the_session_tick(tmp_path, monkeypatch):
    monkeypatch.setenv("DMB_RUNS", str(tmp_path))
    from wizard_rts.god_world.session import GodSession

    w = GodWorld(seed=0)
    s = GodSession(w, permanent=True, autosave_s=0)
    seq = 0
    while not w.history["age_winners"]:
        seq += 1
        w.advance(1000, seq, snapshot=False)
        s.tick(float(seq))
    assert persist.slot_path("boundary").exists()
    while w.phase != "RUNNING":
        seq += 1
        w.advance(1000, seq, snapshot=False)
        s.tick(float(seq))
    assert persist.slot_path("age_started").exists()
    loaded, _ = persist.load_world(persist.slot_path("age_started"))
    assert loaded.age == 2 and loaded.phase == "RUNNING"
