from wizard_rts.industry import units as U


def test_every_producible_combat_unit_has_a_weapon():
    actors, weapons = U.all_rules()
    exempt = U.SUPPORT | U.CORE_UNITS
    bare = [k for k, a in actors.items() if not a["armaments"] and k[4:] not in exempt]
    assert bare == []
    for a in actors.values():
        assert all(w in weapons for w in a["armaments"])
