"""Run one game with controllers in some seats and the heuristic AI in the rest (execution plan T1.5).

`run_episode` builds a HybridEnv with the training rules (campaign profile, generated cards with the era-start draft, diplomacy, cooperative
nest policy), gives every agent seat a controller, calls each controller once per game second with the events since its last call, applies
the commands through HybridEnv.apply (the simulation decides legality), writes a resumable checkpoint every few game minutes, and at the end
validates the books (VP replay, ledger) and scores every seat with neuro/fitness.py.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol

from neuro import fitness as fit
from wizard_rts import history, ledger, regions, vp
from wizard_rts.sim_api import FACTIONS, HybridEnv

HEURISTICS = ("plus", "baseline")


@dataclass
class EpisodeConfig:
    seed: int
    game_minutes: int = 240
    map_size: str = "standard"
    profile: str = "campaign"
    agent_seats: tuple[str, ...] = ()  # factions controlled by controllers
    opponents: dict[str, str] = field(default_factory=dict)  # heuristic seats: faction -> "plus" | "baseline" (default "plus")
    outbreak_interval_scale: float = 1.0  # catastrophe difficulty; the label says which curriculum level this is (N10)
    catastrophe_level: str = "C0"
    diplomacy: bool = True
    nest_policy: str = "coop"
    checkpoint_game_minutes: int = 30
    wall_cap_s: int = 7200
    decision_s: int = 60
    boot_decision_s: int = 20
    boot_minutes: int = 10
    event_min_gap_s: int = 15
    tactical_s: int = 5
    tactical: bool = False
    world_knobs: dict[str, Any] = field(default_factory=dict)  # extra world attributes (a test sets loss_outbreaks_total here); recorded with the run


@dataclass
class SeatResult:
    faction: str
    vp: int
    state: str
    collapsed_at_min: float | None
    fitness: float
    tier: str
    commands: int
    rejected: int


@dataclass
class EpisodeResult:
    seed: int
    catastrophe_level: str
    outbreak_interval_scale: float
    end_reason: str
    t_end_min: float
    outcome: dict
    outbreaks: int
    seats: list[SeatResult]
    control_seats: list[SeatResult]
    state_hash: str
    wall_s: float
    vp_replay_ok: bool
    ledger_ok: bool
    checkpoints: int
    decisions_logged: int


class Controller(Protocol):
    """What the runner needs from a controller. Optional: `attach(env)` (called once the environment exists), `on_results(game_s, commands, replies)`,
    `decisions_logged` (a counter the result reports)."""

    faction: str

    def on_step(self, game_s: int, events: list[dict]) -> list[dict]: ...

    def spawn_for(self, faction: str) -> "Controller": ...


def root_of(world: Any, name: str) -> str:
    """The founding faction a (possibly split-off) faction descends from."""
    seen = 0
    while world.faction_info.get(name, {}).get("parent") and seen < 16:
        name = world.faction_info[name]["parent"]
        seen += 1
    return name


def lineage(world: Any, root: str) -> list[str]:
    return sorted(n for n in world.faction_info if root_of(world, n) == root)


def _collapse_minutes(world: Any) -> dict[str, float]:
    return {c["faction"]: int(c["game_ms"]) / 60000.0 for c in history.state(world)["chronicle"] if c["event"] == "collapsed"}


def _permanent_vp(world: Any, name: str) -> int:
    return sum(1 for e in vp.ledger(world).values() if e["event"] == "destroyed" and e.get("winner") == name)


def _score_seats(world: Any, roots: list[str], end_reason: str, t_end_min: float, horizon_min: float, counts: dict[str, list[int]]) -> list[SeatResult]:
    collapse = _collapse_minutes(world)
    state = history.state(world)["faction"]
    all_roots = [f[0] for f in FACTIONS]
    now_vp = {r: sum(vp.faction_vp(world, n) for n in lineage(world, r)) for r in all_roots}
    cfg = fit.FitnessConfig(horizon_min=horizon_min)
    out = []
    for r in roots:
        members = lineage(world, r)
        dead = all(state.get(n, {}).get("state") == "collapsed" for n in members)
        at = max((collapse[n] for n in members if n in collapse), default=None) if dead else None
        seat_vp = sum(_permanent_vp(world, n) for n in members) if dead else now_vp[r]
        if end_reason == "wall_cap":
            f, tier = 0.0, "V"  # voided: a game cut by the wall clock is replayed, never scored
        else:
            f, tier = fit.seat_fitness(cfg, end_reason, t_end_min, seat_vp, "collapsed" if dead else "active", at, [now_vp[o] for o in all_roots if o != r])
        c = counts.get(r, [0, 0])
        out.append(SeatResult(r, int(seat_vp), "collapsed" if dead else "active", at, round(f, 3), tier, c[0], c[1]))
    return out


def _atomic_write(path: Path, blob: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as fh:
        fh.write(blob)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def run_episode(cfg: EpisodeConfig, controllers: dict[str, Controller], log_dir: Path | None = None, heartbeat: Path | None = None,
                env_hook: Any = None) -> EpisodeResult:
    t0 = time.time()
    names = [f[0] for f in FACTIONS]
    if set(controllers) != set(cfg.agent_seats):
        raise ValueError(f"controllers {sorted(controllers)} do not match agent_seats {sorted(cfg.agent_seats)}")
    for f in cfg.agent_seats:
        if f not in names:
            raise ValueError(f"unknown faction {f}")
    for f, pol in cfg.opponents.items():
        if f in cfg.agent_seats or f not in names or pol not in HEURISTICS:
            raise ValueError(f"opponent {f}: {pol!r} (only heuristic seats can be listed, as one of {HEURISTICS})")
    horizon_s = int(cfg.game_minutes) * 60
    os.environ.setdefault("HYBRID_AI", "1")
    env = HybridEnv(seed=cfg.seed, map_size=cfg.map_size, agent_factions=tuple(cfg.agent_seats), step_ms=1000, max_game_ms=horizon_s * 1000, profile=cfg.profile, rewards=False)
    env.reset()
    w = env.world
    w.cardset, w.draft_v2, w.diplomacy_enabled = "v2", True, bool(cfg.diplomacy)
    w.nest_policy = {n: cfg.nest_policy for n in w.faction_info}
    w.outbreak_interval_scale = float(cfg.outbreak_interval_scale)
    w.ai_policy = {n: cfg.opponents.get(n, "plus") for n in names if n not in cfg.agent_seats}
    for k, v in cfg.world_knobs.items():
        setattr(w, k, v)
    if env_hook is not None:
        env_hook(env)
    for c in controllers.values():
        getattr(c, "attach", lambda _env: None)(env)
    initial = ledger.snapshot_totals(w)
    log_dir = Path(log_dir) if log_dir is not None else None
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
    seat_ctl: dict[str, Controller] = dict(controllers)
    counts: dict[str, list[int]] = {}  # root seat -> [commands, rejected]
    cursor = env.event_cursor()
    new_events: list[dict] = []
    checkpoints = 0
    end_reason = ""
    game_s = 0
    ckpt_every = int(cfg.checkpoint_game_minutes) * 60
    collapsed_state = lambda n: history.state(w)["faction"].get(n, {}).get("state") == "collapsed"  # noqa: E731
    for game_s in range(1, horizon_s + 1):
        actions: dict[str, list[dict]] = {}
        for seat in env.seats():
            if collapsed_state(seat):
                continue
            ctl = seat_ctl.get(seat)
            if ctl is None:  # a split successor: the same controller kind plays it with its own state (N07)
                ctl = seat_ctl[seat] = seat_ctl[root_of(w, seat)].spawn_for(seat)
            cmds = ctl.on_step(game_s - 1, new_events)
            if cmds:
                actions[seat] = cmds
        _obs, _rewards, _term, _trunc, info = env.step(actions, observe=False)
        for seat, replies in info["results"].items():
            c = counts.setdefault(root_of(w, seat), [0, 0])
            c[0] += len(replies)
            c[1] += sum(1 for r in replies if r.get("status") != "ok")
            hook = getattr(seat_ctl.get(seat), "on_results", None)
            if hook is not None:
                hook(game_s - 1, actions.get(seat, []), replies)
        new_events, cursor = env.events_since(cursor)
        if log_dir is not None and game_s % ckpt_every == 0:
            _atomic_write(log_dir / "ckpt.pkl", env.save())
            checkpoints += 1
        if heartbeat is not None and game_s % 60 == 0:
            Path(heartbeat).write_text(f"{game_s} {time.time():.0f}\n")
        if getattr(w, "collective_loss", False):
            end_reason = "collective_loss"
        elif cfg.agent_seats and all(collapsed_state(s) for s in env.seats()):
            end_reason = "agent_collapsed"
        elif env.game_ms >= horizon_s * 1000:
            end_reason = "horizon"
        elif info["episode_over"]:
            end_reason = "last_standing"
        elif cfg.wall_cap_s and time.time() - t0 > cfg.wall_cap_s:
            end_reason = "wall_cap"
        if end_reason:
            break
    t_end_min = env.game_ms / 60000.0
    s = regions.state(w)
    roots = [n for n in names if n in cfg.agent_seats]
    result = EpisodeResult(
        seed=cfg.seed, catastrophe_level=cfg.catastrophe_level, outbreak_interval_scale=float(cfg.outbreak_interval_scale), end_reason=end_reason,
        t_end_min=round(t_end_min, 3), outcome=history.outcome(w), outbreaks=int(s.outbreaks) if s else 0,
        seats=_score_seats(w, roots, end_reason, t_end_min, cfg.game_minutes, counts),
        control_seats=_score_seats(w, [n for n in names if n not in cfg.agent_seats], end_reason, t_end_min, cfg.game_minutes, counts),
        state_hash=env.state_hash(), wall_s=round(time.time() - t0, 2), vp_replay_ok=vp.replay(w) == vp.totals(w), ledger_ok=ledger.check(w, initial) == [],
        checkpoints=checkpoints, decisions_logged=sum(int(getattr(c, "decisions_logged", 0)) for c in seat_ctl.values()),
    )
    if log_dir is not None:
        tmp = log_dir / "result.json.tmp"
        tmp.write_text(json.dumps({"config": asdict(cfg), "result": asdict(result)}, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, log_dir / "result.json")
    return result
