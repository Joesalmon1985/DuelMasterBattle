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


## Press feel (docs/POLISH_WATCHING_FEEL.md): the button dips to 96% while held and springs back. Connected once; safe to call on every restyle.
static func press_feel(b: Button) -> void:
	if b.has_meta("press_feel"):
		return
	b.set_meta("press_feel", true)
	b.button_down.connect(func() -> void:
		b.pivot_offset = b.size * 0.5
		var tw := b.create_tween()
		tw.tween_property(b, "scale", Vector2(0.96, 0.96), 0.06).set_trans(Tween.TRANS_SINE).set_ease(Tween.EASE_OUT))
	b.button_up.connect(func() -> void:
		var tw := b.create_tween()
		tw.tween_property(b, "scale", Vector2.ONE, 0.16).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT))


## A card or panel arriving: it fades up and settles from 96% about its centre. The pivot is read from the size now; a panel sized later is only
## a hair off-centre at 96%, which the eye cannot see.
static func pop_in(c: Control, seconds: float = 0.22) -> void:
	c.pivot_offset = c.size * 0.5
	c.modulate = Color(1, 1, 1, 0)
	c.scale = Vector2(0.96, 0.96)
	var tw := c.create_tween()
	tw.set_parallel(true)
	tw.tween_property(c, "modulate:a", 1.0, seconds)
	tw.tween_property(c, "scale", Vector2.ONE, seconds * 1.4).set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)


## New words on a card that is already up: a short fade, not a second arrival.
static func fade_in(c: Control, seconds: float = 0.14) -> void:
	c.modulate = Color(1, 1, 1, 0.25)
	var tw := c.create_tween()
	tw.tween_property(c, "modulate:a", 1.0, seconds)


## A refused move: the panel shivers sideways and comes back to where it was.
static func shake(c: Control, px: float = 8.0) -> void:
	var origin := c.position
	var tw := c.create_tween()
	for i in 4:
		tw.tween_property(c, "position:x", origin.x + (px if i % 2 == 0 else -px) * (1.0 - float(i) * 0.2), 0.045)
	tw.tween_property(c, "position:x", origin.x, 0.05)


static func style_primary_button(b: Button) -> void:
	press_feel(b)
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
	press_feel(b)
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


# ---------------------------------------------------------------------------------------------------------------------------------
# Narrative UI: conversations, the arrival text, the journal, inspect panels, the campaign HUD and the pause menu share ONE look.
# Arcane fantasy with classic strategy-game chrome: deep indigo cards, a restrained muted-gold edge, parchment text, gold only for names and the
# one primary action. Widgets are built by DmbNarrativeCard (client/ui/narrative_card.gd) and sized by DmbResponsiveModal.metrics(): every size
# there is in PHYSICAL pixels, so these functions take `k`, the virtual units per physical pixel (1 / the stretch scale).
# ---------------------------------------------------------------------------------------------------------------------------------

const COLOR_CARD := Color("#161230")
const COLOR_CARD_INNER := Color("#201a3e")
const COLOR_CARD_EDGE := Color("#9a7b3f")        # muted gold
const COLOR_PARCHMENT := Color("#efe6cf")        # body text
const COLOR_PARCHMENT_DIM := Color("#c8bea4")    # secondary text
const COLOR_GOLD := Color("#e2bb5e")             # names, titles, the primary action
const COLOR_CHOICE := Color("#2a2350")
const COLOR_CHOICE_HOVER := Color("#3a3070")
const COLOR_CHOICE_EDGE := Color("#5b4fb8")
const COLOR_HUD_BG := Color(0.07, 0.06, 0.16, 0.82)
const NARR_TOUCH_MIN := 48.0                     # physical px: the smallest tappable control


static func narr_card_style(k: float, radius: float = 10.0) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = COLOR_CARD
	s.border_color = COLOR_CARD_EDGE
	s.set_border_width_all(maxi(1, int(round(1.5 * k))))
	s.set_corner_radius_all(int(round(radius * k)))
	s.shadow_color = Color(0, 0, 0, 0.5)
	s.shadow_size = int(round(8 * k))
	s.shadow_offset = Vector2(0, 3 * k)
	var m := int(round(14 * k))
	s.content_margin_left = m
	s.content_margin_right = m
	s.content_margin_top = int(round(12 * k))
	s.content_margin_bottom = int(round(12 * k))
	return s


static func narr_hud_style(k: float) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = COLOR_HUD_BG
	s.border_color = COLOR_CARD_EDGE.darkened(0.15)
	s.set_border_width_all(maxi(1, int(round(1.0 * k))))
	s.set_corner_radius_all(int(round(8 * k)))
	s.content_margin_left = int(round(10 * k))
	s.content_margin_right = int(round(10 * k))
	s.content_margin_top = int(round(6 * k))
	s.content_margin_bottom = int(round(7 * k))
	return s


static func narr_button_style(k: float, kind: String, state: String) -> StyleBoxFlat:
	## kind: "choice" (a reply the wizard can give) or "primary" (Continue, Begin, Talk: the one gold action); state: normal, hover, pressed, disabled.
	var s := StyleBoxFlat.new()
	var primary := kind == "primary"
	s.bg_color = (Color("#3b2f12") if primary else COLOR_CHOICE)
	s.border_color = (COLOR_GOLD if primary else COLOR_CHOICE_EDGE)
	match state:
		"hover":
			s.bg_color = (Color("#4d3d17") if primary else COLOR_CHOICE_HOVER)
		"pressed":
			s.bg_color = s.bg_color.darkened(0.25)
		"disabled":
			s.bg_color = Color("#1d1936")
			s.border_color = Color("#3a3160")
	s.set_border_width_all(maxi(1, int(round((2.0 if primary else 1.5) * k))))
	s.set_corner_radius_all(int(round(8 * k)))
	s.content_margin_left = int(round(14 * k))
	s.content_margin_right = int(round(14 * k))
	s.content_margin_top = int(round(8 * k))
	s.content_margin_bottom = int(round(8 * k))
	return s


static func style_narr_button(b: Button, k: float, kind: String, font_px: float) -> void:
	press_feel(b)
	for st in ["normal", "hover", "pressed", "disabled"]:
		b.add_theme_stylebox_override(st, narr_button_style(k, kind, st))
	b.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	b.add_theme_font_size_override("font_size", int(round(font_px * k)))
	b.add_theme_color_override("font_color", COLOR_GOLD if kind == "primary" else COLOR_PARCHMENT)
	b.add_theme_color_override("font_hover_color", COLOR_PARCHMENT)
	b.add_theme_color_override("font_pressed_color", COLOR_PARCHMENT)
	b.add_theme_color_override("font_disabled_color", COLOR_PARCHMENT_DIM.darkened(0.4))
	b.focus_mode = Control.FOCUS_NONE
	b.alignment = HORIZONTAL_ALIGNMENT_LEFT if kind == "choice" else HORIZONTAL_ALIGNMENT_CENTER
	b.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	b.clip_text = false
