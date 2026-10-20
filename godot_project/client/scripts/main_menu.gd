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


func _begin_single(continue_game: bool, new_wizard: bool = false, new_world: bool = false, fresh_world: bool = false) -> void:
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
	LanSession.new_wizard = new_wizard
	LanSession.new_world = new_world
	LanSession.fresh_world = fresh_world
	get_tree().change_scene_to_file("res://client/scenes/lan_menu.tscn")


## The village of games: a private session built fresh on seed 507 with every game's host present and the stranger off, on its own saves folder
## (the phone cannot reach the developer menu, so Settings carries this entry).
func _start_games_village() -> void:
	LanSession.reset()
	var sfx := get_node_or_null("/root/Sfx")
	if sfx:
		sfx.cast()
	LanSession.mode = "host"
	LanSession.private_session = true
	LanSession.fresh_world = true
	LanSession.games_village = true
	get_tree().change_scene_to_file("res://client/scenes/lan_menu.tscn")


## Local Wi-Fi play (docs/MOBILE_LAN_MULTIPLAYER.md): the host runs the authoritative world on its own device; a friend joins it.
func _open_lan(mode: String) -> void:
	LanSession.reset()
	LanSession.mode = mode
	get_tree().change_scene_to_file("res://client/scenes/lan_menu.tscn")


## The world on this device is permanent: characters come and go. A living wizard is continued; a dead one is remembered and a new apprentice enters
## the same world; starting a new world is a deliberate act in Settings. No save slots, no world history to pick from.
func _show_continue_choice() -> void:
	_clear_overlay()
	var info: Dictionary = LanSession.wizard_save_info()
	var who := str(info.get("host_name", ""))
	var dead := bool(info.get("host_dead", false))
	var gen := int(info.get("generation", 1))
	var t := Label.new()
	t.text = "Wizard World"
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_title(t)
	_overlay_vbox.add_child(t)
	var l := Label.new()
	l.name = "SaveInfo"
	if dead:
		l.text = "%s died. The world goes on: the village, its people and everything that happened are still there." % (who if who != "" else "Your apprentice")
	elif who != "":
		l.text = "%s is waiting in the world saved on this device.%s" % [who, "" if gen <= 1 else " (Apprentice %d of this world.)" % gen]
	else:
		l.text = "A world is saved on this device."
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_secondary(l)
	_overlay_vbox.add_child(l)
	if not dead:
		var cont := Button.new()
		cont.name = "ContinueButton"
		cont.text = "Continue as %s" % who if who != "" else "Continue"
		cont.custom_minimum_size = Vector2(0, 76)
		_VT.style_primary_button(cont)
		cont.pressed.connect(func():
			_overlay.visible = false
			_begin_single(true))
		_overlay_vbox.add_child(cont)
	var fresh := Button.new()
	fresh.name = "NewCampaignButton"
	fresh.text = "A new apprentice"
	fresh.custom_minimum_size = Vector2(0, 76 if dead else 64)
	if dead:
		_VT.style_primary_button(fresh)
		fresh.pressed.connect(func():
			_overlay.visible = false
			_begin_single(true, true))
	else:
		_VT.style_secondary_button(fresh)
		fresh.pressed.connect(_confirm_new_campaign)
	_overlay_vbox.add_child(fresh)
	_overlay_close_button("Back")
	_overlay.visible = true


func _confirm_new_campaign() -> void:
	_clear_overlay()
	var who := str(LanSession.wizard_save_info().get("host_name", "your apprentice"))
	var t := Label.new()
	t.text = "A new apprentice?"
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_title(t)
	_overlay_vbox.add_child(t)
	var l := Label.new()
	l.text = "%s leaves the village for good and a new apprentice takes their place in the same world. Everything that happened stays happened. (To begin a whole new world, see Settings.)" % who
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_secondary(l)
	_overlay_vbox.add_child(l)
	var yes := Button.new()
	yes.name = "ConfirmNewButton"
	yes.text = "A new apprentice"
	yes.custom_minimum_size = Vector2(0, 64)
	_VT.style_secondary_button(yes)
	yes.pressed.connect(func():
		_overlay.visible = false
		_begin_single(true, true))
	_overlay_vbox.add_child(yes)
	_overlay_close_button("Keep %s" % who)
	_overlay.visible = true


## Settings: the one way to start a whole new world, confirmed twice; the old saves are archived by the host, never deleted.
func _confirm_new_world(second: bool = false) -> void:
	_clear_overlay()
	var t := Label.new()
	t.text = "Start a new world?" if not second else "Are you sure?"
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_title(t)
	_overlay_vbox.add_child(t)
	var l := Label.new()
	l.text = ("A new world means a new village, new people and a new story from the beginning. The world saved on this device is put aside (archived, not deleted)." if not second
		else "The present world, its people and everything that happened in it will no longer be played. This cannot be undone from inside the game.")
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_secondary(l)
	_overlay_vbox.add_child(l)
	var yes := Button.new()
	yes.name = "ConfirmNewWorldButton" if second else "NewWorldButton"
	yes.text = "Yes, start a new world" if second else "Start a new world"
	yes.custom_minimum_size = Vector2(0, 64)
	_VT.style_secondary_button(yes)
	if second:
		yes.pressed.connect(func():
			_overlay.visible = false
			_begin_single(false, false, true))
	else:
		yes.pressed.connect(func(): _confirm_new_world(true))
	_overlay_vbox.add_child(yes)
	_overlay_close_button("Keep my world")
	_overlay.visible = true


## The developer's total reset, confirmed once: every saved world on this device is deleted (not archived), and the next world is built from nothing
## on a new map. "Start a new world" above keeps the old worlds aside; this does not.
func _confirm_fresh_world() -> void:
	_clear_overlay()
	var t := Label.new()
	t.text = "Total reset?"
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_title(t)
	_overlay_vbox.add_child(t)
	var l := Label.new()
	l.text = "Every saved world on this device is deleted, archived ones too, and a new world is built from nothing on a new map: a new village, new people, a new mentor, Mira with no memory of you. For developers; this cannot be undone."
	l.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_VT.apply_label_secondary(l)
	_overlay_vbox.add_child(l)
	var yes := Button.new()
	yes.name = "ConfirmFreshWorldButton"
	yes.text = "Delete everything and start fresh"
	yes.custom_minimum_size = Vector2(0, 64)
	_VT.style_secondary_button(yes)
	yes.pressed.connect(func():
		_overlay.visible = false
		_begin_single(false, false, false, true))
	_overlay_vbox.add_child(yes)
	_overlay_close_button("Keep my worlds")
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
	if LanSession.has_wizard_save():
		var nw := Button.new()
		nw.name = "StartNewWorldButton"
		nw.text = "Start a new world…"
		nw.custom_minimum_size = Vector2(0, 56)
		_VT.style_secondary_button(nw)
		nw.pressed.connect(func(): _confirm_new_world(false))
		_overlay_vbox.add_child(nw)
	# the developer's total reset: nothing archived, nothing kept, a new map (a new seed) and a new story from nothing
	var fresh := Button.new()
	fresh.name = "FreshWorldButton"
	fresh.text = "Developer: total reset…"
	fresh.custom_minimum_size = Vector2(0, 56)
	_VT.style_secondary_button(fresh)
	fresh.pressed.connect(_confirm_fresh_world)
	_overlay_vbox.add_child(fresh)
	# the developer's village of games (docs/PLAN_VILLAGE_MINIGAMES.md): every game's host in one village, on its own saves folder, never the player's world
	var games := Button.new()
	games.name = "GamesVillageButton"
	games.text = "Developer: the village of games"
	games.custom_minimum_size = Vector2(0, 56)
	_VT.style_secondary_button(games)
	games.pressed.connect(_start_games_village)
	_overlay_vbox.add_child(games)
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


func ui_save_info_text() -> String:
	var l := _overlay_vbox.get_node_or_null("SaveInfo") if _overlay_vbox != null else null
	return l.text if l != null else ""


func ui_press_overlay(button_name: String) -> bool:
	var b := _overlay_vbox.get_node_or_null(button_name) if _overlay_vbox != null else null
	if b == null or not (b is Button):
		return false
	b.pressed.emit()
	return true
