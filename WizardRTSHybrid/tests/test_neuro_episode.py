"""T1.5: the episode runner. A game with controllers in some seats ends for a recorded reason, validates its books, scores every seat and
checkpoints so a long game can be resumed."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from neuro.episode import EpisodeConfig, run_episode
from neuro.random_controller import RandomController
from wizard_rts import construction as con
from wizard_rts import territory
from wizard_rts.sim_api import HybridEnv


class Saboteur:
    """A test controller that wipes its own seat out at a chosen second (what a God command would do)."""

    kind = "saboteur"
    decisions_logged = 0

    def __init__(self, faction, at_s):
        self.faction, self.at_s, self.env = faction, at_s, None

    def attach(self, env):
        self.env = env

    def spawn_for(self, faction):
        return Saboteur(faction, -1)

    def on_step(self, game_s, events):
        if game_s == self.at_s:
            w = self.env.world
            w.damage_building(con.faction_warehouse(w, self.faction)["id"], 10 ** 9, ["structure"], {})
            for u in w.units.values():
                if u["faction_name"] == self.faction and territory.is_founder(u):
                    u["alive"] = False
        return []


def test_a_ten_minute_game_with_one_random_seat_ends_at_the_horizon_with_clean_books():
    cfg = EpisodeConfig(seed=507, game_minutes=10, map_size="small", agent_seats=("Red",))
    res = run_episode(cfg, {"Red": RandomController("Red", cfg, seed=1)})
    assert res.end_reason == "horizon" and res.t_end_min == 10.0
    assert res.vp_replay_ok and res.ledger_ok
    assert [s.faction for s in res.seats] == ["Red"] and len(res.control_seats) == 5
    assert res.seats[0].tier == "S" and res.seats[0].commands > 0
    assert res.catastrophe_level == "C0" and res.outbreak_interval_scale == 1.0
    assert res.decisions_logged > 0 and len(res.state_hash) == 40


def test_a_collective_loss_ends_the_game_and_every_seat_is_tier_c():
    cfg = EpisodeConfig(seed=507, game_minutes=60, map_size="small", agent_seats=(), outbreak_interval_scale=0.02, catastrophe_level="test",
                        world_knobs={"loss_outbreaks_total": 2})
    res = run_episode(cfg, {})
    assert res.end_reason == "collective_loss" and res.t_end_min < 60
    assert res.outcome["result"] == "collective_loss" and res.outbreaks >= 2
    assert {s.tier for s in res.control_seats} == {"C"}
    assert res.vp_replay_ok and res.ledger_ok
    first = res.control_seats[0].fitness
    assert all(abs(s.fitness - first) < 1e-6 for s in res.control_seats) and first < -500  # F = -1000 + 500 * t_c / T with t_c well before T


def test_a_seat_that_is_wiped_out_is_tier_e_with_the_time_it_fell():
    cfg = EpisodeConfig(seed=507, game_minutes=6, map_size="small", profile="developer", agent_seats=("Red",))
    res = run_episode(cfg, {"Red": Saboteur("Red", 120)})
    assert res.end_reason == "agent_collapsed"  # the only agent seat is gone: the episode stops
    seat = res.seats[0]
    assert seat.tier == "E" and seat.state == "collapsed" and seat.collapsed_at_min is not None and 2.0 <= seat.collapsed_at_min <= 3.0
    assert seat.fitness == pytest.approx(100 + 400 * seat.collapsed_at_min / 6, abs=0.01)  # elim_base + elim_time_weight * t_e / T (VP: no conquests)


def test_a_checkpoint_is_written_and_resumes_to_the_same_final_hash(tmp_path):
    cfg = EpisodeConfig(seed=11, game_minutes=2, map_size="small", checkpoint_game_minutes=1)
    res = run_episode(cfg, {}, log_dir=tmp_path)
    assert res.checkpoints == 2 and (tmp_path / "ckpt.pkl").exists() and not (tmp_path / "ckpt.pkl.tmp").exists()
    data = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert data["result"]["state_hash"] == res.state_hash and data["config"]["seed"] == 11
    # the last checkpoint was taken at the horizon: loading it gives the final state; an earlier one must continue to the same hash
    cfg2 = EpisodeConfig(seed=11, game_minutes=3, map_size="small", checkpoint_game_minutes=1)
    full = run_episode(cfg2, {}, log_dir=tmp_path / "b")
    # the checkpoint of run b at minute 3 equals its end; take run a's minute-2 checkpoint and play one more minute
    env = HybridEnv(seed=11, map_size="small", agent_factions=(), step_ms=1000, max_game_ms=3 * 60_000, profile="campaign", rewards=False)
    env.load((tmp_path / "ckpt.pkl").read_bytes())
    assert env.state_hash() == res.state_hash
    for _ in range(60):
        env.step({}, observe=False)
    assert env.state_hash() == full.state_hash


def _hash_in_subprocess(hashseed):
    root, repo = Path(__file__).resolve().parents[1], Path(__file__).resolve().parents[2]
    code = (
        f"import sys; sys.path[:0] = [{str(root)!r}, {str(repo)!r}]\n"
        "from neuro.episode import EpisodeConfig, run_episode\n"
        "from neuro.random_controller import RandomController\n"
        "cfg = EpisodeConfig(seed=23, game_minutes=5, map_size='small', agent_seats=('Red',))\n"
        "r = run_episode(cfg, {'Red': RandomController('Red', cfg, seed=4)})\n"
        "print(r.state_hash, r.seats[0].commands)\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env={**os.environ, "PYTHONHASHSEED": str(hashseed), "HYBRID_AI": "1"}, timeout=600)
    assert out.returncode == 0, out.stderr[-2000:]
    return out.stdout.strip().splitlines()[-1]


def test_the_same_seed_and_controller_give_the_same_game_whatever_the_hash_seed():
    a, b = _hash_in_subprocess(1), _hash_in_subprocess(2)
    assert a == b, (a, b)


def test_a_wall_cap_voids_the_game():
    cfg = EpisodeConfig(seed=507, game_minutes=60, map_size="small", wall_cap_s=1)
    res = run_episode(cfg, {})
    assert res.end_reason == "wall_cap" and {s.tier for s in res.control_seats} == {"V"}


def test_the_runner_refuses_inconsistent_seats():
    cfg = EpisodeConfig(seed=507, game_minutes=1, map_size="small", agent_seats=("Red",))
    with pytest.raises(ValueError):
        run_episode(cfg, {})
    with pytest.raises(ValueError):
        run_episode(EpisodeConfig(seed=507, game_minutes=1, map_size="small", opponents={"Blue": "champion:7"}), {})


@pytest.mark.skipif(not os.environ.get("DMB_SLOW"), reason="240 game minutes: set DMB_SLOW=1 (about 10-20 wall minutes)")
def test_a_full_240_minute_game_with_three_random_seats_completes():
    cfg = EpisodeConfig(seed=7, agent_seats=("Red", "Green", "Purple"))
    res = run_episode(cfg, {f: RandomController(f, cfg, seed=3) for f in cfg.agent_seats})
    assert res.end_reason in ("horizon", "collective_loss", "agent_collapsed") and res.vp_replay_ok and res.ledger_ok
    print("240-minute episode wall seconds:", res.wall_s, "end:", res.end_reason, "t_end:", res.t_end_min)


def test_the_event_cursor_survives_the_world_trimming_its_log():
    os.environ.setdefault("HYBRID_AI", "1")
    env = HybridEnv(seed=11, map_size="small", agent_factions=(), step_ms=1000, rewards=False)
    env.reset()
    w = env.world
    cursor = env.event_cursor()
    w.events.extend({"kind": "marker", "i": i} for i in range(7000))  # more than economy.EVENT_CAP: the next economy quantum trims the log
    env.step({}, observe=False)
    events, new_cursor = env.events_since(cursor)
    marks = [e["i"] for e in events if e["kind"] == "marker"]
    assert marks and marks[-1] == 6999 and marks == sorted(marks)  # the newest markers survive, in order, none repeated
    assert new_cursor - cursor >= 7000 and w.__dict__.get("events_trimmed", 0) > 0
    again, same = env.events_since(new_cursor)
    assert again == [] and same == new_cursor
