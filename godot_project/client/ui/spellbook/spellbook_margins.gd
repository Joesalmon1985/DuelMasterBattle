extends RefCounted
class_name SpellbookMargins

## Authoritative parchment-safe geometry for Spellbook artwork.
## Fractions are of the *displayed* TextureRect size (aspect-fit artwork).
## Measured against Spellbook.png / spellpage.png (1248×832) with generous
## padding clear of leather, purple lining, gold corners, spine gutter,
## page-stack edges, and decorative filigree. Do not scatter offsets elsewhere.

const TEX_BOOK := "res://assets/sprites/Spellbook/Spellbook.png"
const TEX_PAGE := "res://assets/sprites/Spellbook/spellpage.png"
const TEX_CARD := "res://assets/sprites/Spellbook/spellcard.png"

## Open-book two-page spread — blank parchment only (not texture halves).
## Verified 2026-09-25 against Spellbook.png pixel samples (corners ≥~200 luma).
const BOOK_LEFT := Rect2(0.185, 0.210, 0.255, 0.490)
const BOOK_RIGHT := Rect2(0.565, 0.210, 0.200, 0.490)
const BOOK_SPINE_GAP := 0.04

## Single-page layout — central blank parchment inside filigree borders.
## Verified 2026-09-25 against spellpage.png (no red/blue filigree samples).
const PAGE_CONTENT := Rect2(0.420, 0.300, 0.220, 0.340)

## Compact closed card (launcher) — approximate writable patch on spellcard.png.
const CARD_CONTENT := Rect2(0.36, 0.16, 0.34, 0.64)

## Extra inset inside each parchment-safe slot before text/controls begin (pixels
## at 1× art; scaled with the fitted artwork).
const INNER_PAD_FRAC := 0.022
const INNER_PAD_MIN_PX := 10.0
const INNER_PAD_MAX_PX := 16.0

const TEXT_INK := Color("#2a1c12")
const TEXT_MUTED := Color("#5a4636")
const TEXT_ACCENT := Color("#4a2040")
const TEXT_DANGER := Color("#7a1818")
const TEXT_OK := Color("#1e4a28")
const TEXT_PENDING := Color("#5a4010")
const PANEL_FILL := Color(0.96, 0.90, 0.78, 0.92)
const PANEL_BORDER := Color(0.35, 0.22, 0.12, 0.85)

const DUR_OPEN := 0.18
const DUR_CLOSE := 0.16
const DUR_PAGE := 0.14
const DUR_PRESS := 0.10
const DUR_HIGHLIGHT := 0.20

## Readable touch targets — prefer scrolling over shrinking these.
const TOUCH_MIN := 48.0
const TOUCH_GAP := 8.0
const BODY_FONT := 22
const HEADING_FONT := 26
const CAPTION_FONT := 16
const RESULT_FONT := 18

## Spread only when *safe parchment* (not overall texture) stays readable.
## Right page is intentionally narrower (spine + outer edge); ~180px still holds
## BODY_FONT 22 with scrolling. Below this, switch to single-page art.
const MIN_SAFE_PAGE_WIDTH_PX := 175.0
const MIN_SAFE_PAGE_HEIGHT_PX := 260.0

## Bounded open-book panel — artwork aspect-fit inside these caps.
const OPEN_MAX_WIDTH_LANDSCAPE := 1100.0
const OPEN_MAX_HEIGHT_LANDSCAPE := 700.0
const OPEN_VIEWPORT_FRAC_W_LANDSCAPE := 0.90
const OPEN_VIEWPORT_FRAC_H_LANDSCAPE := 0.90
const OPEN_MAX_WIDTH_PORTRAIT := 560.0
const OPEN_MAX_HEIGHT_PORTRAIT := 760.0
const OPEN_VIEWPORT_FRAC_W_PORTRAIT := 0.96
const OPEN_VIEWPORT_FRAC_H_PORTRAIT := 0.90

## Compact launcher stays clear of touch pad / action chrome.
const COMPACT_BOTTOM_CLEARANCE := 200.0
const COMPACT_SIDE_PAD := 12.0
const SAFE_TOP := 8.0

## In-parchment close control (not floating outside the book art).
const CLOSE_BTN_SIZE := Vector2(96, 44)


static func reduced_motion() -> bool:
	return bool(ProjectSettings.get_setting("dmb/spellbook/reduced_motion", false)) \
		or OS.get_environment("DMB_REDUCED_MOTION") == "1"


static func layout_debug_enabled() -> bool:
	return OS.get_environment("DMB_SPELLBOOK_LAYOUT_DEBUG") == "1" \
		or bool(ProjectSettings.get_setting("dmb/spellbook/layout_debug", false))


static func text_scale() -> float:
	var s := float(ProjectSettings.get_setting("dmb/spellbook/text_scale", 1.0))
	return clampf(s, 0.85, 1.6)


static func scaled_font(base: int) -> int:
	return int(round(float(base) * text_scale()))


static func inner_pad_px(drawn_min_side: float) -> float:
	return clampf(drawn_min_side * INNER_PAD_FRAC, INNER_PAD_MIN_PX, INNER_PAD_MAX_PX)


## Map a fractional parchment rect onto the aspect-fit drawn texture inside panel.
static func slot_rect_in_panel(frac: Rect2, panel: Vector2, tex_size: Vector2) -> Rect2:
	var scale := minf(panel.x / tex_size.x, panel.y / tex_size.y)
	var drawn := tex_size * scale
	var origin := (panel - drawn) * 0.5
	return Rect2(
		origin + Vector2(frac.position.x * drawn.x, frac.position.y * drawn.y),
		Vector2(frac.size.x * drawn.x, frac.size.y * drawn.y)
	)


static func safe_page_pixel_size(panel: Vector2, tex_size: Vector2, frac: Rect2) -> Vector2:
	return slot_rect_in_panel(frac, panel, tex_size).size
