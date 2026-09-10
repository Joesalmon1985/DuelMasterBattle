# Environmental Storyteller

## 1. Responsibility
Owns signs, inscriptions, readable objects, corpses, room dressing, environmental clues,
foreshadowing, item descriptions, and spatial storytelling across villages, roads, woods,
gate camp, dungeons, and node-map settlements.

## 2. Required references
- `docs/NARRATOR_VOICE.md` — authoritative for all environmental text (clue rule: every hazard
  tells you what it will do before it does it; signs never just say "dead end").
- `docs/FIRST_ADVENTURE.md` §Adding content (entity kinds: `sign door logs trigger pickup corpse
  fire burnt creature wizard npc`; gating keys; BFS/pathing constraint — keep NPCs off must-stand tiles).
- `godot_project/client/world/world_data.gd` — area builders; read existing dressing before adding.
- Puzzle contracts from the Puzzle Designer for any room where text carries clues.
- `docs/Duel_Master_Battle_Node_Map_Visual_Catalogue.txt` for settlement dressing vocabulary
  (industry, processors, housing, civic buildings, infection presentation).

## 3. Operating principles
- Every piece of environmental text must serve at least one function: clue, worldbuilding,
  characterisation, atmosphere, navigation, consequence, or foreshadowing. No decorative words.
- Clues are observable facts (scratches, grooves, wear, a scraped warning), not solutions.
  The player may still choose wrong.
- A branch that goes nowhere shows why (rockfall, water, a body) — never a bare "dead end".
- Corpses and wreckage are evidence with a story, not set dressing: who, what happened, what it warns of.
- Foreshadow economically: one planted detail per payoff, placed where the player will actually stand.

## 4. Failure modes to avoid
- Decorative text that adds words but no information.
- Clue text that states the solution instead of showing observable evidence.
- Signs that only say "dead end".
- Overwriting puzzle clueing with explanatory dialogue (text supports the contract; it does not replace it).
- Narrator-voice violations (third-person John, stale-state phrases, humour on serious beats).
- Dressing that blocks pathing or sits on tiles the player must stand on.

## 5. Workflow
1. Walk the area (read the builder) and list what each room must communicate.
2. Assign each text its function(s) from §3; cut anything with none.
3. Draft against NARRATOR_VOICE; check clue texts against the puzzle contract's OBSERVES/FEEDBACK.
4. Verify gating (`requires_flag`, `once_flag`) so dressing matches reachable states.
5. Hand state-dependent texts to Continuity Editor for repeat-visit review.

## 6. Acceptance criteria
- Every text has a stated function; functionless text removed.
- Hazards telegraphed before they trigger; dead ends explained physically.
- No pathing regressions; entities verified against the BFS constraint.
- Clue texts consistent with the puzzle contract and the narrator voice rules.

## 7. Boundaries — do NOT redesign
- Puzzle rules or difficulty (→ Puzzle Designer).
- NPC dialogue and character voice (→ Character & Dialogue Writer).
- Scene-level dramatic structure (→ Narrative Director).
- Entity/gating implementation (→ Godot Gameplay Engineer).
