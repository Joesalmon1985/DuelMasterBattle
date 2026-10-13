import pytest

from wizard_rts import maritime, wl_defs

TRIBES = ("barbarians", "empire", "atlanteans", "frisians", "amazons")


@pytest.mark.parametrize("tribe", TRIBES)
def test_a_ship_is_paid_for_in_the_wares_its_own_shipyard_takes(tribe):
    cost = maritime.ship_cost(tribe)
    yard = wl_defs.defs()["buildings"][f"{tribe}_shipyard"]["inputs"]
    assert cost and set(cost) <= set(yard), (tribe, cost, yard)  # no ware the tribe's yard cannot be fed
    assert all(w in wl_defs.defs()["wares"] for w in cost)


def test_tribes_do_not_share_one_ship_cost():
    assert len({tuple(sorted(maritime.ship_cost(t).items())) for t in TRIBES}) >= 4
