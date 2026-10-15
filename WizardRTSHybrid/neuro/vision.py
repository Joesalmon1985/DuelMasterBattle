"""What a controller may know about the other factions: the only door to that information (execution plan T1.1).

A thin facade over wizard_rts.visibility. Everything a controller reads about other factions (their buildings, units, catastrophe regions in
sight) comes through here, and everything here is limited to what the faction has seen, been shown, or remembers from earlier sightings.
"""
from wizard_rts.visibility import (  # noqa: F401
    explored_of,
    known,
    known_enemy_buildings,
    memory_of,
    refresh,
    seen_enemies,
    sources,
    visible,
    visible_regions,
    visible_units,
)
