"""The neural controller of one seat (execution plan T3.2; design 4.4, 5.1-5.2).

`Controller.on_step(game_s, events)` is called once per game second by neuro/episode.py. It decides WHEN to think (a strategic tick every `decision_s`, every
`boot_decision_s` during the first `boot_minutes`; an event tick when something the faction must react to happened, at most once per `event_min_gap_s`, on a 5-second
boundary) and WHAT to do (neuro/brain.py scores every candidate; the selection rule below turns scores into commands).

SELECTION RULE. All scores are on one scale. Per tick, in descending score order, the best candidate of each head is issued if its score exceeds the wait score, at
most one per head and at most MAX_COMMANDS (4) per tick. The draft (H6) is exempt from the cap and from the wait comparison: an open offer is always answered with
its best-scored card. A rejected command (the simulator is authoritative) withholds its key for 60 s and the head's next candidate (if it still beats the wait score)
is tried once, one second later. No sampling anywhere: the same genome and seed give the same game (ties keep the candidate generator's order).
"""
from __future__ import annotations

import gzip
import io
import json
import time
import zlib
from pathlib import Path
from typing import Any

import numpy as np

from neuro.brain import Brain, Thought
from neuro.candidates import CandidateGenerator
from neuro.cand_base import Candidate
from neuro.nets import Nets
from neuro.observer import FactionObserver
from neuro.obs_world import EVENT_CATEGORIES

MAX_COMMANDS = 4
TRIGGERS = ("lost_building", "lost_units", "draft", "outbreak", "era", "relation", "caravan_lost")
TRIGGER_IDX = [EVENT_CATEGORIES.index(t) for t in TRIGGERS]
TACTICAL_HEAD = "N11"


class DecisionLog:
    """Gzip JSONL of the decisions of one or several seats (one record per line, keys sorted so identical games give identical bytes)."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._raw = gzip.GzipFile(filename="", mode="wb", fileobj=open(self.path, "wb"), mtime=0)
        self._fh = io.TextIOWrapper(self._raw, encoding="utf-8")
        self.lines = 0

    def write(self, rec: dict) -> None:
        self._fh.write(json.dumps(rec, sort_keys=True, separators=(",", ":"), default=str) + "\n")
        self.lines += 1

    def close(self) -> None:
        if self._fh is not None:
            self._fh.flush()
            fileobj = self._raw.fileobj
            self._fh.close()
            if fileobj is not None and not fileobj.closed:
                fileobj.close()
            self._fh = None  # type: ignore[assignment]

    def __enter__(self) -> "DecisionLog":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def read_log(path: str | Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def key_text(key: tuple) -> str:
    return "|".join(str(k) for k in key)[:80]


class Controller:
    kind = "neural"

    def __init__(self, env: Any, faction: str, nets: Nets, cfg: Any, rng_seed: int = 0, log: DecisionLog | None = None, tactical: Any = None) -> None:
        self.env, self.faction, self.nets, self.cfg, self.seed, self.log = env, faction, nets, cfg, int(rng_seed), log
        self.brain = Brain(nets)
        self.observer: FactionObserver | None = None
        self.gen: CandidateGenerator | None = None
        self.memory = np.zeros(16, dtype=np.float32)
        self.last_tick = -10 ** 9
        self.last_command_s = 0
        self.decisions_logged = 0
        self._retry: list[tuple[Candidate, float]] = []
        self._inflight: list[tuple[Candidate, list[tuple[Candidate, float]], bool]] = []
        self.commands = 0
        self.rejected = 0
        self.by_head: dict[str, list[int]] = {}  # head -> [issued, rejected]
        self.reject_reasons: dict[str, int] = {}
        self.tick_ms: list[float] = []
        self.ticks = 0
        self.tactical = tactical
        if env is not None:
            self.attach(env)

    # ------------------------------------------------------------------------------------------------------------------------ plumbing
    def attach(self, env: Any) -> None:
        self.env = env
        self.observer = FactionObserver(env.world, self.faction)
        self.gen = CandidateGenerator(env, self.faction, self.observer)

    def spawn_for(self, faction: str) -> "Controller":
        """The controller of a split successor: the same genome, its own memory and decision state (N07)."""
        sub = Controller(None, faction, self.nets, self.cfg, self.seed ^ zlib.crc32(faction.encode()), self.log, self.tactical)
        sub.attach(self.env)
        return sub

    # ------------------------------------------------------------------------------------------------------------------------ scheduler
    def _due(self, game_s: int) -> str:
        """'' (nothing), 'strategic' or 'event:<kinds>'."""
        gap = self.cfg.boot_decision_s if game_s < self.cfg.boot_minutes * 60 else self.cfg.decision_s
        since = game_s - self.last_tick
        if since >= gap:
            return "strategic"
        counts = self.observer.event_counts
        if since >= self.cfg.event_min_gap_s and game_s % 5 == 0:
            hit = [t for t, i in zip(TRIGGERS, TRIGGER_IDX) if counts[i] > 0]
            if hit:
                return "event:" + ",".join(hit)
        return ""

    def on_step(self, game_s: int, events: list[dict]) -> list[dict]:
        if self.observer is None:
            raise RuntimeError("controller used before attach(env)")
        if events:
            self.observer.on_events(events)
        out: list[dict] = []
        self._inflight = []
        if self._retry:
            for cand, wait in self._retry:
                self._inflight.append((cand, [], True))
                out.append(cand.action)
            self._retry = []
        trigger = self._due(game_s)
        if trigger:
            out += self._tick(game_s, trigger)
        if out:
            self.last_command_s = game_s
        return out

    # ------------------------------------------------------------------------------------------------------------------------ one decision
    def _tick(self, game_s: int, trigger: str) -> list[dict]:
        t0 = time.perf_counter()
        self.last_tick = game_s
        obs = self.observer.observe(game_s)
        cands = self.gen.all(obs)
        th = self.brain.think(obs, cands, self.memory, (game_s - self.last_command_s) / 60.0)
        self.memory = th.memory
        chosen = self._select(cands, th)
        cmds = []
        for cand, rest in chosen:
            self._inflight.append((cand, rest, False))
            cmds.append(cand.action)
        self.ticks += 1
        self.tick_ms.append((time.perf_counter() - t0) * 1000.0)
        if self.log is not None:
            self._record(game_s, trigger, cands, th, chosen)
        return cmds

    def _select(self, cands: dict[str, list[Candidate]], th: Thought) -> list[tuple[Candidate, list[tuple[Candidate, float]]]]:
        """[(candidate, the head's next candidates with their scores, best first)] in issue order."""
        ranked: list[tuple[float, str, Candidate, list[tuple[Candidate, float]]]] = []
        for head, lst in cands.items():
            if not lst:
                continue
            sc = th.scores[head]
            order = np.argsort(-sc, kind="stable")
            best = int(order[0])
            rest = [(lst[int(i)], float(sc[int(i)])) for i in order[1:4] if float(sc[int(i)]) > th.wait]
            ranked.append((float(sc[best]), head, lst[best], rest))
        ranked.sort(key=lambda t: (-t[0], t[1]))
        out, n = [], 0
        for score, head, cand, rest in ranked:
            if head == "H6":
                out.append((cand, []))
            elif score > th.wait and n < MAX_COMMANDS:
                out.append((cand, rest))
                n += 1
        out.sort(key=lambda t: 0 if t[0].head == "H6" else 1)  # answer the draft first; stable for the rest
        return out

    # ------------------------------------------------------------------------------------------------------------------------ results
    def on_results(self, game_s: int, commands: list[dict], replies: list[dict]) -> None:
        """Replies come back in command order. A rejection withholds the key and queues the head's next candidate (once; never a retry of a retry)."""
        for (cand, rest, was_retry), r in zip(self._inflight, replies):
            st = self.by_head.setdefault(cand.head, [0, 0])
            st[0] += 1
            self.commands += 1
            if r.get("status") == "ok":
                continue
            reason = str(r.get("reason", "?"))
            st[1] += 1
            self.rejected += 1
            self.reject_reasons[reason] = self.reject_reasons.get(reason, 0) + 1
            self.gen.note_rejection(cand, reason, game_s)
            if not was_retry and rest:
                self._retry.append(rest[0])
        if self.log is not None and self._inflight:
            self.log.write({"s": game_s, "seat": self.faction, "ack": [("ok" if r.get("status") == "ok" else str(r.get("reason", "?"))) for r in replies]})

    # ------------------------------------------------------------------------------------------------------------------------ logging
    def _record(self, game_s: int, trigger: str, cands: dict[str, list[Candidate]], th: Thought, chosen: list) -> None:
        heads = {}
        picked = {c.key for c, _ in chosen}
        for h, lst in cands.items():
            if not lst:
                continue
            sc = th.scores[h]
            order = np.argsort(-sc, kind="stable")[:4]
            heads[h] = {"n": len(lst), "top": [[key_text(lst[int(i)].key), round(float(sc[int(i)]), 4), lst[int(i)].key in picked] for i in order]}
        self.log.write({"s": game_s, "seat": self.faction, "trigger": trigger, "wait": round(th.wait, 4), "heads": heads,
                        "cmds": [c.action for c, _ in chosen]})
        self.decisions_logged += 1

    def stats(self) -> dict:
        t = np.asarray(self.tick_ms) if self.tick_ms else np.zeros(1)
        return {"ticks": self.ticks, "commands": self.commands, "rejected": self.rejected, "by_head": self.by_head, "reject_reasons": dict(sorted(self.reject_reasons.items())),
                "tick_ms_mean": float(t.mean()), "tick_ms_max": float(t.max())}
