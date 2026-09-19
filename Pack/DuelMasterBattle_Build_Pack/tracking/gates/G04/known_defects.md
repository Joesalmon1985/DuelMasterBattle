# G04 known defects / limits (Reuse Repair handoff)

**Gate status:** PASS (Joe Salmon, 2026-09-19T22:05:00Z) against
`75b7f539aa1916fb6c0a5f156be3efa5184dd7eb` on main via
`15eadbd7dd82ebb56167c745e4998f2fa06809fb`.

## Non-blocking limits retained for history

- Automated PASS was necessary but not sufficient; Joe's walk/click/spell and
  hazard Challenge checklist was decisive and is now accepted.
- Local Windows tool may be Godot 4.5.1 while pack pin is 4.4.1.
- Dense melee unit labels may overlap cosmetically.
- Headless runs may log ObjectDB/resource leak warnings at exit; playable
  markers still emit.
- Ensemble depth commits `58ea2d2` / `6f7be0f` remain a separate follow-up and
  were not part of the accepted G04 merge.

## Repair observations that Joe accepted

- Spellbook is a bounded centred panel (not full-viewport); D-pad/action hide
  while open; real pointer open → Shield → targeting → cancel → Close verified
  at 450×800, 720×1280, 1280×720.
- Leased Hazard Challenge result/menu use Continue / Abandon challenge →
  `_return_to_world` (no Play again / Restart loop).
- Prior playtest fixes retained: battle actors release on travel; Ward taps use
  SpellSlot.pressed + int pools; Mira uses WorldInteractionLabel.
