extends Control

## The main menu: Wizard World, and nothing else. One game, two ways to play it.
##
##   Play Single Player   a private Wizard World of your own (the campaign: the apprenticeship, the stranger, the settlement that goes on living),
##                        with an AI fellow apprentice for company; Continue if a campaign is saved on this device
##   Host Multiplayer     host the same world for a friend on the same Wi-Fi
##   Join Multiplayer     join a friend's world
##   Settings
##
## The older adventure (Ashwell, Trial Day), Quick Duel and the G01 testing entry are developer tools: they live in dev_menu.tscn and are reachable
## only through dev_mode.gd's switches. This menu never reads the old adventure's save, so old save data cannot send a player anywhere.

const _VT = preload("res://client/scripts/visual_theme.gd")
const _SaveData = preload("res://client/scripts/save_data.gd")
const _DevMode = preload("res://client/scripts/dev_mode.gd")
const _Art = preload("res://client/scripts/art.gd")

var _panel_vbox: VBoxContainer
var _overlay: ColorRect
var _overlay_vbox: VBoxContainer
var single_btn: Button
var host_btn: Button
var join_btn: Button
var settings_btn: Button
var dev_btn: Button = null


func _ready() -> void:
	_build()


func _build() -> void:
	var bg := ColorRect.new()
	bg.set_anchors_preset(Control.PRESET_FULL_RECT)
	bg.color = _VT.COLOR_BG_DEEP
	add_child(bg)
	var pano := TextureRect.new()
	pano.set_anchors_preset(Control.PRESET_FULL_RECT)
	pano.texture = _Art.load_texture("pixel/backdrops/title_panorama.png")
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
	sub.text = "Wizard World"
	sub.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	sub.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_VT.apply_label_secondary(sub)
	sub.add_theme_color_override("font_outline_color", Color(0.05, 0.03, 0.08))
	sub.add_theme_constant_override("outline_size", 6)
	_panel_vbox.add_child(sub)

	var spacer := Control.new()
	spacer.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_panel_vbox.add_child(spacer)

	var duel_row := HBoxContainer.new()
	duel_row.alignment = BoxContainer.ALIGNMENT_CENTER
	duel_row.add_theme_constant_override("separation", 60)
	_panel_vbox.add_child(duel_row)
	for path in ["pixel/portraits/john.png", "pixel/portraits/arcanist.png"]:
		var tr := TextureRect.new()
		tr.custom_minimum_size = Vector2(160, 160)
		tr.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		tr.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		tr.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		tr.texture = _Art.load_texture(path)
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
	mv.add_theme_constant_override("separation", 14)
	menu_panel.add_child(mv)

	single_btn = _menu_button(mv, "SingleButton", "Play Single Player", true, 30, 84)
	single_btn.pressed.connect(_on_single_player)
	host_btn = _menu_button(mv, "HostButton", "Host Multiplayer", true, 30, 84)
	host_btn.pressed.connect(func(): _open_lan("host"))
	join_btn = _menu_button(mv, "JoinButton", "Join Multiplayer", true, 30, 84)
	join_btn.pressed.connect(func(): _open_lan("join"))
	settings_btn = _menu_button(mv, "SettingsButton", "Settings", false, 26, 68)
	settings_btn.pressed.connect(_show_settings)
	if _DevMode.enabled():
		dev_btn = _menu_button(mv, "DevButton", "Developer tools", false, 20, 52)
		dev_btn.pressed.connect(func(): get_tree().change_scene_to_file("res://client/scenes/dev_menu.tscn"))

	var ver := Label.new()
	ver.text = "v%s" % LanSession.GAME_VERSION
	ver.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_secondary(ver)
	_panel_vbox.add_child(ver)

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


func _menu_button(parent: Control, node_name: String, text_value: String, primary: bool, font_size: int, height: int) -> Button:
	var b := Button.new()
	b.name = node_name
	b.text = text_value
	b.custom_minimum_size = Vector2(0, height)
	if primary:
		_VT.style_primary_button(b)
	else:
		_VT.style_secondary_button(b)
	b.add_theme_font_size_override("font_size", font_size)
	parent.add_child(b)
	return b


# ---------------------------------------------------------------- the four entries

## Wizard World alone. A saved campaign on this device is offered first; everything else starts a new one. Either way it is the same world the
## multiplayer game hosts, running in a private session on this device (the phone's Python host, or a local Python process on a PC).
func _on_single_player() -> void:
	if LanSession.has_wizard_save():
		_show_continue_choice()
		return
	_begin_single(false)


func _begin_single(continue_game: bool) -> void:
	LanSession.reset()
	var sfx := get_node_or_null("/root/Sfx")
	if sfx:
		sfx.cast()
	if _DevMode.classic_sim():
		get_tree().change_scene_to_file("res://client/scenes/hybrid_world.tscn")  # the developer launchers' own server on 127.0.0.1
		return
	LanSession.mode = "host"
	LanSession.private_session = true
	LanSession.continue_game = continue_game
	get_tree().change_scene_to_file("res://client/scenes/lan_menu.tscn")


## Local Wi-Fi play (docs/MOBILE_LAN_MULTIPLAYER.md): the host runs the authoritative world on its own device; a friend joins it.
func _open_lan(mode: String) -> void:
	LanSession.reset()
	LanSession.mode = mode
	get_tree().change_scene_to_file("res://client/scenes/lan_menu.tscn")


func _show_continue_choice() -> void:
	_clear_overlay()
	var t := Label.new()
	t.text = "Wizard World"
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_title(t)
	_overlay_vbox.add_child(t)
	var l := Label.new()
	l.text = "Your campaign is saved on this device."
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_secondary(l)
	_overlay_vbox.add_child(l)
	var cont := Button.new()
	cont.name = "ContinueButton"
	cont.text = "Continue campaign"
	cont.custom_minimum_size = Vector2(0, 76)
	_VT.style_primary_button(cont)
	cont.pressed.connect(func():
		_overlay.visible = false
		_begin_single(true))
	_overlay_vbox.add_child(cont)
	var fresh := Button.new()
	fresh.name = "NewCampaignButton"
	fresh.text = "Start a new campaign"
	fresh.custom_minimum_size = Vector2(0, 64)
	_VT.style_secondary_button(fresh)
	fresh.pressed.connect(_confirm_new_campaign)
	_overlay_vbox.add_child(fresh)
	_overlay_close_button("Back")
	_overlay.visible = true


func _confirm_new_campaign() -> void:
	_clear_overlay()
	var t := Label.new()
	t.text = "Start over?"
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_title(t)
	_overlay_vbox.add_child(t)
	var l := Label.new()
	l.text = "A new campaign begins a new Wizard World. Your saved campaign stays until the new one saves over it."
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_secondary(l)
	_overlay_vbox.add_child(l)
	var yes := Button.new()
	yes.name = "ConfirmNewButton"
	yes.text = "Start a new campaign"
	yes.custom_minimum_size = Vector2(0, 64)
	_VT.style_secondary_button(yes)
	yes.pressed.connect(func():
		_overlay.visible = false
		_begin_single(false))
	_overlay_vbox.add_child(yes)
	_overlay_close_button("Keep my campaign")
	_overlay.visible = true


# ---------------------------------------------------------------- settings

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
	var about := Label.new()
	about.text = "Duel Master Battle %s" % LanSession.GAME_VERSION
	about.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_secondary(about)
	_overlay_vbox.add_child(about)
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


# ---------------------------------------------------------------- test API (client/tests/run_menu_routes.gd)

func ui_visible_entries() -> Array:
	var out: Array = []
	for b in [single_btn, host_btn, join_btn, settings_btn, dev_btn]:
		if b != null and b.visible:
			out.append(b.text)
	return out


func ui_press_single() -> void:
	_on_single_player()


func ui_press_host() -> void:
	_open_lan("host")


func ui_press_join() -> void:
	_open_lan("join")


func ui_show_settings() -> void:
	_show_settings()


func ui_overlay_visible() -> bool:
	return _overlay.visible
