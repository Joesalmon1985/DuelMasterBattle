# Milestones

Each milestone commits only after tests + smoke pass. Commit message states milestone passed.

| # | Name | Gate |
|---|------|------|
| M0 | Repo audit + skeleton | Docs, roles, `.gitignore`, branch |
| M1 | Pure Python rules | pytest green + `shared_fixtures/` generated |
| M2 | tkinter prototype | Minimal functional proof (defer if threatens M3/M4) |
| M3 | Godot rules port | Headless sim tests green + shared fixtures parity |
| M4 | **Godot playable Human vs Bot** | Full 14-step flow works locally; **hard commit gate** |
| M5 | **UI smoke test** | Scripted UI smoke + `MANUAL_PLAYTEST.md` |
| M6 | Solver bot | Deferrable |
| M7 | Visual polish | Deferrable |
| M8 | Web export | Deferrable |
| M9 | Android export notes | Deferrable |
| M10 | Final QA | All required tests + release docs |

## Priority rule
1. Pure game rules tested
2. Python prototype as fast proof
3. Godot playable Human vs Bot vertical slice
4. Scripted UI verification
5. Only then: polish, web, Android

## Sequential flow (this run)
Bot attacks human code first, then human attacks bot code. Round-by-round alternating duel is a later version.
