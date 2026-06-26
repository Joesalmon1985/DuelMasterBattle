# Milestones

Each milestone commits only after tests + smoke pass. Commit message states milestone passed.

| # | Name | Gate | Status |
|---|------|------|--------|
| M0 | Repo audit + skeleton | Docs, roles, `.gitignore`, branch | Done |
| M1 | Pure Python rules | pytest green + `shared_fixtures/` generated | Done |
| M2 | tkinter prototype | Minimal functional proof | Done (may lag Godot) |
| M3 | Godot rules port | Headless sim tests green + fixture parity | Done |
| M4 | **Godot playable Human vs Bot** | Full flow works locally | Done (alternating duel) |
| M5 | **UI smoke test** | Scripted smoke + `MANUAL_PLAYTEST.md` | Done (dual encounter paths) |
| M6 | Solver bot | Candidate elimination + difficulty tiers | Done |
| M7 | Visual polish | Wizard portraits, headers, help panels | Partial |
| M8 | Web export | Local export script; deploy deferrable | Partial (local only) |
| M9 | Android export notes | Documented | Deferrable |
| M10 | Final QA | Tests + release docs | Ongoing per branch |
| M11 | **Encounter progression** | Ruleset model, 4 encounters, Archmage regression | Done (`feature/encounter-progression-rulesets`) |

## Priority rule
1. Pure game rules tested
2. Python prototype as fast proof
3. Godot playable vertical slice
4. Scripted UI verification (include new UI in smoke)
5. Encounter configurability without breaking Archmage
6. Polish, web, Android

## Duel flow (current)
**Alternating:** both secrets at Cast pattern → human attacks first → one attack per side per turn → dual visible histories → solve or exhaustion draw.

Not the old bulk-bot-then-human sequential model.

## References
- [ENCOUNTER_DESIGN.md](ENCOUNTER_DESIGN.md)
- [MANUAL_PLAYTEST.md](MANUAL_PLAYTEST.md)
