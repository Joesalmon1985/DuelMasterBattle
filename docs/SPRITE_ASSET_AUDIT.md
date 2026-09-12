# Duel Master Battle Sprite Asset Audit

## Executive Summary

This audit catalogues all visual assets in the Duel Master Battle repository to establish a foundation for an art pipeline that generates game-appropriate pixel sprites while preserving the existing visual style.

---

## File Structure Overview

| Category | Directory | File Count | Size Range |
|---|---|---|---|
| **Characters** | `assets/pixel/chars/` | 192 PNG files | 16×24 or 18×26 pixels |
| **Creatures** | `assets/pixel/creatures/` | 72 PNG files | 16×16 (world) or 64×64 (portrait) |
| **Portraits** | `assets/pixel/portraits/` | 10 PNG files | 96×96 pixels |
| **Props** | `assets/pixel/props/` | 40 PNG files | 16×16 to 32×32 pixels |
| **Tiles** | `assets/pixel/tiles/` | 14 PNG files | 16×16 pixels |
| **Sprite Sheets** | `assets/sprites/` | 8 files | 96×128 or 320×480 pixels |
| **Effects** | `assets/generated/composite/effects/` | 6 PNG files | 192×192 pixels |
| **UI Icons** | `assets/icons/` | 20 PNG files | Various (16×16 to 32×32) |
| **Backdrops** | `assets/pixel/backdrops/` | 1 PNG file | Full viewport size |

---

## Character Sprites Deep Analysis

### Core Convention: 16×24 pixels per frame, RGBA with transparency

All standard character sprites use a consistent **16×24 pixel** canvas. Two animation frames per direction (`_0`, `_1`), with left/right frames mirrored (same file, Godot handles mirroring).

### Frame Structure per Character

| Direction | Frame 0 | Frame 1 | Purpose |
|---|---|---|---|
| `down` | Walking frame 1 | Walking frame 2 | Forward animation |
| `left` | Walking frame 1 | Walking frame 2 | Left-facing (mirrored to right) |
| `right` | Walking frame 1 | Walking frame 2 | Right-facing (mirrored from left) |
| `up` | Walking frame 1 | Walking frame 2 | Backward animation |

### Character Type Breakdown

| Type | Count | Example Files | Frame Size |
|---|---|---|---|
| **Standard adventurers** | 8 types (assassin, blue_mage, dwarf, elder, elf, knight, red_mage, shepherd) | `knight_down_0.png`, `elf_up_1.png` | 16×24 |
| **Named NPCs** | 6 types (child, farmer, john, matron, miner, official) | `farmer_down_0.png`, `miner_left_1.png` | 16×24 |
| **Special/unique** | 4 types (ivy, hedge_mage, igbut) | `hedge_mage_down_0.png` | 18×26 (slightly taller) |
| **Worker/peasant** | 3 types (villager_a, villager_b, woodcutter) | `woodcutter_down_0.png` | 16×24 |
| **Combat-focused** | 4 types (reaper, official, etc.) | `reaper_down_0.png` | 16×24 |

**Total unique character bases**: 96 (each with 2 directional variants, some with 4 directions)

### Transparency Analysis

| Character Type | Avg. Transparency | Notes |
|---|---|---|
| woodcutter | 23.2% | Low transparency — tight bounding box |
| farmer | 59.6% | Moderate — robe/garments extend outward |
| miner | 69.3% | High — mining gear, open spaces |
| knight | 53.9% | Medium — armor with gaps |
| dwarf | 53.9% | Medium — similar to knight |
| elf | 58.3% | Medium-high |
| assassin | 58.3% | Medium-high |
| blue_mage | 35.3% | Lowest — tighter fit |
| red_mage | 35.3% | Lowest — similar to blue_mage |
| villager_a | 58.3% | Medium |
| villager_b | 58.3% | Medium |
| child | 59.6% | Similar to farmer |

**Key insight**: Transparency varies by character design, not by error. Designs with flowing garments or larger equipment have more transparent pixels.

### Outline Style

- **1-pixel outline** in darkest available color against the base tone
- Outlines define silhouette clearly at 16×24 resolution
- No anti-aliased outlines — hard pixel edges
- Outline color depends on base tone (dark brown for woodcutter, dark gray/black for knights, etc.)

### Shading Style

- **2-3 tone shading** per character: base color, mid-tone, highlight
- Shading follows form: light source from upper-left (consistent across set)
- Cell-shaded regions, no soft gradients
- Minimal anti-aliasing between shades
- Shading defines muscle mass, fabric folds, equipment details

### Perspective

- **Top-down isometric-ish** — not true isometric (no 2:1 ratio)
- Characters face straight down when idle (`down` direction)
- Movement animations show slight position shift between frames `_0` and `_1`
- No forced perspective — characters are drawn at a consistent scale

### Character Proportions

- **16 wide × 24 tall** — roughly 2:3 aspect ratio
- Head occupies approximately top 6 pixels
- Body/torso: middle 12 pixels
- Legs/feet: bottom 6 pixels
- Arms/weapons extend above head in some frames
- Consistent across all 16×24 characters despite different designs

### Terrain & Tiles

| Tile Type | Example | Notes |
|---|---|---|
| `ash.png` | Ash/char tile | 16×16 |
| `bridge.png` | Bridge segment | 16×16 |
| `cave_floor.png` | Cave floor | 16×16 |
| `cave_wall.png` | Cave wall | 16×16 |
| `dirt.png` | Dirt ground | 16×16 |
| `grass.png` | Grass tile | 16×16 |
| `grass_dark.png` | Dark grass variant | 16×16 |
| `path.png` | Path tile | 16×16 |
| `roof.png` | Roof piece | 16×16 |
| `wall.png` | Wall segment | 16×16 |
| `water.png` | Water tile | 16×16 |
| `wood.png` | Wood/plank tile | 16×16 |
| `bridge.png` | Bridge | 16×16 |

All tiles are **16×16 pixels**, designed for a top-down grid layout. No animation, single-frame static tiles.

### Prop Analysis

Props vary in size but many are 16×16 or 32×32:
- Small: `book_black.png` (16×16), `rock.png` (16×16)
- Medium: `door_closed.png` (16×22), `miner_house.png` (varies)
- Large: `door_dungeon.png` (32×32), `tree_0.png` (varies)

Props are **single-frame**, no animation. Some have transparency varying from 20-70%.

### Creature Analysis

- **World sprites**: 16×16 pixels (e.g., `bloodbeast_world_0.png`)
- **Portrait sprites**: 64×64 pixels (e.g., `bloodbeast_portrait_0.png`)
- Two-frame convention similar to characters (`_0`, `_1`)
- Used bestiary/enemy encounters

### Portrait Analysis

- 10 portraits at **96×96 pixels**
- Full-body or head-shot representations
- Used for UI, collections, bestiary entries
- No animation frames

### Effect Sprites

- 6 effect files at **192×192 pixels**
- Composite effects (rings, glyphs, auras)
- Used for spell effects, combat feedback
- Single-frame, likely scaled down in-engine

### Sprite Sheets (Large Assets)

| File | Dimensions | Description |
|---|---|---|
| `player_wizard.png` | 96×128 | Player wizard sprite sheet (multiple frames) |
| `enemy_archmage.png` | 96×128 | Enemy archmage sprite sheet |
| `enemy_blue_apprentice.png` | 96×128 | Enemy blue apprentice |
| `enemy_eightfold_warden.png` | 96×128 | Enemy eightfold warden |
| `enemy_mirror_mage.png` | 96×128 | Enemy mirror mage |
| `enemy_thorn_adept.png` | 96×128 | Enemy thorn adept |
| `enemy_wizard.png` | 96×128 | Enemy wizard |
| `duel_background.png` | 320×480 | Full duel background |

These are **sprite sheets** containing multiple animation frames in a single file. Requires frame extraction for training dataset use.

### UI Icons

- 20 icon files in `assets/icons/`
- Sizes range from 16×16 to 32×32
- Used for status effects, locus points, magic types
- Simple, recognizable silhouettes at small sizes

### Dominant Palette Analysis

- **Standard RGBA** — no custom palette quantization in the source files
- Colors chosen from a limited range consistent with fantasy pixel art:
  - Earth tones: browns, tans for terrain, wood
  - Greens: grass, foliage
  - Grays/stone: for dungeon, stone props
  - Reds/oranges: for fire, blood, magical effects
  - Blues: for water, ice, magical effects
  - Purples/violets: for mystical/rare elements
- No indexed palette — each PNG carries its own RGBA data
- Limited color per asset (typically 20-50 distinct colors per 16×24 character)

### Outline Style (Detailed)

- **1-pixel minimum** outline around character/shape silhouettes
- Uses the darkest practical color from the asset's palette
- Hard edges — no anti-aliasing on outlines
- Consistent 1-pixel width, even if it means some interior pixels become outline
- Examples: woodcutter's axe handle, knight's armor plates, farmer's straw hat

### Shading Style (Detailed)

- **Cell shading with 2-3 distinct tones** per major region
- Light source assumed upper-left
- Core shadow in recesses (armpits, under robes, under equipment)
- Mid-tone on protruding areas (shoulders, arms, forehead)
- Highlight on extreme protrusions (tip of nose, top of head, weapon tips)
- No gradient shading — distinct color blocks
- Shading defines form without losing readability at small scale

### Perspective (Detailed)

- Predominantly **top-down** view
- Characters drawn as if viewed from directly above, slightly angled
- No true isometric projection (no 2:1 tile ratio)
- Vertical objects (trees, buildings) drawn with simple front/side simplification
- Ground tiles are orthogonal grid (16×16) with no perspective distortion

### Appropriate Detail Level at Gameplay Scale

- **16×24 characters**: Every pixel is meaningful. Details must be readable at this resolution:
  - Facial features suggested, not fully detailed
  - Weapon types identifiable (axe, staff, sword)
  - Clothing folds as 1-2 pixel lines
  - Silhouette is the primary readability mechanism
- **16×16 tiles**: Extremely constrained
  - Terrain type (grass, dirt, water, stone) identified by color/pattern
  - Simple props (rocks, trees) as 1-2 tile icons
  - No text or fine detail possible
- **32×32+ props**: Can show more detail but still limited
  - `door_dungeon.png` at 32×32 shows door texture
  - `tree_0.png` shows basic tree shape
  - Reading small text or fine detail is not possible

---

## Exclusion & Inclusion Guidelines for Training

### Include in WORLD SPRITE LoRA training:

- All 16×24 character frames (woodcutter, farmer, miner, etc.) — foundation of style
- 16×16 tile set (grass, dirt, stone, water, wood, wall) — terrain style
- 32×32+ props that exemplify DMB prop style (doors, chests, barrels)
- Creature world sprites (16×16) — monster style
- **Exclude**: Portraits (96×96), UI screenshots, text-heavy images, composite effects (192×192), large sprite sheets without frame extraction

### Exclude from WORLD SPRITE LoRA training:

- Portrait art (96×96) — different aspect ratio and level of detail
- UI screenshots — contain interface chrome, not game art
- Text-heavy images — dialog boxes, menus
- Composite effects — too complex, not sprite-like
- 320×480 background — too large, different purpose

### Duplicate/Near-Duplicate Detection

- **Exact duplicates**: Multiple files with identical pixel data (e.g., mirrored left/right if stored separately)
- **Near-duplicates**: Same character type with minor variations (different color hair, equipment)
  - These are **desirable** for training — the LoRA should learn the style, not memorize exact images
  - But extreme overrepresentation (e.g., 50 variants of the same woodcutter pose) should be balanced

---

## Style Conventions Summary

| Aspect | Convention |
|---|---|
| **Canvas size** | 16×24 (chars), 16×16 (tiles), variable (props/effects) |
| **Directional** | down/left/right/up, 2 frames per direction |
| **Mirroring** | left/right mirrored (Godot handles flip) |
| **Transparency** | RGBA, edges preserved cleanly |
| **Outline** | 1-pixel, hard edge, silhouette-defining |
| **Shading** | 2-3 cell-shade tones, upper-left light source |
| **Perspective** | Top-down, not isometric |
| **Color palette** | Limited fantasy range, no indexed palette |
| **Detail level** | Readable at 16×24, minimal at 16×16 |
| **Godot import** | Texture filter = nearest (0), no mipmaps |