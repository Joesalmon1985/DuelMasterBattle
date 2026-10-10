"""Unit tests isolate one system at a time, so the faction AIs are off unless a test turns them on."""

import os

os.environ.setdefault("HYBRID_AI", "0")


def set_resource(w, node, res, amount):
    """Set a deposit on a node whichever way the world stores them (terrain layers or the legacy dict)."""
    from wizard_rts import terrain as T

    if w.terrain is None:
        w.resources.setdefault(node, {})[res] = amount
        return
    i = node[1] * w.terrain.w + node[0]
    w.terrain.res_kind[i] = T.RES_CODE[res]
    w.terrain.res_amt[i] = amount
    w.terrain.res_init[i] = amount


def resource_sum(w, nodes, res):
    return sum(w.resource_amount(n, res) for n in nodes)
