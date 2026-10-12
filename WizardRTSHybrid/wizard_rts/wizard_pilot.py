"""A scripted wizard for headless crisis experiments (brief P3: "a separate ScriptedWizardAgent ... by the same public actions,
distances, costs and timing as the human player, not teleport/cheat ops").

It plays only the wizard's public actions: `set_pose` one tile at a time (the same walkability rule as Godot's local movement and the
server's pose op: ground, no building, no standing tree or rock) at WALK_TILES_PER_S, and `regions.begin_treatment` (the T key), which
the simulation itself checks (the wizard must stand in the region, stay for the channel time, and wait out the cooldown). It never
commands a faction, never moves faster than a person walks, and never edits the world. It chooses the infected region with the most
cubes that holds a settlement, nearest first, and walks there by an A* over the wizard's walkable tiles.
"""

from __future__ import annotations

import heapq
from typing import Any

from wizard_rts import regions

WALK_TILES_PER_S = 4  # the Godot wizard walks a tile in about 0.2-0.25 s of real time at 1x
REPLAN_LIMIT = 260  # tiles of search radius for one path


class WizardPilot:
    def __init__(self, world: Any) -> None:
        self.world = world
        self.path: list[tuple[int, int]] = []
        self.goal_region: int | None = None
        self.log: list[dict[str, Any]] = []
        self.walked = 0
        self.treatments = 0

    def _note(self, kind: str, **kw: Any) -> None:
        self.log.append({"game_ms": int(self.world.dmb.clock.get("game_ms", 0)), "kind": kind, **kw})
        del self.log[:-200]

    def walkable(self, t: tuple[int, int]) -> bool:
        w = self.world
        return w.tile_in_map(*t) and t not in w.blocked and not w.solid_for_wizard(t)

    def _pick_region(self) -> int | None:
        w = self.world
        s = regions.state(w)
        if s is None or not any(s.cubes):
            return None
        here = (int(w.player["tx"]), int(w.player["ty"]))
        best = None
        for rec in w.dmb.settlements.values():
            if rec["state"] != "standing":
                continue
            i = s.region_at(rec["tile"][0], rec["tile"][1])
            if s.cubes[i] <= 0:
                continue
            d = abs(rec["tile"][0] - here[0]) + abs(rec["tile"][1] - here[1])
            key = (-s.cubes[i], d, i)
            if best is None or key < best[0]:
                best = (key, i, tuple(rec["tile"]))
        return None if best is None else best[1]

    def _plan(self, region: int) -> bool:
        """A* to the nearest walkable tile of the region (the settlement's region is enough: treatment needs presence anywhere in it)."""
        w = self.world
        s = regions.state(w)
        start = (int(w.player["tx"]), int(w.player["ty"]))
        if s.region_at(*start) == region:
            self.path = []
            return True
        target = None
        for rec in w.dmb.settlements.values():
            if rec["state"] == "standing" and s.region_at(rec["tile"][0], rec["tile"][1]) == region:
                target = tuple(rec["tile"])
                break
        if target is None:
            return False
        came: dict[tuple[int, int], tuple[int, int]] = {}
        cost = {start: 0}
        heap = [(0, 0, start)]
        n = 0
        while heap:
            _f, _c, cur = heapq.heappop(heap)
            if s.region_at(*cur) == region:
                path = [cur]
                while cur != start:
                    cur = came[cur]
                    path.append(cur)
                path.reverse()
                self.path = path[1:]
                return True
            if abs(cur[0] - start[0]) > REPLAN_LIMIT or abs(cur[1] - start[1]) > REPLAN_LIMIT:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nxt = (cur[0] + dx, cur[1] + dy)
                if not self.walkable(nxt):
                    continue
                c = cost[cur] + 1
                if c < cost.get(nxt, 1 << 30):
                    cost[nxt] = c
                    came[nxt] = cur
                    n += 1
                    heapq.heappush(heap, (c + abs(target[0] - nxt[0]) + abs(target[1] - nxt[1]), n, nxt))
        return False

    def step(self) -> None:
        """Called once per game second by the harness."""
        w = self.world
        s = regions.state(w)
        if s is None:
            return
        if s.treat is not None:
            return  # channelling: stand still
        here = (int(w.player["tx"]), int(w.player["ty"]))
        if self.goal_region is None or s.cubes[self.goal_region] <= 0:
            self.goal_region = self._pick_region()
            self.path = []
            if self.goal_region is None:
                return
            if not self._plan(self.goal_region):
                self._note("no_path", region=s.rid(self.goal_region))
                self.goal_region = None
                return
            self._note("heading", region=s.rid(self.goal_region), tiles=len(self.path))
        if s.region_at(*here) == self.goal_region:
            res = regions.begin_treatment(w)
            if res.get("status") == "started":
                self.treatments += 1
                self._note("treat", region=s.rid(self.goal_region))
            return
        for _ in range(WALK_TILES_PER_S):
            if not self.path:
                if not self._plan(self.goal_region):
                    self.goal_region = None
                return
            nxt = self.path.pop(0)
            if w.set_pose(nxt[0], nxt[1], "down", snapshot=False)["status"] != "ok":
                self.path = []  # something now stands there: plan again next second
                return
            self.walked += 1
