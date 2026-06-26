# Duel Master Battle

**Real-time wizard ward duel** — mobile-first Human vs rival wizard with independent cast windows, encounter-driven rules (1–8 loci), and global difficulty selection. Built in Godot 4.4.1 with tested rules in Python and GDScript.

## Quick start — play locally

```bash
export GODOT=$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64
export GODOT_USER_DATA_DIR="$(pwd)/godot_project/.godot_user"
"$GODOT" --path godot_project
```

Select **difficulty** → **encounter** → **Start duel** → set ward → **Lock ward** → build attacks and **Cast** in real time → result.

Encounters: **Blue Apprentice** (tutorial) · **Thorn Adept** · **Mirror Mage** · **Archmage Duel** · **Eightfold Warden** (boss).

See [**PRD**](docs/PRD.md) for full product requirements.

## Web export (local)

```bash
tools/export_web.sh
cd godot_project/build/web && python3 -m http.server 8080
```

## Android export

Configure Godot Android export templates, then export preset **Android** → `godot_project/build/android/`. See [ANDROID_EXPORT.md](docs/ANDROID_EXPORT.md).

## Run tests

```bash
cd python_prototype && python3 -m pytest -q
tools/run_godot_tests.sh
tools/run_godot_ui_smoke.sh
```

Regenerate draft sprites:

```bash
python3 tools/generate_draft_sprites.py
```

## Project structure

```
godot_project/
  sim/               DmbRealtimeDuelSim, rules, bots, encounters
  client/            Portrait UI, animation layer, EncounterSession
  assets/            Essence/locus/barrier art (draft placeholders)
python_prototype/    Pure rules + pytest
docs/PRD.md          Product requirements (source of truth)
```

## Docs

- [**Product requirements (PRD)**](docs/PRD.md)
- [Game rules](docs/RULES.md)
- [Encounter design](docs/ENCOUNTER_DESIGN.md)
- [Release notes](docs/RELEASE_NOTES.md)
