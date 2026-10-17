# Character sprites and animation (branch `feature/character-sprites-animation`)

Every person in the wizard world is now drawn by one original, procedurally authored character system instead of borrowed Widelands /
OpenRA infantry sprites, legacy 16x24 rectangles or `GEOMETRIC_MODE` polygons. Presentation only: no simulation, combat, quest or
dialogue rule changed.

## 1. Inventory (what existed, what draws it now)

| Category | Where it appears | Before | Now |
|---|---|---|---|
| Player wizard (John / Halvard / spirits) | `Overworld._john`, `hybrid_world` | `assets/pixel/chars/*_N.png` (16x24, 2 frames, no walk cycle) | named looks (`john`, `john_staff`, `blue_mage`, ...), full clip set |
| Other LAN wizards | `hybrid_world._mp_apply_players` | legacy sprite keys | six wizard cuts chosen by the player id, robe in the player's own colour |
| Workers, carriers (161 Widelands job names, 5 tribes) | `hybrid_art.draw_entity` | imported Widelands sheets | 33 job outfits x tribe palette x per-id hair/skin/beard |
| Soldiers (5 tribes), engineers' infantry (e1 e2 e3 e4 e6 e7 spy thf medi mech shok zombie), `dmb.*` fighters, settlers, caravan | `hybrid_art` | Widelands soldier / OpenRA infantry | one outfit each; faction colour on the accent layer |
| Story people (miner, healer) | `hybrid_art._draw_story` | borrowed Widelands figure or a rectangle | persistent per-id person + animated dialogue portrait |
| Legacy named cast (Ivy, Igbut, Throm, matron, elder, knight, dwarf, elf, reaper, ...) and cutscene actors | `ActorVisual` | 16x24 PNGs | 31 named looks (colours / silhouettes of the old sprites kept) |
| Legacy village projection workers | `worker_controller.gd` | `GEOMETRIC_MODE := true` polygons | character views (`GEOMETRIC_MODE := false`), `work` clip while working |
| Animals (deer, bunny, ox, horse, dog ...), vehicles, ships | `hybrid_art` | borrowed art | **unchanged** (not people; see limitations) |
| Ward-duel board wizards | `CompositeWizard` / `PixelPortrait` | generated composite parts | **unchanged** (own pipeline, retained board) |

## 2. Art direction and pipeline

`tools/character_sprites/` (Python + Pillow + numpy, no third-party art, deterministic):

* `rig.py` an articulated 3-view skeleton (front, side, back; left is a mirror). Legs, arms, head, hips solved per pose; bob comes from
  keeping the lowest foot on the ground, not from moving a static picture.
* `clips.py` idle (breath + blink), walk (6 frames, alternating legs + counter-swinging arms), talk (6 frames: mouth shapes, nod, hand
  gestures), work (tool stroke), hurt, die (fall, keeps last frame), surprise, and for wizards cast and celebrate.
* `garments.py`, `hats.py`, `props.py`, `hair.py`, `face.py` clothes, 18 hats, 35 tools that follow the hand joint, 11 hairstyles,
  7 beards, expressive eyes/brows/mouths.
* `raster.py` 4x oversampled shapes -> fixed-light 3-tone shading -> inner and outer outlines. Every pixel is owned by exactly one
  layer, so the layer sheets can be tinted independently and re-composed exactly.
* `outfits_db.py` 72 outfits; `palettes.py` skin/hair/tribe/wizard palettes, 31 named looks, the job -> outfit table.
* `generate.py` writes `godot_project/assets/characters/` (outfit sheets, portraits, hair and beard sheets, `characters.json`).

Cell 56x48 sprite pixels, figure ~38 px (drawn at 2.5x = about 95 screen px, 1.5 tiles, the old footprint). Layers per sheet: outline,
skin, cloth a/b/c (tinted greys) and untinted detail; hair and beard are separate sheets. A "villager" is therefore a job sheet plus tints
plus hairstyle: new inhabitants cost nothing; new jobs/races/outfits are an entry in `outfits_db.py`.

Regenerate: `cd tools && python3 -m character_sprites.generate` (about 1 min), then open Godot once (`--import`).
Tests: `python3 -m pytest tools/character_sprites/tests -q` (81 tests: every outfit renders, layers never overlap, nothing is cut by the
cell, walk frames differ, talk shows several mouths, determinism, every Widelands worker and OpenRA infantry actor has an outfit).

## 3. Runtime (`godot_project/client/characters/`)

* `character_library.gd` loads the manifest and sheets through `ResourceLoader` only (works from an APK).
* `character_look.gd` / `character_appearance.gd` a look is a pure function of stable ids: FNV-1a of the entity id + definition + tribe;
  named people by name; LAN wizards by player id + colour. No random generator, so save/load, polling, scrolling and every LAN client agree.
* `character_anim.gd` the single controller. Priority: DEAD > REVIVE > HURT > reaction (cast/celebrate/surprise) > TALK > WALK/WORK > IDLE.
  Driven by movement, `DmbCharBus.is_speaking(id)`, hp drops and `alive`. Death holds its last frame and ignores talking/walking.
* `character_bus.gd` presentation events (speak / react / dead) keyed by character id. Nothing flows back into the simulation.
* `character_renderer.gd` draws one cell (8 batched region draws + shadow); `character_crowd.gd` serves the hybrid world's single
  `_draw()` (culled to the viewport, anim updates only for what is drawn, LOD below zoom 0.4, nothing below 0.16);
  `character_view.gd` serves Sprite2D actors and derives walking/facing from the parent's movement.
* `dialogue_portrait.gd` a 64x64 bust (blink, nine expressions, talking mouth) beside the story dialogue; the panel now sits along the
  bottom edge so the speaker stays visible.

Integration points: `actor_visual.gd` (every Sprite2D actor), `hybrid_art.gd` (workers, soldiers, story NPCs), `story_ui.gd`
(talk / choose / close drive the bus: the person speaks, the wizard answers, then the person replies, then everyone idles),
`ui/dialogue.gd` + `world/dialogue_box.gd` (legacy conversations and cutscene `say`), `hybrid_world.gd` (LAN wizards, tribes/colours),
`worker_controller.gd`.

## 4. Android / export

* `hybrid_art._remember` used `Image.load("res://x.png")`, which finds nothing in an exported build (Godot warns "will not work on
  export"). It now loads the imported resource first and only falls back to the raw file in development.
* Character assets are imported textures + `characters.json` (exported as a resource). `client/tests/run_export_check.gd` run against
  `godot --headless --export-pack Android game.pck` from an empty directory loads all 192 textures from the pack alone.
* Textures stay lossless (pixel art does not survive ETC2). Memory is ~5.6 MB per outfit sheet and ~1.2 MB per hair sheet when loaded; only
  sheets that appear are loaded. An APK build itself needs the Android SDK / export templates, which this machine does not have.

## 5. Evidence

`WizardRTSHybrid/docs/evidence/characters/` showcase pages, per-frame sheets for every clip, filmstrips and GIFs, hybrid-world and LAN
screenshots. Showcase: `res://client/scenes/character_showcase.tscn`.
Tests run: `client/tests/run_characters.gd` (headless), `run_hybrid_characters.gd` (headed, real sim: people drawn, walking, idle,
conversation with speaking/answering/idle, soldiers), `scripts/run_lan_characters.sh` (two clients), the existing LAN two-client PvP duel
acceptance, `run_actor_fallback`, `run_g05_humanoid_scale`, `run_ui_smoke`, `run_adventure_flow`, `run_village_test_mode`, `run_dialogue`.

## 6. Known limitations

* Animals, vehicles and ships keep their borrowed art. The Ward duel board keeps `CompositeWizard`.
* The simulation has no ambient villager chatter and no resurrection mechanic; both are supported by the bus (`speak`, `react`, `mark_dead`)
  but nothing in the game emits them yet. A unit that dies is shown falling and lying until the simulation removes the corpse.
* Wizard cast/celebrate clips exist; the hybrid world has no cast event to trigger them yet (LAN test fires one through the bus).
* Hurt is detected from `hp` dropping in snapshots; units that vanish the same tick they die do not show a fall.
* No APK was built here (no SDK).
