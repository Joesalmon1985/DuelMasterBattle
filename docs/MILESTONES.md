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
| M11 | **Encounter progression** | Ruleset model, 4 encounters, Archmage regression | Done |
| M12 | **PRD doc + terminology** | `docs/PRD.md`, Rules Canon, Essence/Locus/Fracture terms | In progress |
| M13 | **Ruleset expansion** | 1–8 loci, cast times, Last Stand, difficulty profiles | Pending |
| M14 | **Real-time sim** | `DmbRealtimeDuelSim`, cast windows, Clash/Stalemate tests | Pending |
| M15 | **Mobile duel UI** | Portrait layout, difficulty select, realtime client wiring | Pending |
| M16 | **Attack animations** | Bolt travel, barrier impact, aggregate feedback reveal | Pending |
| M17 | **Production visuals + audio** | Essence/locus/barrier art, theme, sound cues | Pending |
| M18 | **Content + tutorial** | Help screen, settings, tutorial overlays, boss optional | Pending |
| M19 | **Android release QA** | Export preset, expanded tests, release notes | Pending |

## Priority rule

1. Pure game rules tested
2. Real-time sim authoritative (not UI-only timers)
3. No positional feedback leaks
4. Godot playable vertical slice
5. Scripted UI verification
6. Polish, web, Android

## Duel flow (target — PRD §7)

**Real-time:** both duelists act independently with min/max cast windows; attacks resolve with aggregate feedback; Last Stand and Clash/Stalemate outcomes supported.

Legacy alternating flow (`DmbSequentialDuelGame`) retained for regression until realtime client ships.

## References

- **[PRD.md](PRD.md)** — product requirements and implementation phases (§29)
- [ENCOUNTER_DESIGN.md](ENCOUNTER_DESIGN.md)
- [MANUAL_PLAYTEST.md](MANUAL_PLAYTEST.md)
