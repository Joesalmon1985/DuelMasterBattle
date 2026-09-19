# G04 known defects / limits (Reuse Repair handoff)

- Automated PASS is necessary but not sufficient — Joe's walk/click/spell and hazard Challenge checklist is decisive.
- Local Windows tool is Godot 4.5.1 while pack pin is 4.4.1; behaviour should be rechecked on the pinned engine when available.
- Dense melee unit labels may overlap cosmetically.
- Headless runs may log ObjectDB/resource leak warnings at exit; playable markers still emit.
- Mid-duel visual save/resume through GameBoard UI is implemented via checkpoint APIs; Joe should still exercise resume in the manual checklist.
- Ensemble depth commits `58ea2d2` / `6f7be0f` are a separate follow-up and are not on this branch.
- **Retest after 2026-09-19 repair (this candidate):**
  - Spellbook is a bounded centred panel (not full-viewport); D-pad/action hide while open; real pointer open → Shield → targeting → cancel → Close verified at 450×800, 720×1280, 1280×720.
  - Leased Hazard Challenge result/menu use Continue / Abandon challenge → `_return_to_world` (no Play again / Restart loop).
  - Prior playtest fixes retained: battle actors release on travel; Ward taps use SpellSlot.pressed + int pools; Mira uses WorldInteractionLabel.
- Status remains **AWAITING_HUMAN / FIX_REQUIRED** until Joe retests the manual G04 checklist. Do not mark PASS from automation alone.
