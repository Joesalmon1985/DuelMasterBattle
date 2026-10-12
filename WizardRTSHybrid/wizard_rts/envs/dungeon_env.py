"""Dungeon exploration environment: render-independent, the same puzzle and map code as the game (ported GDScript, parity-tested).

The wizard moves tile by tile, selects an inventory item or a spell exactly as the Godot UI keys do (number keys, Q/F/R) and interacts
with the entity next to him. The observation is what he sees: a window of tile rows, the visible entities with the texts of signs,
his inventory and which rooms are answered. Puzzle records are never exposed. `ExpertPlanner` is the scripted solver (it reads only
the view); `reachability` proves a generated dungeon completable from its start, with and without the imported sigil.
"""

from __future__ import annotations

import copy
from typing import Any

import numpy as np

from wizard_rts import dungeon_agent as D
from wizard_rts.envs import Env
from wizard_rts.puzzle import gen
from wizard_rts.puzzle import items as I
from wizard_rts.puzzle.dungeon import ENTRY, DungeonRun

DIRS = ((0, -1), (1, 0), (0, 1), (-1, 0))
SPELLS = (0, 1, 6)
N_VERBS = 4 + 1 + 8 + 3 + 1  # moves, interact, select item 0..7, select spell 0..2, clear selection
V_INTERACT, V_ITEM0, V_SPELL0, V_CLEAR = 4, 5, 13, 16
SIGIL_WORDS = ["ash", "vale", "ember", "tarn", "flint", "moss", "brine", "cinder"]
KINDS = ("wall", "floor", "door", "logs", "sign", "pickup", "exit")
PUZZLE_TYPES = gen.TEMPLATES
ITEMS = sorted(I._data()["items"]) + ["sigil_*"]
RADIUS = 4


def make_dungeon(seed: int) -> dict[str, Any]:
    word = SIGIL_WORDS[seed % len(SIGIL_WORDS)]
    d = {"id": f"cave_{seed}", "kind": "cave", "faction": "Red", "seed": (seed * 7919 + 13) & 0x7FFFFFFF, "index": 0, "provides": f"sigil_gallery_{seed}",
         "needs": {"item": f"sigil_{word}", "from": "settlement"}, "reward": {}}
    d["puzzles"] = gen.generate(d)
    return d


def split_seeds(split: str) -> range:
    """Disjoint seed ranges: training, validation and held-out test (never mixed)."""
    return {"train": range(0, 600), "val": range(600, 700), "test": range(700, 800)}[split]


class RunActor:
    """An Actor over a DungeonRun (used by the expert on a copy of the live run)."""

    def __init__(self, run: DungeonRun, record: list[int] | None = None) -> None:
        self.run, self.record = run, record

    def view(self) -> dict[str, Any]:
        return self.run.view()

    def move(self, dx: int, dy: int) -> dict[str, Any]:
        if self.record is not None:
            self.record.append(DIRS.index((dx, dy)))
        return self.run.move(dx, dy)

    def interact(self, entity: str, item: str | None = None, spell: int | None = None) -> dict[str, Any]:
        if self.record is not None:
            if item is not None:
                self.record.append(V_ITEM0 + self.run.inv.index(item))
            if spell is not None:
                self.record.append(V_SPELL0 + SPELLS.index(spell))
            self.record.append(V_INTERACT)
            if item is not None or spell is not None:
                self.record.append(V_CLEAR)
        return self.run.interact(entity, item=item, spell=spell)


class DungeonEnv(Env):
    name = "dungeon"
    max_steps = 500

    def __init__(self, with_sigil: bool = True, split: str = "train") -> None:
        super().__init__()
        self.with_sigil, self.split = with_sigil, split
        self.d: dict[str, Any] = {}
        self.run: DungeonRun | None = None
        self.inv: list[str] = []
        self.sel_item = -1
        self.sel_spell = -1
        self._plan: list[int] = []

    def _reset(self, **scenario: Any) -> None:
        self.with_sigil = bool(scenario.get("with_sigil", self.with_sigil))
        self.d = make_dungeon(self.seed)
        self.inv = [self.d["needs"]["item"]] if self.with_sigil else []
        self.run = DungeonRun(self.d, None, self.inv)
        self.sel_item = self.sel_spell = -1
        self._plan = []
        self._solved = 0

    # ---- legality
    def _adjacent(self) -> list[dict]:
        v = self.run.view()
        x, y = v["pos"]
        return [e for e in v["entities"] if abs(e["pos"][0] - x) + abs(e["pos"][1] - y) <= 1]

    def legal_mask(self) -> np.ndarray:
        m = np.zeros(N_VERBS)
        for k, (dx, dy) in enumerate(DIRS):
            x, y = self.run.state["pos"]
            m[k] = 1.0 if self.run.walkable(x + dx, y + dy) else 0.0
        m[V_INTERACT] = 1.0 if self._adjacent() else 0.0
        for i in range(8):
            m[V_ITEM0 + i] = 1.0 if i < len(self.inv) else 0.0
        m[V_SPELL0:V_SPELL0 + 3] = 1.0
        m[V_CLEAR] = 1.0
        return m

    def is_legal(self, action: Any) -> bool:
        a = int(action)
        return 0 <= a < N_VERBS and bool(self.legal_mask()[a]) and not self.done

    def legal_actions(self) -> list[Any]:
        return [i for i, m in enumerate(self.legal_mask()) if m > 0]

    # ---- dynamics
    def _step(self, action: Any) -> tuple[float, dict[str, Any]]:
        a = int(action)
        r = -0.002
        info: dict[str, Any] = {}
        if a < 4:
            self.run.move(*DIRS[a])
        elif a == V_INTERACT:
            ent = D.pick_entity(self._adjacent(), tuple(self.run.state["pos"]))
            kw: dict[str, Any] = {}
            if 0 <= self.sel_item < len(self.inv):
                kw["item"] = self.inv[self.sel_item]
            if self.sel_spell >= 0:
                kw["spell"] = SPELLS[self.sel_spell]
            res = self.run.interact(ent["id"], **kw)
            info["text"] = res.get("text", "")
            if res.get("status") == "rejected":
                r -= 0.01
        elif V_ITEM0 <= a < V_ITEM0 + 8:
            self.sel_item = a - V_ITEM0
        elif V_SPELL0 <= a < V_SPELL0 + 3:
            self.sel_spell = a - V_SPELL0
        else:
            self.sel_item = self.sel_spell = -1
        solved = sum(1 for s in self.run.view()["solved"] if s)
        if solved > self._solved:
            r += 0.25 * (solved - self._solved)
            self._solved = solved
        if solved == 4:
            self.done, self.reason = True, "solved"
            r += 1.0
        return r, info

    # ---- observation
    def observe(self) -> dict[str, Any]:
        v = self.run.view()
        x, y = v["pos"]
        near = [e for e in v["entities"] if abs(e["pos"][0] - x) <= RADIUS + 3 and abs(e["pos"][1] - y) <= RADIUS + 3]
        return {"pos": v["pos"], "rows": v["rows"], "entities": near, "inventory": v["inventory"], "solved": v["solved"], "selected_item": self.sel_item,
                "selected_spell": self.sel_spell, "steps": v["steps"], "room": self._room(y)}

    @staticmethod
    def _room(y: int) -> int:
        from wizard_rts.puzzle.dungeon import ROOM_H, room_origin_y

        for r in range(4):
            if room_origin_y(r) <= y < room_origin_y(r) + ROOM_H:
                return r
        return 0 if y > 16 else 3

    def encode(self, obs: dict[str, Any] | None = None) -> np.ndarray:
        obs = obs or self.observe()
        x, y = obs["pos"]
        rows = obs["rows"]
        ents = {tuple(e["pos"]): e for e in obs["entities"]}
        win = np.zeros((2 * RADIUS + 1, 2 * RADIUS + 1, len(KINDS)))
        for dy in range(-RADIUS, RADIUS + 1):
            for dx in range(-RADIUS, RADIUS + 1):
                tx, ty = x + dx, y + dy
                k = None
                if not (0 <= ty < len(rows) and 0 <= tx < len(rows[0])) or rows[ty][tx] == "#":
                    k = "wall"
                elif (tx, ty) in ents:
                    k = ents[(tx, ty)]["kind"]
                else:
                    k = "floor"
                if k in KINDS:
                    win[dy + RADIUS, dx + RADIUS, KINDS.index(k)] = 1.0
        inv = np.zeros(len(ITEMS))
        for it in obs["inventory"]:
            inv[ITEMS.index(it) if it in ITEMS else len(ITEMS) - 1] = 1.0
        sel = np.zeros(9)
        sel[obs["selected_item"] if obs["selected_item"] >= 0 else 8] = 1.0
        sp = np.zeros(4)
        sp[obs["selected_spell"] if obs["selected_spell"] >= 0 else 3] = 1.0
        return np.concatenate([win.ravel(), inv, sel, sp, np.array(obs["solved"], float), np.eye(4)[obs["room"]], self._clue_features(obs)])

    @staticmethod
    def _clue_features(obs: dict[str, Any]) -> np.ndarray:
        """Features read from the sign texts of the wizard's current room (what a reader of the plaque would take away)."""
        f = np.zeros(8 + 16 + 3 + 3)
        room = obs["room"]
        from wizard_rts.puzzle.dungeon import ROOM_H, room_origin_y

        oy = room_origin_y(room)
        clue = next((e["text"] for e in obs["entities"] if e["kind"] == "sign" and e["id"].endswith("_clue") and oy <= e["pos"][1] < oy + ROOM_H), "")
        low = clue.lower()
        for i, key in enumerate(("two niches", "key sits on a plate", "three levers", "a plate in the floor", "pull the lever and the gate lifts", "four coloured stones",
                                 "wants a wizard", "carved face says")):
            f[i] = 1.0 if key in low else 0.0
        if "three levers" in low or "four coloured stones" in low:
            try:
                for pos, idx in enumerate(D._words_to_order(clue)):
                    f[8 + pos * 4 + idx] = 1.0
            except Exception:
                pass
        if "carved face says" in low:
            f[24] = 1.0 if "pull the left" in low else 0.0
            f[25] = 1.0 if "pull the right" in low else 0.0
            f[26] = 1.0 if "the face lies" in low else 0.0
        if "wants a wizard" in low:
            f[27] = 1.0 if "brazier" in low else 0.0
            f[28] = 1.0 if "chasm" in low else 0.0
            f[29] = 1.0 if "ice" in low else 0.0
        return f

    def state(self) -> Any:
        return {"seed": self.seed, "pos": self.run.state["pos"], "inv": list(self.inv), "puzzles": self.run.state["puzzles"], "taken": self.run.state["taken"],
                "sel": [self.sel_item, self.sel_spell], "done": self.done, "t": self.t}

    # ---- expert
    def expert_action(self) -> int | None:
        """The next verb of a full plan computed on a copy of the live run from the current state (None when the planner fails)."""
        if not self._plan:
            clone = DungeonRun(copy.deepcopy(self.d), copy.deepcopy(self.run.state), list(self.inv))
            record: list[int] = []
            try:
                D.solve_dungeon(RunActor(clone, record))
            except Exception:
                return None
            # the clone starts with no selection; prefix a clear when the live selection is set
            self._plan = ([V_CLEAR] if (self.sel_item >= 0 or self.sel_spell >= 0) else []) + record
        return self._plan.pop(0) if self._plan else None


def reachability(seed: int, with_sigil: bool = True, limit: int = 800) -> dict[str, Any]:
    """Can this generated dungeon be completed from its start by the scripted expert? Returns steps and the failure if any."""
    env = DungeonEnv(with_sigil=with_sigil)
    env.reset(seed)
    for _ in range(limit):
        a = env.expert_action()
        if a is None:
            return {"seed": seed, "solved": False, "why": "planner_failed", "steps": env.t}
        env.step(a)
        if env.done:
            break
    return {"seed": seed, "solved": env.reason == "solved", "why": env.reason, "steps": env.t, "types": [p["type"] for p in env.d["puzzles"]]}
