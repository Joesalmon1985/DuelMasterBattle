"""Every runnable Widelands production site of every tribe runs its programmes, stocked, without an unsupported command (entity sweep, V4 P5)."""
import pytest
from test_widelands_completion import done, run, world

from wizard_rts import tribes, wl_defs

FACTION_OF = {"barbarians": "Red", "empire": "Blue", "frisians": "Green", "atlanteans": "Yellow", "amazons": "Purple"}


def sites():
    out = []
    for name, b in wl_defs.defs()["buildings"].items():
        if b["type"] == "productionsite" and b.get("runnable") and not b.get("enhanced_from") and name.split("_", 1)[0] in FACTION_OF:
            out.append("wl:" + name)
    return sorted(out)


@pytest.mark.parametrize("kind", sites())
def test_site_runs_its_programmes(kind):
    tribe = kind[3:].split("_", 1)[0]
    w = world()
    spec = wl_defs.spec_for_kind(kind)
    stock = {g: n * 6 for g, n in spec["inputs"].items() if g not in ("recruit", "carrier")}
    try:
        b = done(w, kind, faction=FACTION_OF[tribe], stock=stock)
    except AssertionError:
        pytest.skip("no free site near the warehouse in the showcase map")
    run(w, 120)
    stall = b.get("stall") or {}
    assert stall.get("reason") != "unsupported", (kind, stall)
    assert b.get("worker_ids") is not None
