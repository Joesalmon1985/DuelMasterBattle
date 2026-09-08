extends RefCounted

## Central visual constants — see docs/ART_BIBLE.md
## Use: const VT = preload("res://client/scripts/visual_theme.gd")

const ASSET_SCALE := 2
const REF_WIDTH := 720
const REF_HEIGHT := 1280

const PADDING_OUTER := 20
const PADDING_PANEL := 16
const SLOT_SEPARATION := 12

const TOUCH_CAST := 96
const TOUCH_CAST_RING := 132
const TOUCH_ESSENCE := 84
const TOUCH_TRAY := 92
const TOUCH_SECONDARY := 56
const TOUCH_UTILITY := 48

const FONT_TITLE := 40
const FONT_PRIMARY := 28
const FONT_SECONDARY := 22
const FONT_BUTTON := 24
const FONT_HISTORY := 20
const FONT_CAPTION := 16

const COLOR_BG_DEEP := Color("#1a1530")
const COLOR_BG_MID := Color("#2d2550")
const COLOR_PANEL := Color("#1e1a35")
const COLOR_PANEL_BORDER := Color("#6b5ce7")
const COLOR_ACCENT_GOLD := Color("#ffc947")
const COLOR_ACCENT_CYAN := Color("#4fc3f7")
const COLOR_TEXT_PRIMARY := Color("#f2f0ff")
const COLOR_TEXT_SECONDARY := Color("#b8b0d8")
const COLOR_DANGER := Color("#ff6b6b")

const COLOR_FRACTURE := Color("#66ff99")
const COLOR_ECHO := Color("#ffb84d")
const COLOR_FADE := Color("#7c7890")

const DUR_BUTTON_PRESS := 0.10
const DUR_ESSENCE_POP := 0.16
const DUR_CAST_WINDUP := 0.35
const DUR_PROJECTILE := 0.45
const DUR_IMPACT := 0.35
const DUR_FEEDBACK := 0.55
const DUR_VICTORY := 1.0
const DUR_PICKER_OPEN := 0.12
const DUR_FEEDBACK_ANTICIPATION := 0.20
const DUR_FEEDBACK_EMPHASIS := 0.40
const DUR_FEEDBACK_AFTERMATH := 0.40
const DUR_FEEDBACK_LOCK := 1.0

const DRAG_THRESHOLD_PX := 12
const LONG_PRESS_MS := 450
const SAFE_BOTTOM_INSET := 48

const HISTORY_PEEK_MAX := 3
const WARNING_SECONDS := 10.0

enum InteractionState {
	IDLE,
	LOCUS_SELECTED,
	ESSENCE_PICKER_OPEN,
	SOCKET_FILLED,
	CAST_READY,
	CASTING,
	FEEDBACK_LOCKED,
}


static func panel_style(radius: int = 16) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = COLOR_PANEL
	s.border_color = COLOR_PANEL_BORDER
	s.set_border_width_all(2)
	s.set_corner_radius_all(radius)
	s.shadow_color = Color(0, 0, 0, 0.45)
	s.shadow_size = 6
	s.shadow_offset = Vector2(3, 5)
	s.content_margin_left = PADDING_PANEL
	s.content_margin_right = PADDING_PANEL
	s.content_margin_top = PADDING_PANEL
	s.content_margin_bottom = PADDING_PANEL
	return s


static func flat_panel_style(bg: Color = Color("#221c3d"), radius: int = 14) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = bg
	s.set_corner_radius_all(radius)
	s.content_margin_left = 12
	s.content_margin_right = 12
	s.content_margin_top = 10
	s.content_margin_bottom = 10
	return s


static func secondary_button_style() -> StyleBoxFlat:
	var s := panel_style()
	s.bg_color = COLOR_BG_MID
	s.set_corner_radius_all(12)
	s.shadow_size = 0
	s.content_margin_left = 18
	s.content_margin_right = 18
	s.content_margin_top = 10
	s.content_margin_bottom = 10
	return s


static func gem_button_style(pressed: bool = false) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = Color("#3d3580") if not pressed else Color("#2a2460")
	s.border_color = COLOR_ACCENT_GOLD
	s.set_border_width_all(3)
	s.set_corner_radius_all(20)
	s.shadow_color = Color(0, 0, 0, 0.5)
	s.shadow_size = 8
	s.shadow_offset = Vector2(2, 4)
	s.content_margin_left = 24
	s.content_margin_right = 24
	s.content_margin_top = 12
	s.content_margin_bottom = 12
	return s


static func disabled_button_style() -> StyleBoxFlat:
	var s := gem_button_style()
	s.bg_color = Color("#262244")
	s.border_color = Color("#4a3f7a")
	s.shadow_size = 0
	return s


static func style_primary_button(b: Button) -> void:
	b.add_theme_stylebox_override("normal", gem_button_style(false))
	b.add_theme_stylebox_override("hover", gem_button_style(false))
	b.add_theme_stylebox_override("pressed", gem_button_style(true))
	b.add_theme_stylebox_override("disabled", disabled_button_style())
	b.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	b.add_theme_font_size_override("font_size", FONT_BUTTON)
	b.add_theme_color_override("font_color", COLOR_TEXT_PRIMARY)
	b.add_theme_color_override("font_disabled_color", COLOR_TEXT_SECONDARY.darkened(0.3))
	b.focus_mode = Control.FOCUS_NONE


static func style_secondary_button(b: Button) -> void:
	b.add_theme_stylebox_override("normal", secondary_button_style())
	b.add_theme_stylebox_override("hover", secondary_button_style())
	var p := secondary_button_style()
	p.bg_color = COLOR_BG_MID.darkened(0.3)
	b.add_theme_stylebox_override("pressed", p)
	var d := secondary_button_style()
	d.bg_color = Color("#221c3d")
	d.border_color = Color("#3a3160")
	b.add_theme_stylebox_override("disabled", d)
	b.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	b.add_theme_font_size_override("font_size", FONT_SECONDARY)
	b.add_theme_color_override("font_color", COLOR_TEXT_PRIMARY)
	b.add_theme_color_override("font_disabled_color", COLOR_TEXT_SECONDARY.darkened(0.4))
	b.focus_mode = Control.FOCUS_NONE


static func apply_label_title(lbl: Label) -> void:
	lbl.add_theme_font_size_override("font_size", FONT_TITLE)
	lbl.add_theme_color_override("font_color", COLOR_ACCENT_GOLD)


static func apply_label_primary(lbl: Label) -> void:
	lbl.add_theme_font_size_override("font_size", FONT_PRIMARY)
	lbl.add_theme_color_override("font_color", COLOR_TEXT_PRIMARY)


static func apply_label_secondary(lbl: Label) -> void:
	lbl.add_theme_font_size_override("font_size", FONT_SECONDARY)
	lbl.add_theme_color_override("font_color", COLOR_TEXT_SECONDARY)


static func apply_label_caption(lbl: Label) -> void:
	lbl.add_theme_font_size_override("font_size", FONT_CAPTION)
	lbl.add_theme_color_override("font_color", COLOR_TEXT_SECONDARY)
