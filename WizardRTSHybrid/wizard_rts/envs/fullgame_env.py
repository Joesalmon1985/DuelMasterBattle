"""Cross-system environment (owner section D.6): one real HybridWorld in which the wizard must decide, minute by minute, between
finishing a settlement's story (talk -> gallery -> four puzzles -> the warden's duel -> a reopened gallery) and treating the outbreaks
that grow while he is underground. Everything is the real thing: the dry mine, the person, the generated dungeon, the Mastermind duel,
the hex-region cubes, one clock. The outbreak cadence is scaled up so the two crises genuinely compete.

Actions are macro-skills (each a script of real wizard ops that costs game time exactly as the ops would): `wait`, `social` (find the
miner, learn the story, take the sigil, persuade), `puzzles` (enter the gallery and answer all four rooms), `duel` (break the warden's
code; world time is frozen), `leave` (walk out), and `treat(k)` for the k-th inhabited region. Observations are partial: cubes are known
only where the wizard is, next to it, or where a settlement's healer reports them.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from wizard_rts import dungeon_agent as D
from wizard_rts import regions, story, story_agent as A
from wizard_rts.envs import Env
from wizard_rts.envs._world_cache import attention_advance, prepared
from wizard_rts.puzzle.dungeon import DungeonRun

N_TREAT = 8
VERBS = ["wait", "social", "puzzles", "duel", "leave"] + ["treat%d" % k for k in range(N_TREAT)]
N = len(VERBS)
V = {v: i for i, v in enumerate(VERBS)}
STAGES = ["start", "sigil", "inside", "answered", "duelled", "closed"]
WALK = 1.4


class _TimedActor(A.WorldActor):
    """Every dungeon move or interaction costs one game second (the world keeps living underground)."""

    def __init__(self, world: Any, economy: bool) -> None:
        super().__init__(world)
        self.economy = economy

    def move(self, dx: int, dy: int) -> dict[str, Any]:
        r = super().move(dx, dy)
        attention_advance(self.world, 1, self.economy)
        return r

    def interact(self, entity: str, item: str | None = None, spell: int | None = None) -> dict[str, Any]:
        r = super().interact(entity, item, spell)
        attention_advance(self.world, 1, self.economy)
        return r


class FullGameEnv(Env):
    name = "fullgame"
    max_steps = 80

    def __init__(self, horizon_min: int = 40, interval_scale: float = 0.3, economy: bool = False) -> None:
        super().__init__()
        self.horizon_ms, self.scale, self.economy = horizon_min * 60_000, interval_scale, economy
        self.w: Any = None
        self.ids: dict[str, Any] = {}

    def _reset(self, **scenario: Any) -> None:
        self.w, self.ids = prepared(self.seed % 6, "story_outbreak")
        self.w.seed += 1000 * (self.seed // 6)  # the same prepared map and story, a different outbreak sequence per episode seed
        self.w.outbreak_interval_scale = float(scenario.get("interval_scale", self.scale))
        self.w.outbreaks_enabled = True
        rg = regions.state(self.w)
        rg.next_cube_ms = int(self.w.dmb.clock["game_ms"]) + int(regions.const("interval_ms") * self.w.outbreak_interval_scale)
        rg.next_spread_ms = int(self.w.dmb.clock["game_ms"]) + regions.const("spread_ms")
        self.t0 = int(self.w.dmb.clock["game_ms"])
        self.stage = 0
        self._prev_out, self._prev_treated = rg.outbreaks, rg.treated
        self.story_reward_paid = False

    # ---- helpers
    def _rg(self) -> regions.Regions:
        return regions.state(self.w)

    def _inhabited(self) -> list[int]:
        rg = self._rg()
        return sorted({rg.region_at(r["tile"][0], r["tile"][1]) for r in self.w.dmb.settlements.values() if r["state"] == "standing"})

    def _treat_targets(self) -> list[int]:
        """Regions the wizard can choose to treat: the inhabited ones first (sorted by index), at most N_TREAT."""
        return self._inhabited()[:N_TREAT]

    def _known(self) -> set[int]:
        rg, w = self._rg(), self.w
        here = rg.region_at(w.player["tx"], w.player["ty"])
        known = {here} | set(rg.neighbours[here])
        for i in self._inhabited():
            if rg.cubes[i] >= 2:
                known.add(i)
        return known

    def _time(self) -> int:
        return int(self.w.dmb.clock["game_ms"]) - self.t0

    def _q(self) -> tuple[str, dict] | None:
        for qid, q in sorted(story.state(self.w)["quests"].items()):
            if q.get("family") != "outbreak":
                return qid, q
        return None

    def _quest_status(self) -> str:
        qq = self._q()
        return self.w.dmb.quests[qq[0]]["status"] if qq else "none"

    # ---- legality
    def legal_mask(self) -> np.ndarray:
        m = np.zeros(N)
        m[V["wait"]] = 1
        st = self.stage
        open_ = self._quest_status() in ("offered", "active", "suspended")
        if st == 0 and open_:
            m[V["social"]] = 1
        if st == 1 and open_:
            m[V["puzzles"]] = 1
        if st == 3 and story.state(self.w)["in_dungeon"]:
            m[V["duel"]] = 1
        if st >= 3 and story.state(self.w)["in_dungeon"] and not story.state(self.w)["duel"]:
            m[V["leave"]] = 1
        if not story.state(self.w)["in_dungeon"]:
            known = self._known()
            for k, i in enumerate(self._treat_targets()):
                if i in known and self._rg().cubes[i] > 0:
                    m[V["treat%d" % k]] = 1
        return m

    def is_legal(self, action: Any) -> bool:
        a = int(action)
        return 0 <= a < N and bool(self.legal_mask()[a]) and not self.done

    def legal_actions(self) -> list[Any]:
        return [i for i, m in enumerate(self.legal_mask()) if m > 0]

    # ---- skills
    def _social(self) -> None:
        q = self._q()
        npc = q[1]["npc"]
        tile = story.state(self.w)["npcs"][npc]["tile"]
        p = self.w.player
        attention_advance(self.w, (abs(p["tx"] - tile[0]) + abs(p["ty"] - tile[1])) / WALK, self.economy)
        A.place_wizard_near(self.w, tile)
        for c in ("ask_cause", "ask_gallery", "accept_help", "persuade"):
            A.op(self.w, "choose", npc=npc, choice=c)
            attention_advance(self.w, 2, self.economy)
        self.stage = 1

    def _puzzles(self) -> None:
        q = self._q()
        d = story.state(self.w)["dungeons"][q[1]["dungeon"]]
        tile = d["entrance"]["tile"]
        p = self.w.player
        attention_advance(self.w, (abs(p["tx"] - tile[0]) + abs(p["ty"] - tile[1])) / WALK, self.economy)
        A.place_wizard_near(self.w, tile)
        res = A.op(self.w, "enter", dungeon=q[1]["dungeon"])
        if res["status"] != "ok":
            return
        self.stage = 2
        D.solve_dungeon(_TimedActor(self.w, self.economy))
        view = story.dungeon_view(self.w)
        reward = next(e for e in view["entities"] if e["id"].endswith("_reward"))
        D.go_adjacent(_TimedActor(self.w, self.economy), tuple(reward["pos"]))
        self.stage = 3

    def _duel(self) -> None:
        res = A.break_the_code(self.w)  # world time is frozen while the duel is open: no attention_advance
        self.stage = 4

    def _leave(self) -> None:
        view = story.dungeon_view(self.w)
        exit_pos = tuple(next(e for e in view["entities"] if e["kind"] == "exit")["pos"])
        actor = _TimedActor(self.w, self.economy)
        D.walk(actor, D.bfs(actor.view(), None, exit_pos))
        self.stage = 5

    def _treat(self, k: int) -> None:
        i = self._treat_targets()[k]
        rg, w = self._rg(), self.w
        tile = self._region_tile(i)
        p = w.player
        attention_advance(w, (abs(p["tx"] - tile[0]) + abs(p["ty"] - tile[1])) / WALK, self.economy)
        w.player["tx"], w.player["ty"] = tile
        res = regions.begin_treatment(w)
        if res["status"] == "rejected" and res.get("reason") == "recovering":
            attention_advance(w, res["ready_in_ms"] / 1000.0, self.economy)
            res = regions.begin_treatment(w)
        if res["status"] == "started":
            attention_advance(w, regions.const("treat_ms") / 1000.0 + 1, self.economy)
        else:
            attention_advance(w, 2, self.economy)

    def _region_tile(self, i: int) -> tuple[int, int]:
        for rec in sorted(self.w.dmb.settlements.values(), key=lambda r: r["id"]):
            if self._rg().region_at(rec["tile"][0], rec["tile"][1]) == i and rec["state"] == "standing":
                return int(rec["tile"][0]) + 1, int(rec["tile"][1]) + 1
        return int(self.w.player["tx"]), int(self.w.player["ty"])

    def _step(self, action: Any) -> tuple[float, dict[str, Any]]:
        v = VERBS[int(action)]
        rg = self._rg()
        if v == "wait":
            attention_advance(self.w, 30, self.economy)
        elif v == "social":
            self._social()
        elif v == "puzzles":
            self._puzzles()
        elif v == "duel":
            self._duel()
        elif v == "leave":
            self._leave()
        else:
            self._treat(int(v[5:]))
        d_out, d_tr = rg.outbreaks - self._prev_out, rg.treated - self._prev_treated
        self._prev_out, self._prev_treated = rg.outbreaks, rg.treated
        r = -1.5 * d_out + 0.1 * d_tr - 0.002 * float(sum(rg.cubes))
        qs = self._quest_status()
        if qs == "completed" and not self.story_reward_paid:
            self.story_reward_paid = True
            q = self._q()[1]
            r += 3.0 if q["outcome"] == "full" else 1.2
            self.stage = 4
        if rg.lost:
            self.done, self.reason = True, "terminal_loss"
            r -= 5.0
        elif self._time() >= self.horizon_ms:
            self.done, self.reason = True, "horizon"
        elif qs in ("failed_with_consequence", "resolved_by_world") and not self._any_cubes() and self.stage >= 5:
            pass
        return r, {"outbreaks": rg.outbreaks, "treated": rg.treated, "stage": STAGES[self.stage], "quest": qs}

    def _any_cubes(self) -> bool:
        return any(self._rg().cubes)

    # ---- observation
    def observe(self) -> dict[str, Any]:
        rg, w = self._rg(), self.w
        known = self._known()
        return {"stage": STAGES[self.stage], "cubes": [(rg.cubes[i] if i in known else -1) for i in range(len(rg.cubes))], "outbreaks": rg.outbreaks,
                "minutes": self._time() // 60_000, "targets": self._treat_targets(), "here": rg.region_at(w.player["tx"], w.player["ty"]),
                "quest": self._quest_status(), "inside": bool(story.state(w)["in_dungeon"])}

    def encode(self, obs: dict[str, Any] | None = None) -> np.ndarray:
        obs = obs or self.observe()
        R = len(obs["cubes"])
        cubes = np.array(obs["cubes"], float)
        stage = np.zeros(len(STAGES))
        stage[STAGES.index(obs["stage"])] = 1
        tgt = np.zeros(N_TREAT)
        tcub = np.zeros(N_TREAT)
        for k, i in enumerate(obs["targets"][:N_TREAT]):
            tgt[k] = 1
            tcub[k] = max(0, cubes[i]) / 3.0
        return np.concatenate([stage, tcub, tgt, [max(0, cubes.max()) / 3.0, np.maximum(cubes, 0).sum() / 12.0, obs["outbreaks"] / 8.0, obs["minutes"] / 40.0, 1.0 if obs["inside"] else 0.0]])

    def state(self) -> Any:
        rg = self._rg()
        return {"seed": self.seed, "t": self.t, "ms": self._time(), "stage": self.stage, "cubes": list(rg.cubes), "outbreaks": rg.outbreaks, "treated": rg.treated,
                "quest": self._quest_status(), "inv": list(story.state(self.w)["inventory"]), "done": self.done, "reason": self.reason}


# ---------------------------------------------------------------- baselines

def _story_next(env: FullGameEnv) -> int | None:
    m = env.legal_mask()
    for v in ("social", "puzzles", "duel", "leave"):
        if m[V[v]]:
            return V[v]
    return None


def _treat_worst(env: FullGameEnv) -> int | None:
    m = env.legal_mask()
    best, key = None, None
    obs = env.observe()
    for k in range(N_TREAT):
        if m[V["treat%d" % k]]:
            i = obs["targets"][k]
            kk = (-obs["cubes"][i], k)
            if key is None or kk < key:
                best, key = V["treat%d" % k], kk
    return best


def policy_wait(env: FullGameEnv, obs: dict[str, Any]) -> int:
    return V["wait"]


def policy_story_first(env: FullGameEnv, obs: dict[str, Any]) -> int:
    a = _story_next(env)
    if a is not None:
        return a
    a = _treat_worst(env)
    return a if a is not None else V["wait"]


def policy_treat_first(env: FullGameEnv, obs: dict[str, Any]) -> int:
    a = _treat_worst(env)
    if a is not None:
        return a
    a = _story_next(env)
    return a if a is not None else V["wait"]


def policy_interleaved(threshold: int = 2):
    """Treat when a region has the cap-minus-one cubes, otherwise advance the story: a hand-written prioritiser."""
    def p(env: FullGameEnv, obs: dict[str, Any]) -> int:
        worst = max(obs["cubes"])
        if worst >= threshold:
            a = _treat_worst(env)
            if a is not None:
                return a
        a = _story_next(env)
        if a is not None:
            return a
        a = _treat_worst(env)
        return a if a is not None else V["wait"]
    return p


def run_episode(env: FullGameEnv, policy, seed: int, **scenario: Any) -> dict[str, Any]:
    obs = env.reset(seed, **scenario)
    while not env.done:
        obs, _r, _t, _tr, _i = env.step(policy(env, obs))
    rg = env._rg()
    return {"return": round(env.return_, 3), "reason": env.reason, "quest": env._quest_status(), "outbreaks": rg.outbreaks, "treated": rg.treated, "steps": env.t}
