"""Wild animals: wanderers that hunters can kill, and that breed back.

Widelands critters (world/critters/*) wander at random and reproduce at a
species rate. A hunter reserves one, which freezes it, walks to it and removes
it. When game is hunted out the hunter's hut idles. Breeding is limited by how
many animals are already nearby, so a hunted-out region recovers slowly and a
crowded one stops growing. Provisional: no herbivore diet, no predators, no
terrain affinity.
"""

from __future__ import annotations

from typing import Any

from wizard_rts.programs_data import ANIMAL_BREED_CHECK_MS, ANIMAL_CAP_NEAR, ANIMAL_SPECIES
from wizard_rts.workers import new_id

QUANTUM_MS = 100
LEASH = 14  # cells an animal wanders from where it was born


def spawn_animal(world: Any, tile: tuple[int, int], species: str, home: tuple[int, int] | None = None) -> str:
    aid = new_id(world, "animal")
    world.animals[aid] = {
        "id": aid, "class": "animal", "kind": "animal", "species": species,
        "definition": f"widelands.{species}", "tx": tile[0], "ty": tile[1], "alive": True,
        "reserved_by": "", "status": "idle", "facing": "se", "home": home or tile,
        "move_wait_ms": world.rng.randint(0, 3000), "progress_ms": 0, "next": None,
        "breed_ms": world.rng.randint(ANIMAL_BREED_CHECK_MS // 2, ANIMAL_BREED_CHECK_MS),
    }
    return aid


def _free(world: Any, tile: tuple[int, int]) -> bool:
    return world.tile_in_map(*tile) and tile not in world.blocked and tile not in world.road_tile_set


def animal_quantum(world: Any) -> None:
    for animal in list(world.animals.values()):
        if animal["reserved_by"]:
            animal["next"] = None
            continue
        spec = ANIMAL_SPECIES[animal["species"]]
        if animal["next"] is not None:
            animal["progress_ms"] += QUANTUM_MS
            if animal["progress_ms"] >= spec["move_ms"]:
                animal["tx"], animal["ty"] = animal["next"]
                animal["next"] = None
                animal["progress_ms"] = 0
                animal["status"] = "idle"
                animal["move_wait_ms"] = world.rng.randint(1000, 6000)
        else:
            animal["move_wait_ms"] -= QUANTUM_MS
            if animal["move_wait_ms"] <= 0:
                dx, dy = world.rng.choice(((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)))
                tile = (animal["tx"] + dx, animal["ty"] + dy)
                home = animal["home"]
                if _free(world, tile) and max(abs(tile[0] - home[0]), abs(tile[1] - home[1])) <= LEASH:
                    animal["next"] = tile
                    animal["facing"] = {(1, 0): "e", (-1, 0): "w"}.get((dx, dy), ("se" if dy > 0 else "ne") if dx >= 0 else ("sw" if dy > 0 else "nw"))
                    animal["status"] = "moving"
                else:
                    animal["move_wait_ms"] = 1000
        animal["breed_ms"] -= QUANTUM_MS
        if animal["breed_ms"] <= 0:
            animal["breed_ms"] = ANIMAL_BREED_CHECK_MS
            near = sum(1 for o in world.animals.values() if abs(o["tx"] - animal["tx"]) <= 14 and abs(o["ty"] - animal["ty"]) <= 14)
            if near < ANIMAL_CAP_NEAR and world.rng.random() * 100 < spec["reproduction"]:
                for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
                    tile = (animal["tx"] + dx, animal["ty"] + dy)
                    if _free(world, tile):
                        spawn_animal(world, tile, animal["species"], animal["home"])
                        world.events.append({"kind": "animal_born", "species": animal["species"]})
                        break
