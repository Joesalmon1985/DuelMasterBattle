"""T3.2: the controller plays through the episode runner with a learned-network policy, the scheduler and selection rule behave as designed."""
import numpy as np
import pytest

from neuro import nets as N
from neuro.controller import Controller, DecisionLog, read_log
from neuro.episode import EpisodeConfig, run_episode
from wizard_rts import construction as con


def _controller(cfg, genome, log=None):
    return Controller(None, "Red", N.Nets(genome), cfg, 0, log)


def test_a_random_genome_plays_twenty_minutes_with_many_commands_from_several_heads(tmp_path):
    cfg = EpisodeConfig(seed=7, game_minutes=20, map_size="small", agent_seats=("Red",))
    log = DecisionLog(tmp_path / "d.jsonl.gz")
    ctl = _controller(cfg, N.random_genome(np.random.default_rng(1)), log)
    res = run_episode(cfg, {"Red": ctl})
    log.close()
    st = ctl.stats()
    assert res.end_reason == "horizon" and res.vp_replay_ok and res.ledger_ok
    assert st["commands"] >= 20 and len(st["by_head"]) >= 4
    assert res.seats[0].commands == st["commands"] and res.seats[0].rejected == st["rejected"]  # every command was accepted or rejected with a reason
    assert sum(st["reject_reasons"].values()) == st["rejected"]
    recs = read_log(tmp_path / "d.jsonl.gz")
    assert any(r.get("trigger") == "strategic" for r in recs) and all(r["seat"] == "Red" for r in recs)
    print(f"\n[timing] controller tick mean {st['tick_ms_mean']:.1f} ms, max {st['tick_ms_max']:.0f} ms; heads {st['by_head']}")
    assert st["tick_ms_mean"] < 15.0


def test_with_huge_temperatures_and_a_high_wait_bias_only_the_draft_is_answered():
    g = N.random_genome(np.random.default_rng(2))
    nets = N.Nets(g)
    nets.temp[:] = 1e6
    nets.w["H0"]["b2"][:] = 1000.0
    cfg = EpisodeConfig(seed=7, game_minutes=14, map_size="small", agent_seats=("Red",))
    seen = []

    class Spy(Controller):
        def on_step(self, game_s, events):
            out = super().on_step(game_s, events)
            seen.extend(c["op"] for c in out)
            return out

    ctl = Spy(None, "Red", nets, cfg, 0, None)
    run_episode(cfg, {"Red": ctl})
    assert ctl.ticks > 10 and set(seen) <= {"draft"}  # the wait path works; the draft is exempt by design


def test_destroying_an_own_building_triggers_an_event_tick_within_five_seconds(tmp_path):
    cfg = EpisodeConfig(seed=7, game_minutes=14, map_size="small", agent_seats=("Red",))
    log = DecisionLog(tmp_path / "e.jsonl.gz")
    hit = {}

    class Saboteur(Controller):
        def on_step(self, game_s, events):
            out = super().on_step(game_s, events)
            if not hit and game_s >= 700 and 16 <= game_s - self.last_tick <= 40:
                w = self.env.world
                wh = con.faction_warehouse(w, "Red")["id"]
                victim = sorted(b["id"] for b in w.buildings.values() if b["faction_name"] == "Red" and b["id"] != wh and int(b.get("hp", 0)) > 0)[0]
                w.damage_building(victim, 10 ** 9, ["structure"], {})
                hit["s"] = game_s
            return out

    ctl = Saboteur(None, "Red", N.Nets(N.random_genome(np.random.default_rng(1))), cfg, 0, log)
    run_episode(cfg, {"Red": ctl})
    log.close()
    assert hit
    events = [r for r in read_log(tmp_path / "e.jsonl.gz") if str(r.get("trigger", "")).startswith("event:") and hit["s"] < r["s"] <= hit["s"] + 7]
    assert events and "lost_building" in events[0]["trigger"]
    assert events[0]["s"] % 5 == 0
