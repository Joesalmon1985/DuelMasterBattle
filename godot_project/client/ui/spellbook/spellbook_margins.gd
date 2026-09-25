extends RefCounted
class_name SpellbookMargins

## Content insets as fractions of the displayed TextureRect size.
## Tuned against the processed PNGs (white exterior removed; parchment kept).

const TEX_BOOK := "res://assets/sprites/Spellbook/Spellbook.png"
const TEX_PAGE := "res://assets/sprites/Spellbook/spellpage.png"
const TEX_CARD := "res://assets/sprites/Spellbook/spellcard.png"

## Open book (landscape spread) — left/right page rects inside the texture.
const BOOK_LEFT := Rect2(0.10, 0.14, 0.36, 0.70)
const BOOK_RIGHT := Rect2(0.52, 0.14, 0.36, 0.70)
const BOOK_SPINE_GAP := 0.04

## Single page (portrait information / dialogue).
## Wider parchment column — 38% was unreadable at 450×800 output.
const PAGE_CONTENT := Rect2(0.12, 0.14, 0.76, 0.70)

## Compact card.
const CARD_CONTENT := Rect2(0.36, 0.16, 0.34, 0.64)

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

const TOUCH_MIN := 48.0
const TOUCH_GAP := 8.0
const BODY_FONT := 20
const HEADING_FONT := 24
const CAPTION_FONT := 15
const RESULT_FONT := 17

## Prefer single-page when either logical dimension is too narrow for a readable spread.
const SPREAD_MIN_WIDTH := 1000.0
const SPREAD_MIN_PAGE_WIDTH := 320.0

## Bounded open-book panel — artwork fits inside these caps; world stays visible around it.
const OPEN_MAX_WIDTH_LANDSCAPE := 980.0
const OPEN_MAX_HEIGHT_LANDSCAPE := 620.0
const OPEN_VIEWPORT_FRAC_W_LANDSCAPE := 0.82
const OPEN_VIEWPORT_FRAC_H_LANDSCAPE := 0.82
const OPEN_MAX_WIDTH_PORTRAIT := 560.0
const OPEN_MAX_HEIGHT_PORTRAIT := 760.0
const OPEN_VIEWPORT_FRAC_W_PORTRAIT := 0.96
const OPEN_VIEWPORT_FRAC_H_PORTRAIT := 0.90

## Compact launcher stays clear of touch pad / action chrome.
const COMPACT_BOTTOM_CLEARANCE := 200.0
const COMPACT_SIDE_PAD := 12.0
const SAFE_TOP := 8.0

## Open-book chrome (persistent Close).
const PANEL_CLOSE_SIZE := Vector2(132, 48)


static func reduced_motion() -> bool:
	return bool(ProjectSettings.get_setting("dmb/spellbook/reduced_motion", false)) \
		or OS.get_environment("DMB_REDUCED_MOTION") == "1"


static func text_scale() -> float:
	var s := float(ProjectSettings.get_setting("dmb/spellbook/text_scale", 1.0))
	return clampf(s, 0.85, 1.6)


static func scaled_font(base: int) -> int:
	return int(round(float(base) * text_scale()))
