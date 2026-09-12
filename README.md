# Duel Master Battle — Village Dialogue / Story Test Patch

This is a **focused vertical slice** for the current Village Test Mode.

## Goal

Test whether dialogue created by your local language model can be plugged into a real explorable village story while John is running through the normal production `overworld.tscn`.

## What changes

- keeps the existing `Play Village Test Menu.bat` and production Overworld boot;
- replaces the random / coordinate-confused village projection with a deterministic 60x52 continuous map;
- puts Forest/Wood, Village, Fields/Grain and Mine/Ore in the same area;
- represents Sawmill, Mill, Forge, Distillery, Logging Camp, Farmstead and Mine;
- uses production `npc` / `sign` entities, not the previous unsupported generic `interaction` kind;
- adds a real four-beat test story with state:
  **Reeve -> Woodcutter -> Miller -> Miner**;
- talking to story NPCs out of order gives `locked_lines`;
- keeps story state in `Adventure.state`, so the existing VillageTestRunner Reset/Exit snapshot restores it;
- never saves test-story state to the campaign;
- loads the spoken dialogue from editable JSON.

## Install

Extract the zip. Then from its folder run:

```powershell
python apply_patch.py "C:\path\to\DuelMasterBattle"
```

The installer makes a backup:

`.village_test_patch_backup/overworld.gd`

Then it copies the payload and inserts one guarded Village-Test-only hook into `_interact_npc()`.

You can sanity-check installation with:

```powershell
python verify_patch.py "C:\path\to\DuelMasterBattle"
```

## Play

Double-click:

`Play Village Test Menu.bat`

Choose **E17A**.

Story route:

1. Reeve — village square.
2. Woodcutter — forest/logging camp.
3. Miller — village mill.
4. Miner — mine road.

The other economic/civic NPCs are ordinary dialogue test targets.

## Plug in your local-model dialogue

Edit:

`godot_project/content/village_test_dialogue.json`

Keep the stable NPC ids unless you also change the projection:

- `reeve`
- `woodcutter`
- `miller`
- `miner`
- `healer`
- `storekeeper`
- `farmer`
- `blacksmith`
- `distiller`

Each record supports:

```json
{
  "name": "Your generated character name",
  "sprite": "npc",
  "lines": ["Generated line one.", "Generated line two."],
  "locked_lines": ["Dialogue before this story beat is unlocked."]
}
```

A file at `user://village_test_dialogue.json` overrides the repository JSON. That gives your local generator a safe target that need not alter Git files.

Use **Reset Village** or leave/re-enter the fixture after changing dialogue.

## Scope

This patch is intentionally about **proving the dialogue/story pipeline**, not claiming the entire E17/E17A workbook has been implemented.

The current repository fixture contains generic invented cast IDs and pilot-story cast that do not match one another. This patch removes that unreliable coupling and gives you a stable, playable data boundary first.

If this vertical slice works well, the next step is straightforward: convert the workbook/local-LLM output into the same JSON/fixture structure instead of changing gameplay code again.

## Production safety

The added `_interact_npc` branch runs only when:

1. `_village_test_active` is true; and
2. the projected NPC contains `village_test_story`.

Normal campaign NPCs and Puzzle Test Mode therefore retain their normal paths.

## Files

- `apply_patch.py`
- `verify_patch.py`
- `payload/godot_project/sim/world/village_test_profiles.gd`
- `payload/godot_project/sim/world/village_test_dialogue.gd`
- `payload/godot_project/sim/world/village_test_dialogue_story.gd`
- `payload/godot_project/sim/world/village_composite_projection.gd`
- `payload/godot_project/content/village_test_dialogue.json`
