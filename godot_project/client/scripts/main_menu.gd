extends Control

## Main menu: pick a rival difficulty and start the duel. Everything else
## (rules, settings) lives behind small buttons so the first tap is obvious.

const _VT = preload("res://client/scripts/visual_theme.gd")
const _Encounters = preload("res://sim/encounters.gd")
const _DifficultyProfiles = preload("res://sim/difficulty_profiles.gd")
const _SaveData = preload("res://client/scripts/save_data.gd")
const _SpellSlot = preload("res://client/components/spell_slot.gd")
const _Art = preload("res://client/scripts/art.gd")

const HOW_TO_PLAY := [
	"You and your opponent each hide a Ward of spells. Spells may repeat.",
	"Guess each other's Ward. After every cast you learn how many spells were right — never which ones.",
	"●  green — right spell in the right place\n○  amber ring — right spell in the wrong place\n·  grey — spell not in the Ward at all",
	"You can cast 5 seconds after your window opens, and must cast within 60. Ten casts each.",
	"Break their Ward first to win.",
	"Adventure: walk with the pad, tap ✦ to talk, take, douse fires and face creatures. Your weave (how many spells you cast at once) grows as you learn.",
]

var _difficulties: Array = []
var _selected_difficulty: String = "medium"
var _diff_buttons: Array = []
var _diff_desc_lbl: Label
var _panel_vbox: VBoxContainer
var _overlay: ColorRect
var _overlay_vbox: VBoxContainer
var _start_btn: Button
var _resume_btn: Button
var _quick_btn: Button
var _confirm_pending: bool = false


func _ready() -> void:
	_difficulties = _DifficultyProfiles.all_profiles()
	_selected_difficulty = _SaveData.get_last_difficulty()
	_build()


func _build() -> void:
	var bg := ColorRect.new()
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.color = _VT.COLOR_BG_DEEP
	add_child(bg)
	# Pixel-art dark fantasy backdrop (imported from the spare sprites pack).
	var pano := TextureRect.new()
	pano.set_anchors_preset(Control.PRESET_FULL_RECT)
	pano.texture = load("res://assets/pixel/backdrops/title_panorama.png")
	pano.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	pano.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	pano.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	pano.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(pano)
	var shade := ColorRect.new()
	shade.set_anchors_preset(Control.PRESET_FULL_RECT)
	shade.color = Color(0.03, 0.02, 0.07, 0.45)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(shade)
	var glow := _Vignette.new()
	glow.set_anchors_preset(Control.PRESET_FULL_RECT)
	glow.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(glow)

	var margin := MarginContainer.new()
	margin.set_anchors_preset(Control.PRESET_FULL_RECT)
	margin.add_theme_constant_override("margin_left", 28)
	margin.add_theme_constant_override("margin_right", 28)
	margin.add_theme_constant_override("margin_top", 60)
	margin.add_theme_constant_override("margin_bottom", 40)
	add_child(margin)
	_panel_vbox = VBoxContainer.new()
	_panel_vbox.add_theme_constant_override("separation", 18)
	margin.add_child(_panel_vbox)

	var title := Label.new()
	title.text = "Duel Master\nBattle"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", 60)
	title.add_theme_color_override("font_color", _VT.COLOR_ACCENT_GOLD)
	title.add_theme_color_override("font_outline_color", Color(0.05, 0.03, 0.08))
	title.add_theme_constant_override("outline_size", 10)
	_panel_vbox.add_child(title)
	var sub := Label.new()
	sub.text = "A woodcutter. A dead man's staff. Four knots to learn."
	sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	sub.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_VT.apply_label_secondary(sub)
	sub.add_theme_color_override("font_outline_color", Color(0.05, 0.03, 0.08))
	sub.add_theme_constant_override("outline_size", 6)
	_panel_vbox.add_child(sub)

	var spacer := Control.new()
	spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_panel_vbox.add_child(spacer)

	# John and the Red wizard face off across the title.
	var duel_row := HBoxContainer.new()
	duel_row.alignment = BoxContainer.ALIGNMENT_CENTER
	duel_row.add_theme_constant_override("separation", 60)
	_panel_vbox.add_child(duel_row)
	for path in ["res://assets/pixel/portraits/john.png", "res://assets/pixel/portraits/arcanist.png"]:
		var tr := TextureRect.new()
		tr.custom_minimum_size = Vector2(160, 160)
		tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		tr.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		tr.texture = load(path)
		if path.ends_with("arcanist.png"):
			tr.flip_h = true
		duel_row.add_child(tr)
		if path.ends_with("john.png"):
			var vs := Label.new()
			vs.text = "vs"
			vs.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
			_VT.apply_label_title(vs)
			duel_row.add_child(vs)

	var spacer2 := Control.new()
	spacer2.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_panel_vbox.add_child(spacer2)

	var menu_panel := PanelContainer.new()
	menu_panel.add_theme_stylebox_override("panel", _VT.flat_panel_style(Color(0.08, 0.06, 0.14, 0.88), 16))
	_panel_vbox.add_child(menu_panel)
	var mv := VBoxContainer.new()
	mv.add_theme_constant_override("separation", 12)
	menu_panel.add_child(mv)

	_start_btn = Button.new()
	_start_btn.text = "NEW GAME"
	_start_btn.custom_minimum_size = Vector2(0, 76)
	_VT.style_primary_button(_start_btn)
	_start_btn.add_theme_font_size_override("font_size", 30)
	_start_btn.pressed.connect(_on_new_game)
	mv.add_child(_start_btn)

	_resume_btn = Button.new()
	_resume_btn.custom_minimum_size = Vector2(0, 76)
	_VT.style_primary_button(_resume_btn)
	_resume_btn.add_theme_font_size_override("font_size", 30)
	_resume_btn.pressed.connect(_on_resume)
	mv.add_child(_resume_btn)
	_refresh_resume()

	_quick_btn = Button.new()
	_quick_btn.text = "Quick Duel  (4-slot wizard match)"
	_quick_btn.custom_minimum_size = Vector2(0, 60)
	_VT.style_secondary_button(_quick_btn)
	_quick_btn.pressed.connect(_show_quick_duel)
	mv.add_child(_quick_btn)

	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 12)
	mv.add_child(row)
	var how := Button.new()
	how.text = "How to play"
	how.custom_minimum_size = Vector2(0, 56)
	how.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_VT.style_secondary_button(how)
	how.pressed.connect(_show_how_to_play)
	row.add_child(how)
	var settings := Button.new()
	settings.text = "Settings"
	settings.custom_minimum_size = Vector2(0, 56)
	settings.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_VT.style_secondary_button(settings)
	settings.pressed.connect(_show_settings)
	row.add_child(settings)

	_overlay = ColorRect.new()
	_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	_overlay.color = Color(0.05, 0.03, 0.1, 0.8)
	_overlay.visible = false
	add_child(_overlay)
	var center := CenterContainer.new()
	center.set_anchors_preset(Control.PRESET_FULL_RECT)
	_overlay.add_child(center)
	var panel := PanelContainer.new()
	panel.add_theme_stylebox_override("panel", _VT.panel_style(20))
	panel.custom_minimum_size = Vector2(560, 0)
	center.add_child(panel)
	_overlay_vbox = VBoxContainer.new()
	_overlay_vbox.add_theme_constant_override("separation", 14)
	panel.add_child(_overlay_vbox)


func _adventure() -> Node:
	return get_node("/root/Adventure")


func _refresh_resume() -> void:
	var has: bool = _adventure().has_save()
	_resume_btn.disabled = not has
	if has:
		_resume_btn.text = "RESUME GAME"
		_resume_btn.tooltip_text = ""
	else:
		_resume_btn.text = "RESUME — no saved game"
	var summary: String = _adventure().save_summary()
	if summary != "":
		_resume_btn.text = "RESUME GAME\n" + summary
		_resume_btn.add_theme_font_size_override("font_size", 24)


func _on_new_game() -> void:
	if _adventure().has_save():
		_confirm_new_game()
		return
	_begin_new_game()


func _confirm_new_game() -> void:
	_clear_overlay()
	var t := Label.new()
	t.text = "Start over?"
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_title(t)
	_overlay_vbox.add_child(t)
	var l := Label.new()
	l.text = "You already have a saved game:\n%s\n\nStarting a New Game will erase it. There is only one save." % _adventure().save_summary()
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_secondary(l)
	_overlay_vbox.add_child(l)
	var yes := Button.new()
	yes.text = "Erase and start new"
	yes.custom_minimum_size = Vector2(0, 64)
	_VT.style_secondary_button(yes)
	yes.add_theme_color_override("font_color", _VT.COLOR_DANGER)
	yes.pressed.connect(func():
		_overlay.visible = false
		_begin_new_game()
	)
	_overlay_vbox.add_child(yes)
	_overlay_close_button("Keep my game")
	_overlay.visible = true


func _begin_new_game() -> void:
	_adventure().new_game()
	_adventure().save()
	var sfx := get_node_or_null("/root/Sfx")
	if sfx:
		sfx.cast()
	get_tree().change_scene_to_file("res://client/scenes/overworld.tscn")


func _on_resume() -> void:
	if not _adventure().load_game():
		_refresh_resume()
		return
	var sfx := get_node_or_null("/root/Sfx")
	if sfx:
		sfx.tap()
	get_tree().change_scene_to_file("res://client/scenes/overworld.tscn")


func _show_quick_duel() -> void:
	_clear_overlay()
	_diff_buttons.clear()
	var t := Label.new()
	t.text = "Quick Duel"
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_title(t)
	_overlay_vbox.add_child(t)
	var l := Label.new()
	l.text = "A straight four-slot Ward duel against a rival wizard. Six spells, ten casts each."
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_secondary(l)
	_overlay_vbox.add_child(l)
	var diff_row := HBoxContainer.new()
	diff_row.add_theme_constant_override("separation", 10)
	_overlay_vbox.add_child(diff_row)
	for d in _difficulties:
		var b := Button.new()
		b.text = d.display_name
		b.custom_minimum_size = Vector2(0, 64)
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		_VT.style_secondary_button(b)
		var id: String = d.id
		b.pressed.connect(func(): _select_difficulty(id))
		diff_row.add_child(b)
		_diff_buttons.append(b)
	_diff_desc_lbl = Label.new()
	_diff_desc_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_diff_desc_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_diff_desc_lbl.custom_minimum_size = Vector2(0, 60)
	_VT.apply_label_secondary(_diff_desc_lbl)
	_overlay_vbox.add_child(_diff_desc_lbl)
	_select_difficulty(_selected_difficulty)
	var go := Button.new()
	go.text = "Start Duel"
	go.custom_minimum_size = Vector2(0, 72)
	_VT.style_primary_button(go)
	go.pressed.connect(_on_start_duel)
	_overlay_vbox.add_child(go)
	_overlay_close_button("Back")
	_overlay.visible = true


func _select_difficulty(id: String) -> void:
	var found := false
	for d in _difficulties:
		if d.id == id:
			found = true
	if not found:
		id = "medium"
	_selected_difficulty = id
	if _diff_buttons.is_empty():
		return
	for i in range(_difficulties.size()):
		var d = _difficulties[i]
		var b: Button = _diff_buttons[i]
		var s := _VT.secondary_button_style()
		if d.id == id:
			s.bg_color = Color("#3d3580")
			s.border_color = _VT.COLOR_ACCENT_GOLD
			s.set_border_width_all(3)
			_diff_desc_lbl.text = d.description
		else:
			s.bg_color = Color("#1b1633")
			s.border_color = Color("#3a3160")
		b.add_theme_stylebox_override("normal", s)
		b.add_theme_stylebox_override("hover", s)


func _session() -> Node:
	return get_node("/root/EncounterSession")


func _on_start_duel() -> void:
	_adventure().clear_pending_battle()
	_session().set_encounter(_Encounters.DEFAULT_ENCOUNTER_ID)
	_session().set_difficulty(_selected_difficulty)
	_SaveData.set_last_difficulty(_selected_difficulty)
	var sfx := get_node_or_null("/root/Sfx")
	if sfx:
		sfx.cast()
	get_tree().change_scene_to_file("res://client/scenes/game_board.tscn")


func _clear_overlay() -> void:
	for c in _overlay_vbox.get_children():
		c.queue_free()


func _overlay_close_button(text_value: String = "Back") -> void:
	var b := Button.new()
	b.text = text_value
	b.custom_minimum_size = Vector2(0, 64)
	_VT.style_primary_button(b)
	b.pressed.connect(func(): _overlay.visible = false)
	_overlay_vbox.add_child(b)


func _show_how_to_play() -> void:
	_clear_overlay()
	var t := Label.new()
	t.text = "How to play"
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_title(t)
	_overlay_vbox.add_child(t)
	for line in HOW_TO_PLAY:
		var l := Label.new()
		l.text = line
		l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		_VT.apply_label_secondary(l)
		_overlay_vbox.add_child(l)
	_overlay_close_button("Got it")
	_overlay.visible = true


func _show_settings() -> void:
	_clear_overlay()
	var t := Label.new()
	t.text = "Settings"
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_title(t)
	_overlay_vbox.add_child(t)
	var rows := [
		["sound", "Sound effects", true],
		["haptics", "Vibration", true],
		["reduce_motion", "Reduce motion", false],
	]
	for r in rows:
		var key: String = r[0]
		var h := HBoxContainer.new()
		h.add_theme_constant_override("separation", 12)
		var lbl := Label.new()
		lbl.text = r[1]
		lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
		_VT.apply_label_secondary(lbl)
		h.add_child(lbl)
		var check := CheckButton.new()
		check.focus_mode = Control.FOCUS_NONE
		check.custom_minimum_size = Vector2(0, 48)
		check.button_pressed = bool(_SaveData.get_setting(key, r[2]))
		check.toggled.connect(func(on): _SaveData.set_setting(key, on))
		h.add_child(check)
		_overlay_vbox.add_child(h)
	var reset := Button.new()
	reset.text = "Show tutorial again next duel"
	reset.custom_minimum_size = Vector2(0, 56)
	_VT.style_secondary_button(reset)
	reset.pressed.connect(func():
		_SaveData.set_setting("seen_how_to_play", false)
		reset.text = "Tutorial will show next duel ✓"
	)
	_overlay_vbox.add_child(reset)
	_overlay_close_button("Back")
	_overlay.visible = true


class _Vignette:
	extends Control
	func _draw() -> void:
		var c := size * Vector2(0.5, 0.3)
		var r := size.length() * 0.5
		for i in range(12):
			var t := float(i) / 12.0
			draw_circle(c, r * (0.2 + 0.8 * t), Color(0.3, 0.22, 0.55, 0.07 * (1.0 - t)))


# --- UI smoke API ------------------------------------------------------------

func ui_action_start_encounter(_encounter_id: String = "") -> void:
	_on_start_duel()


func ui_new_game() -> void:
	_on_new_game()


func ui_resume() -> void:
	_on_resume()


func ui_confirm_overwrite() -> void:
	_overlay.visible = false
	_begin_new_game()


func ui_resume_enabled() -> bool:
	return not _resume_btn.disabled


func ui_action_select_difficulty(difficulty_id: String) -> void:
	_select_difficulty(difficulty_id)


func ui_get_selected_difficulty() -> String:
	return _selected_difficulty


func ui_has_help_panel() -> bool:
	return _overlay != null


func ui_is_overlay_visible() -> bool:
	return _overlay.visible


func ui_show_help() -> void:
	_show_how_to_play()
