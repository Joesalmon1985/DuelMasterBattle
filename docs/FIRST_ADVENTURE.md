# First Adventure — Trial Day in Ashwell (P1 chapter)

John the woodcutter lives in Ashwell. On Trial Day he watches the Blue wizard
Halvard fall to the Red Wizard, inherits a staff, learns the duel from Ashby,
walks the carnival road, meets the other contestants at the gate — and chooses
to enter the Trial. The chapter ends at the threshold.

The wider game vision lives in [PRD.md](PRD.md); the duel rules in
[RULES.md](RULES.md); the Deathtrap plan in
[DEATHTRAP_OVERHAUL_PLAN.md](DEATHTRAP_OVERHAUL_PLAN.md).

## Play

Main menu: **NEW GAME** / **RESUME GAME** / **Quick Duel** (a standalone 4-slot
wizard match, the old MVP duel). One save slot; starting a New Game over an
existing save asks for confirmation.

- Move: D-pad (touch) or arrow keys / WASD. Interact: ✦ button or Space.
- Pause (≡ button): saves, then offers Continue / How to play / Main menu.
- The game also autosaves on area travel, battle results, and story events.

## Chapter path

1. **Ashwell** (`village`) — Trial-day morning. Talk to anyone; step onto the
   road → Halvard vs Red Wizard cutscene (4-slot spectacle, Red wins, no fire
   spreads). Take the staff: learn **Water**, weave 1 (`has_staff`).
2. Villagers react (`lines_flag` on `has_staff`); elder points at Ashby.
   **Ashby lesson 1** (1-slot, fixed Water Ward, guaranteed win → `beat_lesson1`),
   **lesson 2** (1-slot Water-or-Fire deduction → `beat_lesson2`). Optional 2nd.
3. South to **Trial Road** (`trial_road`): six travellers, stalls, bookmaker,
   healer, and an optional **Giant Fly** (1-slot, fixed Water Ward, walk away
   any time via "Not yet").
4. East to the **Burnt Wood** (`forest_deep`): optional training detour. Its
   creatures still duel, but the pendant and heart-stone are burnt-out husks
   (`grant: {}`) — no Fire/Stone before the dungeon earns them.
5. North to the **Trial Gate** (`trial_gate`): seven entrants (Serra the Knight,
   the Elven woman, Throm, the laughing Barbarian, the quiet assassin, the Red
   Wizard, John) + the Rollkeeper. Step to the doors → **ENTER THE TRIAL** /
   **NOT YET** (repeatable; genuinely free). Entering sets `entered_trial` and
   plays the threshold ending. Chapter complete at weave 1.

## Bestiary (chapter order)

| Enemy | Weave | Casts | Ward | Ward pool | Bot |
|---|---|---|---|---|---|
| Ashby's Practice Ward | 1 | Water | 1 (fixed Water) | Water | random |
| Ashby's Hidden Ward | 1 | Water | 1 | Water, Fire | candidate_filter |
| Giant Fly | 1 | Fire | 1 (fixed Water) | Water | random |
| Burnt Wood fauna (imp, sprite, brute, golem) | 1–2 | various | 1–2 | Fire, Water | random / candidate_filter |

Defined in `godot_project/sim/bestiary.gd`. The wood's Fire/Stone-gated
creatures are unreachable at weave 1 with Water only — natural gating, no
special code.

## Saving

`user://adventure.save` (JSON: `{state, progression}`). Persists: area +
position + facing, known spells, weave size, story/event flags, defeated and
picked marks, environmental changes. Battles themselves restart; results are
applied to the save. New games start in `village` at [7,10].
Code: `godot_project/client/scripts/adventure.gd` (`Adventure` autoload).

## Adding content

- **New area**: add a builder in `client/world/world_data.gd`, register in
  `_build()`; entity kinds: `sign door logs trigger pickup corpse fire burnt
  creature wizard npc`. Gate with `requires_flag` / `requires_item` /
  `requires_spell` / `requires_defeated` / `once_flag`; wire exits via `exits`
  (they autosave on travel). Keep rows equal-length; keep NPCs off the tile
  the player must stand on (BFS cannot path onto blocked tiles).
- **Repeatable trigger**: add `"no_auto_flag": true` so the event (not the
  engine) owns the flag — used by the gate choice.
- **Pickup flags**: `"set_flag": "<flag>"` on a pickup sets a flag on take.
- **New enemy**: add a dict in `sim/bestiary.gd`; needs a creature portrait
  `assets/pixel/creatures/<archetype>_portrait_0.png` + world sprite
  `<archetype>_world_0.png` (see `tools/build_pixel_assets.py`), and a
  `creature` entity in `world_data.gd`. Wizard-kind enemies use a
  `chars/<sprite>_*` sprite and fall back to the generic battle portrait.
- **New story beat**: extend `client/world/story_events.gd`; use
  `adv.learn_spell(id)` / `adv.grow_weave(n)` / `adv.set_flag(f)`; choices via
  `choose_async` (test drives them with `ui_dialogue_choose`).

## Art

Pixel-art dark fantasy style. Source of truth is `tools/build_pixel_assets.py`
(deterministic; safe to re-run) into `godot_project/assets/pixel/`. Only
`assets/pixel/*.png` is committed (`.import` files are Godot-generated).
P1 adds: Giant Fly (portrait + world), gate contestants
(knight/elf/assassin/throm/official) — placeholders, refined in the P7 pass.

## Tests

- `tools/run_godot_tests.sh` — sim (incl. `test_dd_canon.gd` P0 canon set).
- `tools/run_godot_ui_smoke.sh` — standalone duel.
- `tools/run_adventure_flow.sh` — **Trial-Day path**: New Game → duel cutscene →
  staff → Mara → lesson 1 → lesson 2 → save/load → road → Tam → fly → Burnt
  Wood detour + return → gate roster → NOT YET → ENTER → threshold, plus a
  final save/load round trip.
- `tools/capture_adventure_qa.sh` — headed screenshots →
  `qa/screenshots/adventure` (village, aftermath, road, gate, battles).
