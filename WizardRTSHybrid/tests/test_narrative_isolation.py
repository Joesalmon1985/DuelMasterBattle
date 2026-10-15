"""A.2: the narrative layer exists only when something enables it, and enabling it changes nothing the factions can see.

(a) a campaign world without `world.narrative` has the hash it had before the layer existed (references recorded on 14 Oct 2026 from the
    unmodified code at planning HEAD 6a8302a; if a legitimate simulation change moves them, re-record them from a world with this package
    removed from the call path, never from a world with narrative enabled);
(b) the same world with the layer enabled has identical faction-only state, RNG state and event count;
(c) `world.py` and `sim_api.py` never mention it."""
import hashlib
import json
import os
import pickle
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from wizard_rts import history, narrative
from wizard_rts.world import HybridWorld

HERE = Path(__file__).resolve().parents[1]
SECONDS = 180
REFERENCE = {507: "cb8e1a0b1b0d6e3749eb451db86ac791638d9336", 11: "2d5f07b04cd4c2bf007d6c9a11213a2be94765d9"}
FACTION_FIELDS = ("buildings", "units", "stocks", "workers", "carriers", "tech", "stats")


def run(seed, enable):
    w = HybridWorld(seed, profile="campaign")
    w.ai_enabled = False
    if enable:
        narrative.enable(w)
    for i in range(SECONDS):
        w.advance(1000, i + 1, snapshot=False)
    return w


def faction_hash(w):
    raw = {n: getattr(w, n, None) for n in FACTION_FIELDS}
    return hashlib.sha1(json.dumps(raw, sort_keys=True, default=str).encode()).hexdigest()


@pytest.fixture(scope="module", params=sorted(REFERENCE))
def pair(request):
    return request.param, run(request.param, False), run(request.param, True)


def test_a_world_without_the_layer_is_unchanged(pair):
    seed, plain, _ = pair
    assert "narrative" not in plain.__dict__
    assert plain.state_hash() == REFERENCE[seed]


def test_b_enabling_the_layer_leaves_the_factions_alone(pair):
    _, plain, wiz = pair
    assert "narrative" in wiz.__dict__
    assert faction_hash(plain) == faction_hash(wiz)
    assert plain.rng.getstate() == wiz.rng.getstate()  # the narrative layer never draws from world.rng
    assert plain.events.total == wiz.events.total  # and never appends to world.events
    assert wiz.narrative["wizard"]["spells"] == []
    assert wiz.narrative["log"] == []


def test_c_the_simulation_core_never_mentions_the_layer():
    for name in ("world.py", "sim_api.py"):
        assert "narrative" not in (HERE / "wizard_rts" / name).read_text(), name


def test_narrative_package_uses_no_world_rng_and_no_wall_clock():
    pkg = HERE / "wizard_rts" / "narrative"
    for f in sorted(pkg.glob("*.py")):
        text = f.read_text()
        assert "world.rng" not in text.replace("`world.rng`", ""), f.name  # the docstring may name it; code may not use it
        if f.name != "perf.py":
            for banned in ("time.time(", "perf_counter", "datetime.now", "time.monotonic("):
                assert banned not in text, (f.name, banned)


def test_enable_is_idempotent_and_pickles():
    w = HybridWorld(507, profile="campaign")
    assert not narrative.enabled(w)
    n = narrative.enable(w)
    n["wizard"]["spells"].append(0)
    assert narrative.enable(w) is n
    w2 = pickle.loads(pickle.dumps(w))
    assert w2.narrative == w.narrative


def test_tick_runs_once_a_game_second_and_only_when_enabled():
    from wizard_rts.narrative import perf

    perf.reset()
    w = HybridWorld(507, profile="campaign")
    w.ai_enabled = False
    for i in range(5):
        w.advance(1000, i + 1, snapshot=False)
    assert perf.COUNTS.get("tick", 0) == 0
    narrative.enable(w)
    for i in range(5, 10):
        w.advance(1000, i + 1, snapshot=False)
    assert perf.COUNTS["tick"] == 5


def test_the_wizard_crosses_a_cycle_reset():
    w = HybridWorld(507, profile="campaign")
    narrative.enable(w)
    w.narrative["wizard"]["spells"] = [0, 1, 6]
    w.narrative["wizard"]["lessons"]["meet"] = 1234
    w.narrative["links"]["worker:1"] = "person:9"
    fresh = history.cycle_reset(w)
    assert not narrative.enabled(fresh)  # the reset builds a plain HybridWorld; the server then carries the wizard over
    narrative.carry_over(w, fresh)
    assert fresh.narrative["wizard"]["spells"] == [0, 1, 6]
    assert fresh.narrative["wizard"]["lessons"] == {"meet": 1234}
    assert fresh.narrative["links"] == {}  # entities of the old cycle do not exist any more
    assert fresh.narrative["wizard"] is not w.narrative["wizard"]


def test_server_creates_the_layer_and_publishes_it():
    """The real server process: its world has `narrative`, and the snapshot carries `story.narrative`."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = dict(os.environ, HYBRID_SIM_PORT=str(port), HYBRID_PROFILE="campaign")
    proc = subprocess.Popen([sys.executable, "-u", "-m", "wizard_rts.server"], cwd=HERE, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for line in proc.stdout:
            if "HYBRID_SIM_READY" in line:
                break
        else:
            pytest.fail("the server did not start")
        conn = socket.create_connection(("127.0.0.1", port), timeout=60)
        conn.sendall(b'{"op":"snapshot"}\n')
        buf = b""
        deadline = time.time() + 60
        while b"\n" not in buf and time.time() < deadline:
            buf += conn.recv(1 << 20)
        reply = json.loads(buf.split(b"\n", 1)[0])
        story = reply["snapshot"]["story"]
        assert story["narrative"]["version"] == narrative.config.version() and [e["kind"] for e in story["narrative"]["events"]] == ["resident_arrived"]
        assert len(story["narrative"]["journal"]["lessons"]) == 6 and len(story["narrative"]["journal"]["opening"]) == 3  # campaign: the opening and a teacher
    finally:
        proc.kill()
        proc.wait()
