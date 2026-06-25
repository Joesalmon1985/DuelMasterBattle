# Duel Master Battle

Two-player **duelling Mastermind** reskinned as a **wizard duel**: configurable encounters (1–4 points, filtered magic pools, variable attack limits). Default **Archmage Duel** is the full game — 4 points, 10 magic types, 12 attacks. Playable **Human vs Bot** in Godot 4.4.1.

## Quick start — play locally

```bash
export GODOT=$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64
export GODOT_USER_DATA_DIR="$(pwd)/godot_project/.godot_user"
"$GODOT" --path godot_project
```

Select an **encounter** on the main menu → **Start duel** → set your pattern → **Cast pattern** → alternate attacks (you go first) → result → **New duel** or **Back to menu**.

Encounters: **Blue Apprentice** (tutorial) · **Thorn Adept** · **Mirror Mage** · **Archmage Duel** (classic 4/10/12).

Draft placeholder sprites live under `godot_project/assets/` (see `docs/ART_ASSET_MANIFEST.md`).

## Web export (local)

```bash
tools/export_web.sh
cd godot_project/build/web && python3 -m http.server 8080
# Open http://localhost:8080
```

Web build output is **not committed** to git. See [Deploy to Cloudflare Pages](docs/DEPLOY_CLOUDFLARE_PAGES.md) for hosting steps.

**Current limitations:** desktop-oriented layout, draft placeholder art, Expert bot may be slower during enemy attacks, Godot 4 web may need COOP/COEP headers (documented in deploy guide). Cloudflare deployment is **not** claimed unless you verify it yourself.

## Run tests

```bash
cd python_prototype && python3 -m pytest -q
PYTHONPATH=. python3 tests/generate_fixtures.py   # after rule changes
tools/run_godot_tests.sh
tools/run_godot_ui_smoke.sh
tools/godot_check.sh && tools/godot_cleanup.sh
```

Regenerate draft sprites:

```bash
python3 tools/generate_draft_sprites.py
```

Evaluate bot difficulty (Python only):

```bash
cd python_prototype && python3 scripts/evaluate_bots.py          # 100 secrets
cd python_prototype && python3 scripts/evaluate_bots.py --quick  # 8 secrets
```

## Project structure

```
shared_fixtures/     JSON golden files
python_prototype/    Pure rules, solver, NN experiment (Python only)
godot_project/
  sim/               Authoritative rules + bots
  client/            Wizard-duel UI
  assets/            Draft PNG sprites/icons
  build/web/         Local web export output (gitignored / not committed)
tools/               Test runners, sprite generator, export_web.sh
docs/                Rules, playtest, NN experiment, art manifest
```

## Docs

- [Game rules](docs/RULES.md)
- [Encounter design](docs/ENCOUNTER_DESIGN.md)
- [Manual playtest](docs/MANUAL_PLAYTEST.md)
- [Visual capture checklist](docs/VISUAL_CAPTURE.md)
- [Bot difficulty tuning](docs/BOT_DIFFICULTY.md)
- [Deploy to Cloudflare Pages](docs/DEPLOY_CLOUDFLARE_PAGES.md)
- [NN experiment](docs/NN_BOT_EXPERIMENT.md)
- [Art manifest](docs/ART_ASSET_MANIFEST.md)
- [Release notes](docs/RELEASE_NOTES.md)

## License

See repository for license terms.
