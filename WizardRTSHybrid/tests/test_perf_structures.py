"""The performance containers behave like the dicts they replace (copy, pickle, ordering)."""
import copy
import pickle

from wizard_rts.workers import TREE_STRIDE, TreeDict


def sample():
    return TreeDict({"tree:5": {"a": 1}, "tree:12": {"a": 2}, "tree:15": {"a": 3}})


def test_buckets_follow_inserts_and_removals_in_order():
    t = sample()
    assert list(t.buckets[5]) == ["tree:5", "tree:15"] and list(t.buckets[2]) == ["tree:12"]
    t["tree:25"] = {"a": 4}
    t.pop("tree:5")
    del t["tree:12"]
    assert list(t.buckets[5]) == ["tree:15", "tree:25"] and not t.buckets[2]
    assert list(t) == ["tree:15", "tree:25"]
    assert sum(len(b) for b in t.buckets) == len(t) and TREE_STRIDE == 10


def test_pickle_deepcopy_and_copy_rebuild_the_buckets():
    t = sample()
    for x in (pickle.loads(pickle.dumps(t)), copy.deepcopy(t), t.copy()):
        assert isinstance(x, TreeDict) and list(x) == list(t)
        assert list(x.buckets[5]) == ["tree:5", "tree:15"] and x == t
