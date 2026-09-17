"""Seeded board geography and faction start placement (C04)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sim.dmb.core.rng import RngBank
from sim.dmb.world.board import HexBoard

TERRAIN_MULTISET: tuple[str, ...] = (
    "woodland",
    "woodland",
    "woodland",
    "woodland",
    "clay_mountains",
    "clay_mountains",
    "clay_mountains",
    "ore_mountains",
    "ore_mountains",
    "ore_mountains",
    "fields",
    "fields",
    "fields",
    "fields",
    "grazing_land",
    "grazing_land",
    "grazing_land",
    "desert",
    "desert",
)

NUMBER_MULTISET: tuple[int, ...] = (
    2,
    3,
    3,
    4,
    4,
    5,
    5,
    6,
    6,
    8,
    8,
    9,
    9,
    9,
    10,
    10,
    11,
    11,
    12,
)

TERRAIN_TO_GOOD: dict[str, str | None] = {
    "woodland": "timber",
    "clay_mountains": "brick",
    "ore_mountains": "ore",
    "fields": "grain",
    "grazing_land": "wool",
    "desert": None,
}

MAX_ATTEMPTS = 100
FIXTURE_DIR = Path(__file__).resolve().parents[3] / "godot_project" / "content" / "fixtures" / "boards"


@dataclass(frozen=True)
class CoreSite:
    faction_id: str
    node_id: str
    index: int


@dataclass
class SetupPlan:
    seed: int
    faction_count: int
    board: HexBoard
    hex_terrain: dict[str, str]
    hex_token: dict[str, int]
    cores: list[CoreSite]
    hazard_hexes: list[str]
    attempts: int
    used_fallback: bool
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "faction_count": self.faction_count,
            "board": self.board.to_dict(),
            "hex_terrain": dict(self.hex_terrain),
            "hex_token": {k: int(v) for k, v in self.hex_token.items()},
            "cores": [
                {"faction_id": c.faction_id, "node_id": c.node_id, "index": c.index}
                for c in self.cores
            ],
            "hazard_hexes": list(self.hazard_hexes),
            "attempts": self.attempts,
            "used_fallback": self.used_fallback,
            "diagnostics": dict(self.diagnostics),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SetupPlan":
        board = HexBoard.from_dict(payload["board"])
        cores = [
            CoreSite(
                faction_id=str(c["faction_id"]),
                node_id=str(c["node_id"]),
                index=int(c["index"]),
            )
            for c in payload["cores"]
        ]
        return cls(
            seed=int(payload["seed"]),
            faction_count=int(payload["faction_count"]),
            board=board,
            hex_terrain={str(k): str(v) for k, v in dict(payload["hex_terrain"]).items()},
            hex_token={str(k): int(v) for k, v in dict(payload["hex_token"]).items()},
            cores=cores,
            hazard_hexes=[str(h) for h in payload.get("hazard_hexes", [])],
            attempts=int(payload.get("attempts", 0)),
            used_fallback=bool(payload.get("used_fallback", False)),
            diagnostics=dict(payload.get("diagnostics", {})),
        )


def _shuffle_copy(rng: RngBank, stream: str, values: list[Any]) -> list[Any]:
    order = rng.shuffle(stream, [str(i) for i in range(len(values))])
    return [values[int(i)] for i in order]


def _assign_geography(board: HexBoard, seed: int, attempt: int) -> tuple[dict[str, str], dict[str, int]]:
    rng = RngBank()
    rng.ensure("geography", seed=f"{seed}:{attempt}", version=1)
    terrains = _shuffle_copy(rng, "geography", list(TERRAIN_MULTISET))
    tokens = _shuffle_copy(rng, "geography", list(NUMBER_MULTISET))
    hex_terrain: dict[str, str] = {}
    hex_token: dict[str, int] = {}
    for idx, hex_id in enumerate(board.hexes):
        hex_terrain[hex_id] = terrains[idx]
        hex_token[hex_id] = int(tokens[idx])
    return hex_terrain, hex_token


def _place_hazards(board: HexBoard, seed: int, attempt: int) -> list[str]:
    rng = RngBank()
    rng.ensure("hazards", seed=f"{seed}:haz:{attempt}", version=1)
    order = rng.shuffle("hazards", list(board.hexes))
    return order[:3]


def _goods_at_node(board: HexBoard, node: str, hex_terrain: dict[str, str]) -> set[str]:
    goods: set[str] = set()
    for hid in board.touching_hexes(node):
        good = TERRAIN_TO_GOOD.get(hex_terrain[hid])
        if good:
            goods.add(good)
    return goods


def _node_productive(
    board: HexBoard,
    node: str,
    hex_terrain: dict[str, str],
    hazard_hexes: set[str],
) -> bool:
    for hid in board.touching_hexes(node):
        if hid in hazard_hexes:
            continue
        if TERRAIN_TO_GOOD.get(hex_terrain[hid]):
            return True
    return False


def _has_cross_terrain_route(board: HexBoard, a: str, b: str, hex_terrain: dict[str, str]) -> bool:
    """Two sites share an industrial route if a shortest path length >= 1 and terrains differ."""
    if board.distance(a, b) < 1:
        return False
    ta = {hex_terrain[h] for h in board.touching_hexes(a)}
    tb = {hex_terrain[h] for h in board.touching_hexes(b)}
    return bool(ta - tb) or bool(tb - ta)


def _legal_cores(
    board: HexBoard,
    chosen: list[str],
    candidate: str,
) -> bool:
    for existing in chosen:
        if board.distance(existing, candidate) < 2:
            return False
    return True


def _select_cores(
    board: HexBoard,
    faction_count: int,
    hex_terrain: dict[str, str],
    hazard_hexes: list[str],
    seed: int,
    attempt: int,
) -> list[CoreSite] | None:
    rng = RngBank()
    rng.ensure("cores", seed=f"{seed}:cores:{attempt}", version=1)
    candidates = rng.shuffle("cores", list(board.nodes))
    hazard_set = set(hazard_hexes)
    needed = faction_count * 2
    chosen: list[str] = []

    def backtrack() -> bool:
        if len(chosen) == needed:
            return True
        for node in candidates:
            if node in chosen:
                continue
            if not _legal_cores(board, chosen, node):
                continue
            if not _node_productive(board, node, hex_terrain, hazard_set):
                continue
            chosen.append(node)
            if backtrack():
                return True
            chosen.pop()
        return False

    if not backtrack():
        return None

    # Pair consecutive cores per faction and validate pair constraints.
    cores: list[CoreSite] = []
    for fi in range(faction_count):
        a = chosen[fi * 2]
        b = chosen[fi * 2 + 1]
        if not _has_cross_terrain_route(board, a, b, hex_terrain):
            return None
        goods = _goods_at_node(board, a, hex_terrain) | _goods_at_node(board, b, hex_terrain)
        if len(goods) < 2:
            return None
        faction_id = f"faction:{fi + 1}"
        cores.append(CoreSite(faction_id=faction_id, node_id=a, index=0))
        cores.append(CoreSite(faction_id=faction_id, node_id=b, index=1))
    return cores


def validate_setup(plan: SetupPlan) -> list[str]:
    problems: list[str] = []
    board = plan.board
    if len(board.hexes) != 19 or len(board.nodes) != 54 or len(board.edges) != 72:
        problems.append("board topology counts invalid")
    terrain_counts: dict[str, int] = {}
    for terrain in plan.hex_terrain.values():
        terrain_counts[terrain] = terrain_counts.get(terrain, 0) + 1
    expected_t = {t: TERRAIN_MULTISET.count(t) for t in set(TERRAIN_MULTISET)}
    if terrain_counts != expected_t:
        problems.append(f"terrain multiset mismatch: {terrain_counts}")
    token_list = sorted(plan.hex_token.values())
    if token_list != sorted(NUMBER_MULTISET):
        problems.append(f"number multiset mismatch: {token_list}")
    if len(plan.cores) != plan.faction_count * 2:
        problems.append("core count mismatch")
    nodes = [c.node_id for c in plan.cores]
    if len(set(nodes)) != len(nodes):
        problems.append("duplicate core nodes")
    for i, a in enumerate(nodes):
        for b in nodes[i + 1 :]:
            if board.distance(a, b) < 2:
                problems.append(f"cores too close: {a} {b}")
    if len(plan.hazard_hexes) != 3:
        problems.append("expected three initial hazards")
    return problems


def _fixture_path(faction_count: int) -> Path:
    return FIXTURE_DIR / f"validated_{faction_count}f.json"


def _load_fallback(faction_count: int, seed: int) -> SetupPlan:
    path = _fixture_path(faction_count)
    payload = json.loads(path.read_text(encoding="utf-8"))
    plan = SetupPlan.from_dict(payload)
    plan.seed = seed
    plan.used_fallback = True
    plan.attempts = MAX_ATTEMPTS
    plan.diagnostics = {"fallback_source": str(path.relative_to(Path(__file__).resolve().parents[3]))}
    problems = validate_setup(plan)
    if problems:
        raise RuntimeError(f"invalid fallback fixture: {problems}")
    return plan


def generate(seed: int, faction_count: int) -> SetupPlan:
    if faction_count not in (2, 6):
        raise ValueError("faction_count must be 2 or 6")
    board = HexBoard.radius2()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        hex_terrain, hex_token = _assign_geography(board, seed, attempt)
        hazards = _place_hazards(board, seed, attempt)
        cores = _select_cores(board, faction_count, hex_terrain, hazards, seed, attempt)
        if cores is None:
            continue
        plan = SetupPlan(
            seed=seed,
            faction_count=faction_count,
            board=board,
            hex_terrain=hex_terrain,
            hex_token=hex_token,
            cores=cores,
            hazard_hexes=hazards,
            attempts=attempt,
            used_fallback=False,
            diagnostics={"attempt": attempt},
        )
        problems = validate_setup(plan)
        if not problems:
            return plan
    return _load_fallback(faction_count, seed)


class BoardBuilder:
    """C04 BoardBuilder facade."""

    @staticmethod
    def generate(seed: int, faction_count: int) -> SetupPlan:
        return generate(seed, faction_count)

    @staticmethod
    def validate_setup(plan: SetupPlan) -> list[str]:
        return validate_setup(plan)
