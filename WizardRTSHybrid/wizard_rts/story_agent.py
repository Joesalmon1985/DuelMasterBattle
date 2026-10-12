"""A scripted wizard that plays the story through the public wizard ops only (same ops the Godot client sends).

It sees what the wizard sees: the dungeon view (tile rows and visible entities with their texts), its inventory, the dialogue lines
and choices. It never reads puzzle records, the duel secret or `world.story` internals. It is the scripted baseline of the
quest/dungeon/duel environments and the reference that every generated dungeon is solvable.
"""

from __future__ import annotations

from typing import Any

from wizard_rts import dungeon_agent as D
from wizard_rts import story
from wizard_rts.mastermind_solvers import ConsistentSolver


def op(world: Any, name: str, **kw: Any) -> dict[str, Any]:
    return story.dispatch(world, {"op": name, **kw})


def walk_to_npc(world: Any, npc: str) -> None:
    """Stand beside the person (the Godot client walks the wizard; here the pose is set to a free tile next to them)."""
    n = story.state(world)["npcs"][npc]
    place_wizard_near(world, n["tile"])


def place_wizard_near(world: Any, tile: list[int], rng: int = 1) -> None:
    x, y = tile
    for r in range(1, 4):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if abs(dx) + abs(dy) == r and world.tile_in_map(x + dx, y + dy) and (x + dx, y + dy) not in world.blocked \
                        and not world.solid_for_wizard((x + dx, y + dy)):
                    world.set_pose(x + dx, y + dy, "down", snapshot=False)
                    return
    raise RuntimeError("no standing tile near %s" % (tile,))


class WorldActor:
    """The live game as an Actor: every move and interaction goes through the wizard ops."""

    def __init__(self, world: Any) -> None:
        self.world = world

    def view(self) -> dict[str, Any]:
        return story.dungeon_view(self.world)

    def move(self, dx: int, dy: int) -> dict[str, Any]:
        return op(self.world, "dungeon_move", dx=dx, dy=dy)

    def interact(self, entity: str, item: str | None = None, spell: int | None = None) -> dict[str, Any]:
        kw: dict[str, Any] = {"entity": entity}
        if item is not None:
            kw["item"] = item
        if spell is not None:
            kw["spell"] = spell
        return op(self.world, "dungeon_interact", **kw)


def _bfs(view: dict[str, Any], goal_adjacent: tuple[int, int] | None, goal_tile: tuple[int, int] | None = None):
    return D.bfs(view, goal_adjacent, goal_tile)


def go_adjacent(world: Any, view: dict[str, Any], target: tuple[int, int]) -> dict[str, Any]:
    return D.go_adjacent(WorldActor(world), target)


def solve_dungeon(world: Any, log: list[str] | None = None) -> bool:
    """Play all four rooms in order. Returns True when every puzzle reports solved. Raises if the content is not completable."""
    return D.solve_dungeon(WorldActor(world), log)


def break_the_code(world: Any, max_guesses: int = 14) -> dict[str, Any]:
    """Play the Mastermind duel with only the public feedback."""
    res = op(world, "duel_begin")
    if res["status"] != "started":
        return res
    solver = ConsistentSolver()
    history: list[tuple[list[int], int, int]] = []
    last: dict[str, Any] = res
    for _ in range(max_guesses):
        guess = solver.next_guess(history)
        last = op(world, "duel_guess", guess=guess)
        if last["status"] in ("solved", "exhausted"):
            return last
        fb = last["feedback"]
        history.append((guess, fb["exact"], fb["colour_only"]))
    return last
