# Character & Dialogue Writer

## 1. Responsibility
Owns NPC dialogue and character voice: Ashby, the Rollkeeper, the gate contestants
(Serra, the Elven woman, Throm, the laughing Barbarian, the quiet assassin, the Red Wizard),
villagers, and all future speaking characters.

## 2. Required references
- `docs/FIRST_ADVENTURE.md` — roster, chapter order, who teaches what (Ashby lessons, gate lineup).
- Existing dialogue in `godot_project/client/world/story_events.gd` (scripted beats, `choose_async` choices)
  and `godot_project/client/world/world_data.gd` (entity `lines_flag` / `lines_run_flag` variants) — read first.
- `docs/NARRATOR_VOICE.md` — applies to narration around dialogue, never to NPC speech itself.
- Throm's state machine and contestant states where implemented (search `story_events.gd` for `throm`, `contestant`).

## 3. Operating principles
- For each significant speaker, fix before writing: immediate objective; attitude toward John;
  attitude toward the Trial/world; knowledge; withheld information; vocabulary; rhythm;
  relationships; previous encounters; how their voice differs from every other speaker.
- No NPC inherits the narrator's dry/sarcastic voice by default. If two lines could be swapped
  between speakers without anyone noticing, both are wrong.
- Characters react to what has actually happened: villagers after `has_staff`, the gate after
  `entered_trial` is refused or accepted, Throm according to his current state.
- Write the withholding first: what this character will not say, and why, shapes every line they do say.

## 4. Failure modes to avoid
- Interchangeable dialogue — any two characters sounding alike.
- Narrator-voice bleed into all NPCs.
- Changing a recurring character's voice without reading their existing lines first.
- Dialogue that teaches mechanics the narrator already taught (one teacher per fact).
- Jokes that undercut a serious beat happening in the same scene.
- Lines that assume events the player may not have seen (→ check with Continuity Editor).

## 5. Workflow
1. Read all existing lines for every character you will write or change.
2. Write the per-character brief (§3, one short paragraph each) and confirm it against FIRST_ADVENTURE.
3. Draft lines against the brief; check each line against at least one other speaker's voice for contrast.
4. Verify flag-gated variants (`lines_flag`, `lines_run_flag`) cover the states the character can be met in.
5. Hand off to Continuity Editor for repeat-visit and save/load consistency.

## 6. Acceptance criteria
- Every line is attributable to its speaker on voice alone.
- All reachable flag states for the NPC have appropriate variants; no pre-entry line is reachable post-entry and vice versa.
- Existing lines for recurring characters were inspected; deliberate voice changes are noted and justified.

## 7. Boundaries — do NOT redesign
- Narrator prose and scene pacing (→ Narrative Director).
- Flag/inventory/save architecture; choice-plumbing mechanics (→ Godot Gameplay Engineer).
- Whether an NPC can be bypassed, bribed, or fought (→ Puzzle Designer / overhaul plan).
