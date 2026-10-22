# Ledger: polish for watching (0.5.1, branch `feature/polish-watching-feel`)

Design and the per-event checklist: `docs/POLISH_WATCHING_FEEL.md`. Budget: the owner gave three and a half hours (22 Oct 2026, from 19:14).
Base: `feature/village-minigames` at `69165b95` (the 0.5.0 minigames). Merging into `main` is the owner's call.

Note on the working tree: when this branch was cut, the checkout carried uncommitted changes that are not this branch's (the rival's name in the
AI wizard, a name prompt in the main menu, test and data edits, `observations.json`). They were left as they were, uncommitted; this ledger's
commits add only the polish files. The APK built from this tree carries them.

## Milestones

- [x] P0 Branch, orientation (the art layer has no tweens or particles; the table and the cards are static; `Sfx` is procedural).
- [x] P1 The world's watching layer `client/hybrid/ambience.gd`: deliveries (dust, the ware icon, a clack), pickups, chimney smoke for working
  buildings, the construction arc, completions (ring, sparks, chime), felled trees (chips, chop), saplings, new units, the waiting crate; rationed
  sounds; wired into `hybrid_world.gd` (observe on every snapshot, step in `_process`, draw after the entities, view bounds from `_draw`).
- [x] P2 The table: `table_fx.gd` (tap rings, result banner, sparks), the panel's pop-in, the message flash, the staggered deal, tumbling dice,
  the shake and red message on a refused move; widgets pass themselves to `widget_act`.
- [x] P3 Menus and cards: `press_feel` on every themed button, `pop_in` on cards and main-menu overlays, `fade_in` for a card's next page, `swish`.
- [x] P4 Version 0.5.1 (Android code 6; protocol 4 unchanged, the messages did not change shape), docs, the headed test's two new checks.
- [ ] P5 Headed evidence, the APK, the phone install (see the session log).

## Session log

- 22 Oct 2026 19:14 Start. Branch cut from `feature/village-minigames`. Read `hybrid_world.gd`, `hybrid_art.gd`, `industry_view.gd`, the table and
  widgets, `visual_theme.gd`, `narrative_card.gd`, `sfx.gd`, the snapshot's entity rows (`working`, `constructing`, `cargo`, `carrying`, `stage`,
  `status_text`).
- 19:30 to 19:55 Wrote `ambience.gd`, `table_fx.gd`, the sounds, the theme helpers, the table and widget changes, the card and menu pops.
  Godot `--check-only` on every changed script: clean (the `LanSession` autoload errors are the checker's, as before).
- 19:56 Headed `run_hybrid_minigames.gd` (rps, yahtzee, slide, whist, guesswho) started with `HYBRID_SHOT_DIR=WizardRTSHybrid/docs/evidence/polish`.
