# G04 known defects / limits (Reuse Repair handoff)

- Automated PASS is necessary but not sufficient — Joe's walk/click/spell and hazard Challenge checklist is decisive.
- Local Windows tool is Godot 4.5.1 while pack pin is 4.4.1; behaviour should be rechecked on the pinned engine when available.
- Dense melee unit labels may overlap cosmetically.
- Spellbook overlay can intercept chrome Wait pointer hits on other gates; production Wait still works via HUD signal.
- Headless runs may log ObjectDB/resource leak warnings at exit; playable markers still emit.
- Mid-duel visual save/resume through GameBoard UI is implemented via checkpoint APIs; Joe should still exercise resume in the manual checklist.
- Ensemble depth commits `58ea2d2` / `6f7be0f` are a separate follow-up and are not on this branch.
