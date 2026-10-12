"""The C A* kernel returns exactly the paths of the Python search (same tie-breaks), including join, avoid, limit and failure."""
import random

import pytest

from wizard_rts import native, workers
from wizard_rts.world import HybridWorld


@pytest.fixture(scope="module")
def world():
    w = HybridWorld(507, terrain=True, map_size="standard")
    for i in range(240):
        w.advance(1000, i + 1, snapshot=False)
    return w


def search(world, native_on, *a, **k):
    old = list(workers._NATIVE)
    workers._NATIVE[:] = [True, native.astar_lib() if native_on else None]
    try:
        return workers.find_path(world, *a, **k)
    finally:
        workers._NATIVE[:] = old


@pytest.mark.skipif(native.astar_lib() is None, reason="no C compiler")
def test_native_matches_python(world):
    rng = random.Random(5)
    t = world.terrain
    same = found = 0
    for _ in range(120):
        a = (rng.randrange(t.w), rng.randrange(t.h))
        b = (min(t.w - 1, max(0, a[0] + rng.randint(-60, 60))), min(t.h - 1, max(0, a[1] + rng.randint(-40, 40))))
        loco = rng.choice(["foot", "wheeled", "tracked", "naval"])
        avoid = {(a[0] + rng.randint(-5, 5), a[1] + rng.randint(-5, 5)) for _ in range(rng.randint(0, 30))}
        limit = rng.choice([24, 400])
        nodes = rng.choice([500, 20_000, 150_000])
        join = None
        if rng.random() < 0.3:
            ref = search(world, False, a, b, limit=400, loco=loco)
            if ref:
                join = {tile: i for i, tile in enumerate(ref[: len(ref) // 2])}
        py = search(world, False, a, b, limit=limit, avoid=avoid, max_nodes=nodes, loco=loco, join=join)
        c = search(world, True, a, b, limit=limit, avoid=avoid, max_nodes=nodes, loco=loco, join=join)
        assert py == c
        same += 1
        found += py is not None
    assert same == 120 and found > 20
