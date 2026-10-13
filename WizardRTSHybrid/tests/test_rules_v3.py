"""Core rule consistency (13 Oct 2026): v2 drafting by default, settings across saves/resets, collective loss as a recorded terminal state."""
from __future__ import annotations

import pickle

from wizard_rts import draft, history, regions, tech, vp
from wizard_rts.sim_api import HybridEnv
from wizard_rts.world import HybridWorld


def _world(profile="campaign", **kw):
    w = HybridWorld(507, profile=profile, **kw)
    w.ai_enabled = False
    w._seq = 0
    return w


def _run(w, seconds):
    for _ in range(int(seconds)):
        w._seq = getattr(w, "_seq", 0) + 1
        w.advance(1000, int(w.dmb.clock.get("clock_sequence", 0)) + 1, snapshot=False)


def _collapse(w):
    rg = regions.state(w)
    w.loss_outbreaks_per_era = 2
    for _ in range(2):
        rg.cubes[0] = regions.const("cube_cap")
        regions._add_cube(w, rg, 0, 0, "test")
    _run(w, 1)
    assert w.collective_loss


def test_default_campaign_world_drafts_v2_and_a_draft_phase_opens():
    w = _world()
    _run(w, 2)
    assert draft.enabled(w) and draft.state(w)["era"] == 0 and draft.state(w)["round"] == 0
    assert all(len(w.tech[f]["offers"]) == 7 for f in w.faction_info)


def test_save_and_load_keep_the_rules_active():
    w = _world()
    _run(w, 5)
    w2 = pickle.loads(pickle.dumps(w))
    assert w2.cardset == "v2" and w2.draft_v2 and draft.enabled(w2) and w2.state_hash() == w.state_hash()


def test_cycle_reset_carries_every_rule_setting():
    w = _world()
    w.era_vp_end, w.era_vp_step, w.loss_outbreaks_total, w.diplomacy_enabled = 9, 3, 5, True
    w.nest_policy = {"Red": "coop"}
    fresh = history.cycle_reset(w)
    assert fresh.cardset == "v2" and fresh.draft_v2 and (fresh.era_vp_end, fresh.era_vp_step, fresh.loss_outbreaks_total) == (9, 3, 5)
    assert fresh.diplomacy_enabled and fresh.nest_policy == {"Red": "coop"} and fresh.nest_policy is not w.nest_policy
    legacy = _world(legacy_draft=True)
    assert history.cycle_reset(legacy).__dict__.get("draft_v2") is None and history.cycle_reset(legacy).legacy_draft


def test_collective_loss_is_terminal_recorded_and_stops_time():
    w = _world(profile="developer")
    _collapse(w)
    out = history.outcome(w)
    assert out["result"] == "collective_loss" and out["winner"] == "" and set(out["losers"]) == set(w.faction_info)
    ms = w.dmb.clock["game_ms"]
    r = w.advance(1000, int(w.dmb.clock.get("clock_sequence", 0)) + 1, snapshot=False)
    assert r["status"] == "terminal" and r["terminal"]["result"] == "collective_loss" and w.dmb.clock["game_ms"] == ms
    fresh = history.cycle_reset(w)
    assert fresh.past_cycles[-1]["outcome"]["result"] == "collective_loss" and history.snapshot(fresh)["past"][-1]["outcome"] == "collective_loss"
    assert not getattr(fresh, "collective_loss", False) and fresh.draft_v2


def test_headless_env_reports_collective_loss_to_every_agent():
    env = HybridEnv(507, agent_factions=("Red", "Blue"), step_ms=1000)
    env.reset()
    _collapse(env.world)
    _obs, rew, term, _trunc, info = env.step({})
    assert all(term.values()) and info["episode_over"] and info["outcome"]["result"] == "collective_loss" and all(rew[f] < 0 for f in rew)


def test_loss_limits_hold_in_every_era():
    for era in range(4):
        w = _world(profile="developer")
        w.era_index = era
        vp.era_state(w)["index"] = era
        _collapse(w)
        assert regions.state(w).lost_by in ("era", "total") and history.outcome(w)["result"] == "collective_loss"
