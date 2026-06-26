# Art Bible — Duel Master Battle

Shared visual language for vector-composite cutout assets, UI skin, and VFX.

## Export scale

- Reference viewport: **720 × 1280** portrait
- Asset generation scale: **2×** (`ASSET_SCALE = 2`)
- Import: transparent PNG, filter on, mipmaps off for UI

## Master palette

| Role | Hex | Usage |
|------|-----|-------|
| Background deep | `#1a1530` | Duel backdrop gradient base |
| Background mid | `#2d2550` | Panel gradients |
| Panel fill | `#1e1a35` | Primary panels |
| Panel accent border | `#6b5ce7` | Rounded panel rim |
| Accent gold | `#ffc947` | Cast ready, highlights |
| Accent cyan | `#4fc3f7` | Player aura |
| Text primary | `#f2f0ff` | Status, labels |
| Text secondary | `#b8b0d8` | Hints, history |

## Essence colours

Use [`colour_data.gd`](../godot_project/client/scripts/colour_data.gd) `COLOURS` array; generator applies outline + glow per essence.

## Feedback colours

| Type | Hex | Shape language |
|------|-----|----------------|
| Fracture | `#66ff99` | Jagged crack glyph |
| Echo | `#ffb84d` | Concentric ring |
| Fade | `#a8a8b8` | Dissolving mote |

## Outline

- Stroke width: **2px** at 1× display (4px at 2× export)
- Colour: `#1a1030` at 80% opacity (dark rim)
- Inner highlight: `#ffffff` at 25% on top edge

## Shadow

- Offset: `(3, 5)` px at 1×
- Blur: 6px Gaussian pass
- Colour: `#000000` at 45%

## Glow / rim light

- Outer glow radius: 8–16px
- Pulse range: alpha 0.4 → 0.9 for cast-ready states
- Rim tint: essence or accent colour at 50%

## Shape language

- **UI panels:** rounded rect, radius 16px, inner glow
- **Gem buttons:** octagonal/circular facet, gold rim when primary
- **Essence tokens:** medallion with internal glyph
- **Locus sockets:** rune ring + name chip
- **Wards:** concentric rings + rotating rune band

## Wizard archetype accents

| Archetype | Palette accent |
|-----------|----------------|
| blue_apprentice | Soft blue `#5eb3ff` |
| thorn_adept | Green/brown `#6bbf59` |
| mirror_mage | Half light `#fff5cc` / shadow `#4a3060` |
| archmage | Gold/arcane `#ffd54f` / `#9c7cff` |
| eightfold_warden | Violet/gold `#7e57c2` / `#ffc947` |
| player | Blue/purple `#6b8cff` |

## Animation timing (seconds)

| Action | Duration |
|--------|----------|
| Button press | 0.10 |
| Essence pop | 0.16 |
| Cast wind-up | 0.35 |
| Projectile travel | 0.50 |
| Impact swirl | 0.35 |
| Feedback reveal | 0.55 |
| Victory burst | 1.0 |

## Non-goals

- Pixel art, monolithic sprites, flat unshaded squares, per-locus feedback visuals
