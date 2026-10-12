# DuelMasterBattle — the owner review the long run must deliver

This is a specification for the finished review experience. The launcher, debug pages and checkpoints below are proposed work for Cursor; they have not been implemented by this document.

The existing P0 plan would deliver a baseline and stop before repairing the game. Use `DuelMasterBattle_Full_Run_Cursor_Prompt.txt` as its replacement execution instruction. It authorizes P0–P9, keeps internal verification, and defers your subjective approval until the end.

## The launch experience

Double-click **Play Visual Review.bat**. The actual integrated game opens with an isolated review save. Click **Spellbook → Review → Start review**. These are the proposed labels Cursor must implement and verify, then reproduce exactly in its final start sheet.

Keep the full book open while reading or checking a detail. Click **Close and watch** when you want to see activity happen. A small card shows the current task without covering the world. Use **Wait once** only when a chapter explicitly asks for a World Turn; standing in an area lets real Game Time drive industry.

You should not need a terminal, Python logs, raw node numbers, test fixture names or a search through screenshot folders. Cursor should supply named, replay-verified checkpoints close to the relevant events.

## A 28-minute review

| Time | Simple task | Things to watch | Optional spellbook detail |
|---|---|---|---|
| 0–3 min | Move, select a person, Observe/Talk, find an exit and Travel once. | Can you identify yourself, the place, people and controls? Does travel make sense? | This place; selected person. |
| 3–7 min | Follow a loaded cart through the prepared delivery and construction sequence. | Can you connect its cargo, destination and completed building/road? Is the consequence noticeable? | Economy: actual cargo, destination and order state. |
| 7–10 min | Watch a working factory complete a soldier, then select that soldier. | Is it clear the soldier came from industry? Does it feel like a persistent person? | Industry meter and Person/unit link. |
| 10–13 min | Advance the prepared round and inspect the affected facility, cart or soldier. | Can you perceive factions developing technology without managing their cards? | Technology: before/after hand, acquisition, activation and actual effect. |
| 13–17 min | Inspect a hazard's blocked work/transit; advance the responder's seat; watch recovery. | Can you connect danger → soldiers responding → hazard removal → work restarting? | Hazard target, spent activation, suppression/recovery receipts. |
| 17–20 min | Witness the prepared hostile contact and aftermath. | Can you tell who is fighting and why? Are casualties, withdrawal and building damage consequential? | Relations; formation objective; battle result. |
| 20–25 min | Challenge the selected manifestation, enter a ward, play the retained duel and return. | Does the full duel work by pointer? Does the same world return cleanly with the correct outcome? | Encounter/visit state, only if something seems wrong. |
| 25–28 min | Save, quit, relaunch/load; then trigger the supplied near-era checkpoint. | Do the same people and changes persist? Does an era change feel like history happening to a familiar world? | Save continuity; known history; core/legacy changes. |

The book must give the actual relevant names, controls, route and expected number of Wait presses for each build. The durations are preparation targets, not a promise about the current game. For a long duel, an optional verified mid-duel save can shorten the review without pretending you completed an entire encounter. The full pointer sequence remains Cursor's responsibility to test.

For each chapter choose **Clear**, **Unclear** or **Broken**, and optionally add one sentence. Use **Capture issue** to attach the screenshot and technical context automatically. **Replay chapter** reloads that chapter's verified save. **Next chapter** loads the next recorded checkpoint; it does not force the current event to succeed.

The final question is: **Which moment still feels like a separate technical demo?**

Optional extras: full Future→Prehistoric cycle, legacy industry, narrow/mobile layout or a particular policy's behaviour. You should not manually check hundreds of arithmetic or replay assertions.

## What the debug spellbook should show

The ordinary player sees learned, contextual information. The review/debug book can additionally show the facts needed to understand whether a system is connected:

- Cargo, reservations, delivery/order progress and the actual reason a route is blocked.
- Real factory progress, input constraints and the produced Person/unit.
- Active faction/round, policy identity, diplomatic state, draft hands/picks and activated effects.
- Formation objective and activation, selected hazard, treatment and economic recovery.
- Era conversion, legacy state, identity/history and save/reload continuity.

These are read-only explanations of the actual world. Opening a page must not create an event, alter the simulation or grant hidden knowledge in normal play. Useful controls are checkpoint loading, normal Wait, save/reload, Close and watch, and issue capture.

The existing book includes reusable host/model/binders and pointer tests. Some older gate pages also contain state-changing fixture tools such as Clear hazard and Set health to 25%. Cursor must keep those out of this owner journey and reuse the book's presentation without importing all its old fixture controls.

## How the long run should finish

Cursor should continue through all ten phases without requesting your approval between them. It should retain internal tests and evidence, reassess failed approaches instead of stopping after a fixed number of attempts, and record resumable progress if the environment interrupts the run.

Its final message should say exactly what to double-click, what to click in the spellbook, where the short start sheet is, and what still needs your judgment. Automated readiness and your approval are different statuses. A completed P0, inaccessible screenshots or missing gameplay repairs must not be described as a finished visual-review build.

The original audit's detailed tests and evidence requirements remain in force. The new master prompt changes execution scheduling, adds the spellbook review requirements, and permits clearly labelled alternative normal seeds for rare-event checkpoints. It does not claim that all of this can necessarily finish in a single night.
