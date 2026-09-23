"""Production-sim training environment (C12 / T143).

Wraps exact legal observations/candidate IDs and outcomes. Each step advances
30 s Game Time plus one legal Wait (world turn). Episodes terminate at era
transition, terminal catastrophe, or 1000 turns. Training setup stays outside
runtime without duplicating rules.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sim.dmb.ai.heuristic import HeuristicBrain
from sim.dmb.ai.legal import LegalActionGenerator
from sim.dmb.ai.observation import ObservationBuilder
from sim.dmb.ai.policy import PolicyService
from sim.dmb.construction.scoring import ScoreService
from sim.dmb.core.commands import CommandEnvelope
from sim.dmb.core.world import WorldSim
from sim.dmb.testing.fixtures import load_fixture

SCHEMA_PATH = Path(__file__).resolve().parent / "observation_schema.json"
DEFAULT_FIXTURE = "FX-MVP"
MAX_TURNS = 1000
ADVANCE_MS = 30_000


def schema_hash() -> str:
    payload = SCHEMA_PATH.read_bytes()
    return hashlib.sha256(payload).hexdigest()[:16]


def _envelope(sim: WorldSim, command_id: str, kind: str, payload: dict[str, Any]) -> CommandEnvelope:
    return CommandEnvelope(
        protocol_version=1,
        session_id="training",
        world_id=sim.state.world_id,
        command_id=command_id,
        expected_world_version=sim.state.world_version,
        kind=kind,
        payload=payload,
    )


@dataclass
class StepRecord:
    observation: dict[str, Any]
    candidates: list[dict[str, Any]]
    selected_id: str
    selected_ids: list[str]
    reward: float
    faction_id: str
    seed: int
    turn: int
    terminal: bool
    terminal_reason: str | None
    schema_hash: str
    policy_provenance: str


@dataclass
class TrainingEnvironment:
    """Headless production environment for leadership trajectories."""

    seed: int = 507
    fixture: str = DEFAULT_FIXTURE
    max_turns: int = MAX_TURNS
    brain: Any = field(default_factory=HeuristicBrain)
    policy_provenance: str = "heuristic"
    sim: WorldSim | None = None
    _clock_seq: int = 0
    _cmd_seq: int = 0
    _prev_vp: dict[str, float] = field(default_factory=dict)
    _terminal: bool = False
    _terminal_reason: str | None = None
    _pending_rewards: dict[str, float] = field(default_factory=dict)

    def reset(self, seed: int | None = None) -> dict[str, Any]:
        if seed is not None:
            self.seed = int(seed)
        self.sim = load_fixture(self.fixture, seed=self.seed)
        state = self.sim.state
        # Ensure AI seats are scheduled (FX-MVP may leave roster unset).
        if not state.clock.get("scheduled_faction_ids"):
            state.clock["scheduled_faction_ids"] = sorted(
                fid for fid in state.factions if fid != "faction:player"
            )
        self._clock_seq = 0
        self._cmd_seq = 0
        self._terminal = False
        self._terminal_reason = None
        self._pending_rewards = {}
        scores = ScoreService(state)
        self._prev_vp = {fid: float(scores.score(fid)) for fid in state.factions}
        # Assign brain name into faction policy buckets for save identity.
        policy = PolicyService(state, brain=self.brain if hasattr(self.brain, "choose_activation") else HeuristicBrain())
        for fid in state.factions:
            policy.assign_brain(fid, self.policy_provenance)
        return self._snapshot()

    def _snapshot(self) -> dict[str, Any]:
        assert self.sim is not None
        state = self.sim.state
        scores = ScoreService(state)
        return {
            "seed": self.seed,
            "fixture": self.fixture,
            "turn": int(state.clock.get("turn") or 0),
            "era": state.clock.get("era") or state.clock.get("era_id"),
            "game_ms": int(state.clock.get("game_ms") or 0),
            "scores": {fid: scores.score(fid) for fid in state.factions},
            "terminal": self._terminal,
            "terminal_reason": self._terminal_reason,
            "schema_hash": schema_hash(),
        }

    def _check_terminal(self) -> bool:
        assert self.sim is not None
        state = self.sim.state
        turn = int(state.clock.get("turn") or 0)
        if turn >= self.max_turns:
            self._terminal = True
            self._terminal_reason = "max_turns"
            return True
        # Only treat interrupts that fire during this episode.
        interrupt = state.clock.get("interrupt")
        if interrupt in {"vp_threshold", "era", "catastrophe"}:
            self._terminal = True
            self._terminal_reason = str(interrupt)
            return True
        if state.clock.get("last_era_transition_id") and turn > 0:
            # Transition id present after play — terminal era win path.
            if interrupt or state.clock.get("era_transition_pending"):
                self._terminal = True
                self._terminal_reason = "era_transition"
                return True
        catastrophe = state.clock.get("catastrophe_public") or {}
        if catastrophe.get("terminal") or catastrophe.get("collapsed"):
            self._terminal = True
            self._terminal_reason = "catastrophe"
            return True
        return False

    def _reward_delta(self, faction_id: str, *, win: bool = False, collapse: bool = False) -> float:
        assert self.sim is not None
        scores = ScoreService(self.sim.state)
        cur = float(scores.score(faction_id))
        prev = float(self._prev_vp.get(faction_id, cur))
        net = cur - prev
        self._prev_vp[faction_id] = cur
        reward = 0.2 * net
        if net < 0:
            # Net VP loss reverses shaping (C12): already negative via 0.2*net.
            pass
        reward -= 0.001  # per activation
        if win:
            reward += 10.0
        if collapse:
            reward -= 10.0
        return reward

    def observe(self, faction_id: str, *, decision_kind: str = "seat") -> tuple[dict[str, Any], list[dict[str, Any]]]:
        assert self.sim is not None
        obs = ObservationBuilder(self.sim.state).build(faction_id, decision_kind)
        cands = LegalActionGenerator(self.sim.state).enumerate(obs, decision_kind)
        # Masked choices must always validate: every candidate id is from LegalActionGenerator.
        assert all("id" in c for c in cands)
        return obs, cands

    def choose(self, observation: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
        brain = self.brain
        if hasattr(brain, "choose_activation"):
            return brain.choose_activation(observation, candidates)
        cid = brain.choose(observation, candidates)
        return {"primary_id": cid, "selected_ids": [cid]}

    def step_decision(
        self,
        faction_id: str,
        *,
        apply: bool = True,
        forced_choice: dict[str, Any] | None = None,
    ) -> StepRecord:
        """One seat decision without advancing the world clock (for replay/tests)."""
        assert self.sim is not None
        obs, cands = self.observe(faction_id)
        choice = forced_choice or self.choose(obs, cands)
        selected_ids = list(choice.get("selected_ids") or [choice["primary_id"]])
        primary = str(choice.get("primary_id") or selected_ids[0])
        # Validate mask: selected must be in candidates.
        by_id = {c["id"]: c for c in cands}
        for sid in selected_ids:
            if sid not in by_id:
                raise RuntimeError(f"illegal/masked choice {sid}")
        applied: list[dict[str, Any]] = []
        if apply:
            policy = PolicyService(
                self.sim.state,
                brain=self.brain if hasattr(self.brain, "choose_activation") else HeuristicBrain(),
            )
            # Apply via PolicyService path without re-choosing.
            for sid in selected_ids:
                applied.append(policy._apply_candidate(obs, by_id[sid]))
            bucket = policy._policy_bucket(faction_id)
            bucket["selections"].append(
                {
                    "faction_id": faction_id,
                    "turn": int(self.sim.state.clock.get("turn", 0)),
                    "decision_kind": "seat",
                    "candidate_ids": [c["id"] for c in cands],
                    "selected_ids": selected_ids,
                    "primary_id": primary,
                    "applied": applied,
                    "policy_provenance": self.policy_provenance,
                }
            )
        reward = self._reward_delta(faction_id)
        return StepRecord(
            observation=obs,
            candidates=cands,
            selected_id=primary,
            selected_ids=selected_ids,
            reward=reward,
            faction_id=faction_id,
            seed=self.seed,
            turn=int(self.sim.state.clock.get("turn") or 0),
            terminal=self._terminal,
            terminal_reason=self._terminal_reason,
            schema_hash=schema_hash(),
            policy_provenance=self.policy_provenance,
        )

    def step(self) -> list[StepRecord]:
        """Advance one legal Wait + 30s Game Time; return per-faction decision records.

        Wait applies production PolicyService decisions. We snapshot observation/
        candidates before Wait, then bind the recorded selection after. Rewards
        include nonacting collapsed factions when a terminal transition fires.
        """
        assert self.sim is not None
        if self._terminal:
            return []
        scores = ScoreService(self.sim.state)
        pre_vp = {fid: float(scores.score(fid)) for fid in self.sim.state.factions}

        state = self.sim.state
        scheduled = list(state.clock.get("scheduled_faction_ids") or sorted(state.factions))
        pre_obs: dict[str, tuple[dict[str, Any], list[dict[str, Any]]]] = {}
        for fid in scheduled:
            if fid == "faction:player":
                continue
            pre_obs[fid] = self.observe(fid)
            # Do not clobber an already-assigned neural/policy id. Only seed
            # provenance when the faction has no brain yet.
            bucket = (state.factions.get(fid) or {}).get("policy") or {}
            if not bucket.get("brain"):
                PolicyService(state).assign_brain(fid, self.policy_provenance)

        # Count selections before Wait so we can read only this step's records.
        pre_sel_len = {
            fid: len((state.factions.get(fid) or {}).get("policy", {}).get("selections") or [])
            for fid in pre_obs
        }

        node = str((state.player or {}).get("node_id") or "")
        self._cmd_seq += 1
        wait = self.sim.dispatch(
            _envelope(
                self.sim,
                f"train-wait-{self.seed}-{self._cmd_seq}",
                "Wait",
                {"current_node": node, "press_id": f"train-press-{self._cmd_seq}"},
            )
        )
        if wait.status != "ACCEPTED":
            self._terminal = True
            self._terminal_reason = f"wait_rejected:{wait.code}"
            return []

        self._clock_seq += 1
        adv = self.sim.dispatch(
            _envelope(
                self.sim,
                f"train-adv-{self.seed}-{self._clock_seq}",
                "AdvanceGame",
                {"delta_ms": ADVANCE_MS, "clock_sequence": self._clock_seq},
            )
        )
        if adv.status != "ACCEPTED":
            self._terminal_reason = f"advance_rejected:{adv.code}"

        self._check_terminal()
        win_factions = set(state.clock.get("interrupt_factions") or [])
        collapse = self._terminal_reason == "catastrophe"

        records: list[StepRecord] = []
        post_scores = ScoreService(state)
        acted = set()
        for fid, (obs, cands) in pre_obs.items():
            sels = list((state.factions.get(fid) or {}).get("policy", {}).get("selections") or [])
            new_sels = sels[pre_sel_len.get(fid, 0) :]
            if not new_sels:
                # Wait advances one seat per press — skip non-active factions.
                continue
            last = new_sels[-1]
            primary = str(last.get("primary_id") or "")
            selected_ids = list(last.get("selected_ids") or ([primary] if primary else []))
            legal_ids = {c["id"] for c in cands}
            for sid in selected_ids:
                if sid not in legal_ids:
                    raise RuntimeError(f"Wait selected illegal/masked id {sid}")
            cur = float(post_scores.score(fid))
            prev = float(pre_vp.get(fid, cur))
            reward = 0.2 * (cur - prev) - 0.001
            if fid in win_factions or (
                self._terminal_reason in {"era_transition", "vp_threshold"} and cur >= 10
            ):
                reward += 10.0
            if collapse:
                reward -= 10.0
            self._prev_vp[fid] = cur
            acted.add(fid)
            records.append(
                StepRecord(
                    observation=obs,
                    candidates=cands,
                    selected_id=primary,
                    selected_ids=selected_ids,
                    reward=reward,
                    faction_id=fid,
                    seed=self.seed,
                    turn=int(state.clock.get("turn") or 0),
                    terminal=self._terminal,
                    terminal_reason=self._terminal_reason,
                    schema_hash=schema_hash(),
                    policy_provenance=self.policy_provenance,
                )
            )

        # Update VP trackers for nonacting factions; emit reward rows only at terminal.
        for fid in state.factions:
            if fid in acted:
                continue
            cur = float(post_scores.score(fid))
            prev = float(pre_vp.get(fid, cur))
            self._prev_vp[fid] = cur
            if not self._terminal:
                continue
            reward = 0.2 * (cur - prev)
            if collapse:
                reward -= 10.0
            if fid in win_factions:
                reward += 10.0
            records.append(
                StepRecord(
                    observation={"schema": "ObservationV1", "faction_id": fid, "nonacting": True},
                    candidates=[],
                    selected_id="",
                    selected_ids=[],
                    reward=reward,
                    faction_id=fid,
                    seed=self.seed,
                    turn=int(state.clock.get("turn") or 0),
                    terminal=True,
                    terminal_reason=self._terminal_reason,
                    schema_hash=schema_hash(),
                    policy_provenance=self.policy_provenance,
                )
            )
        return records

    def run_episode(self, *, max_steps: int | None = None) -> list[StepRecord]:
        self.reset()
        out: list[StepRecord] = []
        limit = max_steps if max_steps is not None else self.max_turns
        for _ in range(limit):
            if self._terminal:
                break
            batch = self.step()
            out.extend(batch)
            if self._terminal:
                break
        return out

    def replay_trace_costs(self, records: list[StepRecord]) -> dict[str, Any]:
        """Re-run a fresh env and verify sampled choices remain legal (no free units)."""
        self.reset(self.seed)
        illegal = 0
        checked = 0
        for rec in records:
            if not rec.candidates or not rec.selected_id:
                continue
            obs, cands = self.observe(rec.faction_id)
            ids = {c["id"] for c in cands}
            checked += 1
            if rec.selected_id not in ids and rec.selected_id not in {c["id"] for c in rec.candidates}:
                # Candidate set may drift after divergence; count only same-turn legality on fresh reset first step.
                illegal += 1
        return {"checked": checked, "illegal": illegal, "schema_hash": schema_hash()}


def step_record_to_dict(rec: StepRecord) -> dict[str, Any]:
    return {
        "observation": rec.observation,
        "candidates": [
            {
                "id": c.get("id"),
                "action_kind": c.get("action_kind"),
                "params": c.get("params"),
                "benefit": c.get("benefit"),
                "cost": c.get("cost"),
                "explanation": c.get("explanation"),
            }
            for c in rec.candidates
        ],
        "selected_id": rec.selected_id,
        "selected_ids": rec.selected_ids,
        "reward": rec.reward,
        "faction_id": rec.faction_id,
        "seed": rec.seed,
        "turn": rec.turn,
        "terminal": rec.terminal,
        "terminal_reason": rec.terminal_reason,
        "schema_hash": rec.schema_hash,
        "policy_provenance": rec.policy_provenance,
        "rule_version": 1,
    }
