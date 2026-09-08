# First Adventure — opening chapter (vertical slice)

John the woodcutter finds magic, walks out of his burning clearing, crosses the
burnt wood, reaches the village of Ashwell, and faces the Red Wizard in a full
four-slot duel.

This is the first playable adventure section, built on the core duel. The wider
game vision lives in [PRD.md](PRD.md); the duel rules in [RULES.md](RULES.md).

## Play

Main menu: **NEW GAME** / **RESUME GAME** / **Quick Duel** (a standalone 4-slot
wizard match, the old MVP duel). One save slot; starting a New Game over an
existing save asks for confirmation.

- Move: D-pad (touch) or arrow keys / WASD. Interact: ✦ button or Space.
- Pause (≡ button): saves, then offers Continue / How to play / Main menu.
- The game also autosaves on area travel, battle results, and story events.

## Chapter path

1. **The Clearing** (`forest_home`) — opening cutscene (a Blue wizard dies,
   the clearing burns). Take the staff: learn **Water**, weave 1.
2. Douse a fire with Water → Flame Wisps appear → fight (1-slot, fixed Water
   Ward, guaranteed win — teaches the interface).
3. Douse the two fires blocking the north exit → **Burnt Wood** (`forest_deep`).
4. Burnt Wood: pendant pickup (learn **Fire**, weave 2), Steam Sprites (1-slot deduction),
   Cinder Golem (first 2-slot duel), Stone pickup (learn **Stone**, weave 3).
5. East to **Ashwell** (`village`): Moss Shade under the well (3-slot); elder
   teaches **Vine** once the shade is cleared; **Ashby the Hedge Wizard**
   (3-slot wizard) grants weave 4 on defeat.
6. The Red Wizard (4-slot, full deduction). Beating him ends the chapter.

## Unequal weaves (asymmetric duels)

Creatures and wizards don't always match John's weave size. The rule:

- Attempt *i* (0-based, left to right) targets enemy Ward slot
  `i mod ward_size` — extra weave slots **wrap around** onto Ward slot 0, 1, …
- A Ward is **broken** when every Ward slot has been hit by at least one exact
  (Fracture) attempt — not when every attempt is exact.
- If your weave is smaller than the enemy Ward, some slots are unreachable:
  the battle screen warns you that you **cannot break** that Ward yet (go learn
  more magic). Enemy bots face the same constraint against your Ward.

Implementation: `DmbFeedback.target_slot(i, ward_size)`,
`targets_by_ward_slot(attack_size, ward_size)`, `score_attack` in
`godot_project/sim/feedback.gd`. Combatants: `sim/combatant.gd`
(`attack_pool` / `ward_pool` / `weave_size` / `ward_size` separate by design).
Opponent deduction under asymmetry: `sim/weave_bot.gd`.

## Bestiary (chapter order)

| Enemy | Weave | Casts | Ward | Ward pool | Bot |
|---|---|---|---|---|---|
| Flame Wisp | 1 | Water | 1 (fixed Water) | Water | random |
| Flame Imp | 1 | Fire | 1 | Water, Fire | random |
| Steam Sprite | 1 | Fire, Water | 1 | Fire, Water | candidate_filter |
| Steam Brute | 2 | Fire, Water | 2 | Fire, Water | candidate_filter |
| Cinder Golem | 2 | Fire, Stone | 2 | Fire, Water | candidate_filter |
| Moss Shade | 3 | Vine, Water, Stone | 3 | Fire, Water, Stone | candidate_filter |
| Ashby the Hedge Wizard | 3 | Fire, Stone | 3 | Fire, Stone, Water | candidate_filter |
| The Red Wizard | 4 | Fire, Water, Stone, Vine | 4 | Fire, Water, Stone, Vine | capped_minimax |

Defined in `godot_project/sim/bestiary.gd` (`DmbBestiary.get_data(id)`).

## Saving

`user://adventure.save` (JSON: `{state, progression}`). Persists: area +
position + facing, known spells, weave size, story/event flags, defeated and
extinguished marks, collected pickups, environmental changes (fires out, wisps
spawned). Battles themselves restart; results are applied to the save.
Code: `godot_project/client/scripts/adventure.gd` (`Adventure` autoload).

## Adding content

- **New area**: add a builder in `client/world/world_data.gd`, register in
  `_build()`; entity kinds: `sign door logs trigger pickup corpse fire burnt
  creature wizard npc`. Gate with `requires_flag` / `requires_item` /
  `once_flag`; wire exits via `exits` (they autosave on travel).
- **New enemy**: add a dict in `sim/bestiary.gd`; needs a creature portrait
  `assets/pixel/creatures/<archetype>_portrait_0.png` + world sprite
  `<archetype>_world_0.png` (see `tools/build_pixel_assets.py`), and a
  `creature` entity in `world_data.gd`.
- **New story beat**: extend `client/world/story_events.gd`; use
  `adv.learn_spell(id)` / `adv.grow_weave(n)` for progression.

## Art

Pixel-art dark fantasy style. Source sprites live in the gitignored
`Spare Sprites/` folder; `tools/build_pixel_assets.py` imports what the game
needs and generates placeholders (creatures, tiles, portraits) into
`godot_project/assets/pixel/`. Only `assets/pixel/` is committed.

## Tests

- `tools/run_godot_tests.sh` — sim (incl. asymmetric battle suite).
- `tools/run_godot_ui_smoke.sh` — standalone duel.
- `tools/run_adventure_flow.sh` — **full chapter path**: New Game → opening →
  staff → fire → wisp → … → Red Wizard, plus a save/load round trip.
- `tools/capture_adventure_qa.sh` — headed screenshots → `qa/screenshots/adventure`.
