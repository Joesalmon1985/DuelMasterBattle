# Release Notes — Duel Master Battle v0.1.0

## Branch
`feature/duel-mastermind-build`

## Summary
Playable **Human vs Bot** duelling Mastermind vertical slice in Godot 4.4.1, backed by tested pure rules in Python and GDScript with shared golden fixtures.

## What's included
- Pure game rules: 4 pegs, 10 colours, repeats allowed, Mastermind feedback, 12-guess limit
- Sequential flow: bot guesses your code → you guess bot's code
- Random legal bot
- Python prototype (tkinter) + pytest suite
- Godot 4.4.1 client: main menu, peg selector, colour picker, bot board, result screen, restart
- Shared JSON fixtures for Python/Godot parity
- Headless Godot rules tests + UI smoke test
- Web export built locally (`godot_project/build/web/`)

## Tests run
| Suite | Result |
|-------|--------|
| Python pytest (24 tests) | **passed** |
| Godot rules tests (4 modules) | **passed** |
| Godot UI smoke test | **passed** |

## Manual playtest
**Not performed** in this run environment (no visible Godot window). Scripted UI smoke test passed. See `docs/MANUAL_PLAYTEST.md` for local verification steps.

## Deferred
- Solver bot (feedback-filtering)
- Advanced animations / styling
- Cloudflare Pages deployment (export built; not uploaded)
- Android APK build (templates not installed; see `docs/ANDROID_EXPORT.md`)

## Known issues
- Harmless Godot shutdown noise: "resources still in use at exit" in headless test runs
- Web build may need COOP/COEP headers on hosting (see deploy doc)

## Launch locally
```bash
export GODOT=$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64
"$GODOT" --path godot_project
```

## Stale Godot processes
None remaining after `tools/godot_cleanup.sh`.
