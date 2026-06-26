"""Tests for realtime duel ruleset fields and 8-locus support."""

from duel_mastermind.encounters import get_encounter
from duel_mastermind.difficulty_profiles import get_profile


def test_eightfold_warden_has_eight_loci():
    rs = get_encounter("eightfold_warden")
    assert rs.slot_count == 8
    assert len(rs.point_names) == 8
    assert rs.last_stand_seconds == 20.0


def test_blue_apprentice_no_repeats():
    rs = get_encounter("blue_apprentice")
    assert rs.allow_repeats is False
    assert rs.attack_magic_pool == [0, 1, 2]


def test_difficulty_profiles():
    assert get_profile("medium").bot_logic == "candidate_filter"
    assert get_profile("hard").bot_min_cast_time_multiplier == 0.75
