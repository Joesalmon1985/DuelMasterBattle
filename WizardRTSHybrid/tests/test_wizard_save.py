"""A.4: Wizard Mode save and load (narrative/persist.py, the `save` and `load` server ops, `HYBRID_LOAD_SLOT`)."""
import json
import os
import pickle
import subprocess
import sys
from pathlib import Path

import pytest

from wizard_rts import magic, narrative, server
from wizard_rts.narrative import characters, config, persist
from wizard_rts.world import HybridWorld

HERE = Path(__file__).resolve().parents[1]


def play(w, seconds, start=None):
    base = int(w.dmb.clock.get("clock_sequence", 0)) if start is None else start
    for i in range(seconds):
        w.advance(1000, base + i + 1, snapshot=False)


@pytest.fixture()
def world():
    w = HybridWorld(507, profile="campaign")
    narrative.enable(w)
    w.ai_enabled = False
    play(w, 40)
    w.player["tx"], w.player["ty"] = next(iter(w.workers.values()))["tx"], next(iter(w.workers.values()))["ty"]
    play(w, 3)  # the tick gives the bodies beside the wizard characters, so there is narrative state to keep
    assert w.narrative["links"], "fixture: the wizard stands among workers"
    return w


def test_save_then_load_gives_identical_state_and_narrative(world, tmp_path):
    path = tmp_path / "a.pkl"
    info = persist.save_world(world, path)
    loaded, linfo = persist.load_world(path)
    assert loaded.state_hash() == world.state_hash() == info["hash"]
    assert loaded.narrative == world.narrative
    assert not linfo["hash_mismatch"] and linfo["game_ms"] == info["game_ms"] == int(world.dmb.clock["game_ms"])
    assert list(loaded.dmb.people) == list(world.dmb.people)
    assert not (tmp_path / "a.pkl.tmp").exists()  # atomic: the temporary file is gone
    play(loaded, 5)
    play(world, 5)
    assert loaded.state_hash() == world.state_hash()  # and the loaded world continues exactly as the original does


def test_a_world_without_the_layer_gains_it_on_load(tmp_path):
    w = HybridWorld(507, profile="campaign")
    persist.save_world(w, tmp_path / "plain.pkl")
    loaded, _ = persist.load_world(tmp_path / "plain.pkl")
    assert narrative.enabled(loaded) and loaded.narrative["version"] == config.version()


def test_a_truncated_file_is_refused_and_prev_is_offered(world, tmp_path):
    path = tmp_path / "t.pkl"
    persist.save_world(world, path)
    play(world, 2)
    persist.save_world(world, path)  # the first save becomes t.prev.pkl
    prev = persist.prev_path(path)
    assert prev.exists()
    path.write_bytes(path.read_bytes()[:5000])
    with pytest.raises(persist.SaveError) as e:
        persist.load_world(path)
    assert e.value.reason == "corrupt" and e.value.prev == str(prev)
    back, _ = persist.load_world(prev)
    assert int(back.dmb.clock["game_ms"]) < int(world.dmb.clock["game_ms"])


def test_a_corrupt_save_never_replaces_the_previous_valid_one(world, tmp_path):
    path = tmp_path / "c.pkl"
    persist.save_world(world, path)
    play(world, 1)
    persist.save_world(world, path)
    good_prev = persist.prev_path(path).read_bytes()
    path.write_bytes(b"garbage")
    play(world, 1)
    persist.save_world(world, path)  # the damaged file is overwritten, not promoted to .prev
    assert persist.prev_path(path).read_bytes() == good_prev
    assert persist.load_world(path)[1]["game_ms"] == int(world.dmb.clock["game_ms"])


def rewrite(path, **changes):
    payload = pickle.loads(path.read_bytes())
    payload.update(changes)
    path.write_bytes(pickle.dumps(payload, protocol=5))


def test_a_newer_narrative_version_is_refused(world, tmp_path):
    path = tmp_path / "n.pkl"
    persist.save_world(world, path)
    rewrite(path, narrative_version=config.version() + 1)
    with pytest.raises(persist.SaveError) as e:
        persist.load_world(path)
    assert e.value.reason == "newer_version"


def test_an_older_version_without_a_migration_is_refused_and_with_one_is_migrated(world, tmp_path, monkeypatch):
    path = tmp_path / "o.pkl"
    persist.save_world(world, path)
    monkeypatch.setattr(config, "version", lambda: 2)
    with pytest.raises(persist.SaveError) as e:
        persist.load_world(path)
    assert e.value.reason == "older_version"
    monkeypatch.setitem(persist.MIGRATIONS, 1, lambda payload: payload)
    loaded, _ = persist.load_world(path)
    assert loaded.state_hash() == world.state_hash()


def test_another_format_is_refused(world, tmp_path):
    path = tmp_path / "f.pkl"
    persist.save_world(world, path)
    rewrite(path, format=persist.save_format() + 1)
    with pytest.raises(persist.SaveError) as e:
        persist.load_world(path)
    assert e.value.reason == "format"


def test_a_hash_mismatch_loads_but_is_flagged(world, tmp_path):
    path = tmp_path / "h.pkl"
    persist.save_world(world, path)
    rewrite(path, hash="0" * 40)
    loaded, info = persist.load_world(path)
    assert info["hash_mismatch"] and info["recovered"] and loaded is not None


def test_two_saves_in_a_row_differ_only_in_game_time(world, tmp_path):
    a, b = tmp_path / "a.pkl", tmp_path / "b.pkl"
    persist.save_world(world, a)
    persist.save_world(world, b)
    assert a.read_bytes() == b.read_bytes()  # nothing in a save depends on when it was written
    play(world, 1)
    persist.save_world(world, b)
    pa, pb = pickle.loads(a.read_bytes()), pickle.loads(b.read_bytes())
    assert {k for k in pa if k not in ("world", "hash", "game_ms")} == {k for k in pb if k not in ("world", "hash", "game_ms")}
    for k in ("format", "narrative_version", "profile", "seed"):
        assert pa[k] == pb[k]
    assert pb["game_ms"] == pa["game_ms"] + 1000 and pb["hash"] != pa["hash"]


def test_a_save_between_two_advances_does_not_change_the_run(tmp_path):
    def run(save_at):
        w = HybridWorld(507, profile="campaign")
        narrative.enable(w)
        w.ai_enabled = True  # the factions are playing: a save must not perturb their decisions either
        play(w, 30)
        if save_at:
            persist.save_world(w, tmp_path / "mid.pkl")
            persist.save_world(w, tmp_path / "mid.pkl")
        play(w, 30)
        return w.state_hash(), w.rng.getstate()

    assert run(False) == run(True)


def test_server_ops_save_and_load(world, tmp_path, monkeypatch):
    monkeypatch.setenv("DMB_RUNS", str(tmp_path))
    r = server._handle(world, {"op": "save", "slot": "quit"})
    assert r["status"] == "ok" and Path(r["path"]) == tmp_path / "saves" / "campaign" / "quit.pkl" and Path(r["path"]).exists()
    saved_ms = int(world.dmb.clock["game_ms"])
    play(world, 30)
    assert int(world.dmb.clock["game_ms"]) == saved_ms + 30_000
    r = server._handle(world, {"op": "load", "slot": "quit"})
    assert r["status"] == "ok" and r["loaded"] is True and not r["hash_mismatch"]
    loaded = r["_swap"]
    assert int(loaded.dmb.clock["game_ms"]) == saved_ms and loaded.visual_state is True
    assert r["terrain"] is not None and r["snapshot"]["story"]["narrative"]["version"] == config.version()
    assert r["snapshot"]["player"]["tx"] == world.player["tx"]
    assert server._handle(world, {"op": "load", "slot": "nothing"})["reason"] == "missing"
    assert server._handle(world, {"op": "save", "slot": "../evil"})["reason"] == "bad_slot"
    assert server._handle(world, {"op": "save", "slot": ""})["reason"] == "bad_slot"
    (tmp_path / "saves" / "campaign" / "quit.pkl").write_bytes(b"x")
    bad = server._handle(world, {"op": "load", "slot": "quit"})
    assert bad["status"] == "rejected" and bad["reason"] == "corrupt" and "_swap" not in bad


def test_the_server_resumes_from_hybrid_load_slot(world, tmp_path):
    persist.save_world(world, tmp_path / "saves" / "campaign" / "boot.pkl")
    base = dict(os.environ, DMB_RUNS=str(tmp_path), HYBRID_PROFILE="campaign", HYBRID_SIM_PORT="0")

    def boot(slot):
        env = dict(base, HYBRID_LOAD_SLOT=slot)
        p = subprocess.Popen([sys.executable, "-u", "-m", "wizard_rts.server"], cwd=HERE, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        out = []
        try:
            for line in p.stdout:
                out.append(line)
                if "HYBRID_SIM_READY" in line or "HYBRID_LOAD_FAILED" in line:
                    break
        finally:
            p.kill()
            p.wait()
        return "".join(out)

    ok = boot("boot")
    assert "HYBRID_LOADED" in ok and ok.index("HYBRID_LOADED") < ok.index("HYBRID_SIM_READY")
    info = json.loads(ok.split("HYBRID_LOADED", 1)[1].splitlines()[0])
    assert info["game_ms"] == int(world.dmb.clock["game_ms"]) and info["hash_mismatch"] is False
    assert "HYBRID_LOAD_FAILED missing" in boot("absent")
