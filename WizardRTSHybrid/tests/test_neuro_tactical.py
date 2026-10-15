"""M8: the tactical controller N11 - orders, clustering, and a game with it switched on."""
import numpy as np

from neuro import nets as N
from neuro.controller import Controller
from neuro.episode import EpisodeConfig, run_episode
from neuro.tactical import ATTACK, FOCUS, HOLD, RETREAT, Tactical


def unit(i, x, y):
    return {"id": f"unit:{i}", "tx": x, "ty": y}


def test_clustering_is_single_link_and_deterministic():
    us = [unit(1, 0, 0), unit(2, 5, 0), unit(3, 11, 0), unit(4, 40, 40)]
    groups = Tactical._cluster(us)
    assert [[u["id"] for u in g] for g in groups] == [["unit:1", "unit:2", "unit:3"], ["unit:4"]]
    assert [[u["id"] for u in g] for g in Tactical._cluster(list(reversed(us)))] == [["unit:1", "unit:2", "unit:3"], ["unit:4"]]


def test_the_four_orders_become_the_right_commands():
    squad = [unit(1, 10, 10), unit(2, 11, 10)]
    enemies = [{"id": "unit:9", "tx": 20, "ty": 10}, {"id": "unit:8", "tx": 14, "ty": 10}]
    buildings = [{"id": "building:5", "tile": (30, 30)}, {"id": "building:6", "tile": (12, 12)}]
    ccs = [(0, 0, "building:1"), (50, 50, "building:2")]
    c = (10.5, 10.0)
    assert Tactical._command(HOLD, squad, c, enemies, buildings, ccs) == {"op": "stop", "units": ["unit:1", "unit:2"]}
    a = Tactical._command(ATTACK, squad, c, enemies, buildings, ccs)
    assert a["op"] == "move" and (a["tx"], a["ty"]) == (14, 10) and a["attack_move"] is True
    assert Tactical._command(FOCUS, squad, c, enemies, buildings, ccs) == {"op": "order", "unit": "unit:1", "target": "building:6"}
    r = Tactical._command(RETREAT, squad, c, enemies, buildings, ccs)
    assert r["op"] == "move" and (r["tx"], r["ty"]) == (0, 3) and r["attack_move"] is False
    assert Tactical._command(ATTACK, squad, c, [], buildings, ccs) is None and Tactical._command(RETREAT, squad, c, enemies, buildings, []) is None


def test_a_game_with_the_tactical_controller_on_runs_clean_and_is_replayable():
    def play():
        cfg = EpisodeConfig(seed=9, game_minutes=25, map_size="small", agent_seats=("Red", "Blue"), tactical=True)
        g = N.random_genome(np.random.default_rng(4))
        ctls = {s: Controller(None, s, N.Nets(g), cfg, 0, None) for s in cfg.agent_seats}
        res = run_episode(cfg, ctls)
        return res, ctls

    r1, c1 = play()
    r2, _c2 = play()
    assert r1.end_reason in ("horizon", "agent_collapsed") and r1.vp_replay_ok and r1.ledger_ok and r1.state_hash == r2.state_hash
    assert all(isinstance(c.tactical, Tactical) for c in c1.values())
    print("\n[tactical] orders issued:", {s: c.tactical.orders_issued for s, c in c1.items()})


def test_a_squad_next_to_a_visible_enemy_gets_each_of_the_four_orders_and_the_simulator_accepts_them():
    """Engagement on purpose: the rich world has six riflemen by the capital, a Blue raider in sight and a blight nest; N11's output bias forces each order in turn."""
    import copy
    import pickle

    from neuro import nets as NN
    from wizard_rts.sim_api import HybridEnv
    from tests.neuro_worlds import rich_world

    base = pickle.dumps(rich_world(), protocol=5)
    seen_ops = {}
    for order, name in enumerate(("hold", "attack", "focus", "retreat")):
        w = pickle.loads(base)
        env = HybridEnv(seed=1, map_size="standard", agent_factions=("Red",), step_ms=1000, profile="campaign")
        env.world = w
        g = NN.random_genome(np.random.default_rng(2))
        n = NN.Nets(g)
        n.w["N11"]["W2"][:] = 0.0
        n.w["N11"]["b2"][:] = -5.0
        n.w["N11"]["b2"][order] = 5.0
        cfg = EpisodeConfig(seed=1, game_minutes=60, map_size="standard", agent_seats=("Red",), tactical=True)
        ctl = Controller(env, "Red", n, cfg, 0, None)
        t = int(w.dmb.clock["game_ms"]) // 1000
        ctl._tick(t, "strategic")  # fills the cache N11 reads
        cmds = ctl.tactical.tick(t + 5)
        assert cmds, f"no tactical order for {name}"
        for cmd, label in cmds:
            assert label == name
            seen_ops.setdefault(name, set()).add(cmd["op"])
            assert env.apply("Red", cmd).get("status") == "ok", (name, cmd, env.apply("Red", cmd))
        assert ctl.tactical.orders_issued[order] == len(cmds)
    assert seen_ops["hold"] == {"stop"} and seen_ops["attack"] == {"move"} and seen_ops["focus"] == {"order"} and seen_ops["retreat"] == {"move"}
