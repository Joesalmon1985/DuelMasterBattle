"""The passability table used by A* belongs to one terrain object: a later world must never be handed an earlier world's table (it used to be
cached by id(terrain), which Python reuses after a world is freed: a crash with the native kernel, or silently wrong paths)."""
import gc

from wizard_rts import workers
from wizard_rts.world import HybridWorld


def _world(seed, size):
    w = HybridWorld(seed, terrain=True, map_size=size)
    w.ai_enabled = False
    return w


def test_each_world_gets_a_table_of_its_own_size_and_content():
    a = _world(507, "small")
    ta = workers._passable(a, "foot")
    assert len(ta) == a.terrain.w * a.terrain.h
    b = _world(11, "standard")
    tb = workers._passable(b, "foot")
    assert len(tb) == b.terrain.w * b.terrain.h and tb is not ta
    c = _world(23, "small")
    tc = workers._passable(c, "foot")
    assert len(tc) == len(ta) and tc is not ta and bytes(tc) != bytes(ta)  # same size, different land


def test_a_freed_terrain_leaves_nothing_behind():
    a = _world(507, "small")
    workers._passable(a, "foot")
    before = len(workers._PASSABLE)
    del a
    gc.collect()
    assert len(workers._PASSABLE) < before
