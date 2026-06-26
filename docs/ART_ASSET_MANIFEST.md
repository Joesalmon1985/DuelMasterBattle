# Art Asset Manifest — Composite Visual Polish

## Regenerate composite assets

```bash
python3 tools/generate_composite_sprites.py
```

Outputs **2× vector-composite cutout PNGs** under `godot_project/assets/generated/composite/`:

| Folder | Contents |
|--------|----------|
| `wizards/{archetype}/` | Layered body parts + `manifest.json` |
| `essences/{slug}/` | core_glyph, inner_glow, outer_aura, trail, spark |
| `wards/` | Barrier rings, surface, cracks, instability |
| `effects/` | impact_flash, shockwave, fracture_glyph, echo_ring, fade_mote |
| `ui/` | button_gem, timer_ring |
| `loci/{slug}/` | rune_empty, rune_filled |

Legacy flat icons in `assets/icons/` remain as fallbacks.

## Runtime loading

`DmbArt` (`client/scripts/art.gd`) resolves composite paths. Components:

- `CompositeWizard` — layered wizard assembly + idle/cast tweens
- `WardBarrier` — layered ward states
- `EssenceToken`, `LocusSocket`, `FeedbackChip`, `CastButton`, `CastTimer`
- `SpellVfx` — projectile + impact layers

## Visual theme

Constants in `client/scripts/visual_theme.gd` (preload as `_VT`). Art direction: `docs/ART_BIBLE.md`.

## Verification

```bash
tools/run_godot_tests.sh      # includes test_assets.gd
tools/run_godot_ui_smoke.sh
tools/capture_visual_qa.sh    # screenshot QA pipeline
python3 tools/visual_qa_report.py
```

## Draft generator (legacy)

```bash
python3 tools/generate_draft_sprites.py
```

Flat placeholders for rapid iteration; superseded by composite generator for in-game visuals.
