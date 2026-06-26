# Art Asset Manifest — Draft Placeholders

Regenerate:
```bash
python3 tools/generate_draft_sprites.py
```

All assets are **draft flat PNG placeholders** (PIL-generated). Not final art.

## Sprites (`godot_project/assets/sprites/`)

| File | Purpose | Integrated |
|------|---------|------------|
| `player_wizard.png` | Player wizard portrait | Yes — `game_board.gd` player column |
| `enemy_wizard.png` | Enemy wizard portrait | Yes — `game_board.gd` enemy column |
| `duel_background.png` | Panel/background frame | Yes — board background (subtle) |

## Icons (`godot_project/assets/icons/`)

| File | Purpose | Integrated |
|------|---------|------------|
| `magic_*.png` (×10) | Magic type picker buttons | Yes — `magic_picker.gd` (filtered per encounter pool) |
| `point_*.png` (×4) | Shield/Body/Staff/Mind | Yes — point header rows (count matches encounter slots) |
| `feedback_hit.png` | Hit marker | Partial — feedback text labels in `feedback_display.gd` |
| `feedback_weakness.png` | Weakness marker | Partial — feedback text labels |
| `feedback_unaffected.png` | Unaffected marker | Partial — feedback text labels |

## Loading
Runtime load via `DmbArt.load_texture()` (`client/scripts/art.gd`). Missing files return null without crashing.

## Verification
Godot headless: `tools/run_godot_tests.sh` includes `test_assets.gd`. UI smoke asserts wizard portraits load.
