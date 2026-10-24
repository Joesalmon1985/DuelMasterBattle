extends CanvasLayer
class_name GodHud

## The minimal HUD of God World (docs/GOD_WORLD_PRD.md 12.4): age, a compact six-faction VP strip, play/pause, 1x/2x/4x, fit, overlay, menu, and
## small event notices. Playback acts on the one simulation clock through the host; the camera never does. Nothing here covers the world for long.

const _VT = preload("res://client/scripts/visual_theme.gd")
const NarrativeCard = preload("res://client/ui/narrative_card.gd")

var world: Node
var top: PanelContainer
var age_lbl: Label
var vp_row: HBoxContainer
var toast: Label
var pause_btn: Button
var speed_btns: Array = []
var fit_btn: Button
var overlay_btn: Button
var menu_btn: Button
var notice: Control  # DmbNarrativeCard for age change / final result / menu
var _toast_t := 0.0
var _last_event_ms := -1
var _chips: Dictionary = {}
var _age_shown := 0
var _final_shown := false


func setup(p_world: Node) -> void:
	world = p_world
	layer = 10
	name = "GodHud"
	top = PanelContainer.new()
	top.name = "TopStrip"
	top.add_theme_stylebox_override("panel", _VT.flat_panel_style(Color(0.07, 0.05, 0.12, 0.86), 0))
	top.set_anchors_preset(Control.PRESET_TOP_WIDE)
	top.offset_bottom = 112
	add_child(top)
	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 4)
	top.add_child(v)
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 10)
	v.add_child(row)
	menu_btn = _small_button("MenuButton", "≡", 64)
	menu_btn.pressed.connect(_on_menu)
	row.add_child(menu_btn)
	age_lbl = Label.new()
	age_lbl.name = "AgeLabel"
	age_lbl.text = "God World"
	age_lbl.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	age_lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	age_lbl.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_VT.apply_label_primary(age_lbl)
	row.add_child(age_lbl)
	pause_btn = _small_button("PauseButton", "❚❚", 64)
	pause_btn.pressed.connect(_on_pause)
	row.add_child(pause_btn)
	for s in [1, 2, 4]:
		var b := _small_button("Speed%dButton" % s, "%d×" % s, 60)
		b.pressed.connect(func(): world.set_speed(s))
		row.add_child(b)
		speed_btns.append(b)
	vp_row = HBoxContainer.new()
	vp_row.name = "VpRow"
	vp_row.alignment = BoxContainer.ALIGNMENT_CENTER
	vp_row.add_theme_constant_override("separation", 8)
	v.add_child(vp_row)
	# bottom-right view controls
	var corner := VBoxContainer.new()
	corner.name = "ViewButtons"
	corner.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	corner.offset_left = -96
	corner.offset_top = -200
	corner.offset_right = -16
	corner.offset_bottom = -24
	corner.add_theme_constant_override("separation", 10)
	add_child(corner)
	fit_btn = _small_button("FitButton", "⤢", 76)
	fit_btn.pressed.connect(func(): world.camera_ctl.fit_board())
	corner.add_child(fit_btn)
	overlay_btn = _small_button("OverlayButton", "#", 76)
	overlay_btn.pressed.connect(func(): world.view.show_overlay = not world.view.show_overlay; world.view.queue_redraw())
	corner.add_child(overlay_btn)
	toast = Label.new()
	toast.name = "Toast"
	toast.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	toast.offset_top = -84
	toast.offset_bottom = -30
	toast.offset_left = 20
	toast.offset_right = -120
	toast.horizontal_alignment = HORIZONTAL_ALIGNMENT_LEFT
	toast.vertical_alignment = VERTICAL_ALIGNMENT_BOTTOM
	toast.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	toast.add_theme_font_size_override("font_size", 22)
	toast.add_theme_color_override("font_color", _VT.COLOR_TEXT_PRIMARY)
	toast.add_theme_color_override("font_outline_color", Color(0.05, 0.03, 0.08))
	toast.add_theme_constant_override("outline_size", 6)
	toast.mouse_filter = Control.MOUSE_FILTER_IGNORE
	toast.visible = false
	add_child(toast)
	notice = NarrativeCard.new()
	add_child(notice)
	notice.setup(world, "modal", "GodNotice")
	notice.footer_pressed.connect(_on_notice_footer)
	notice.choice_pressed.connect(_on_notice_choice)


func _small_button(nm: String, text: String, w: int) -> Button:
	var b := Button.new()
	b.name = nm
	b.text = text
	b.focus_mode = Control.FOCUS_NONE
	b.custom_minimum_size = Vector2(w, 56)
	b.add_theme_font_size_override("font_size", 24)
	_VT.style_secondary_button(b)
	return b


func _process(delta: float) -> void:
	if _toast_t > 0.0:
		_toast_t -= delta
		if _toast_t <= 0.0:
			toast.visible = false


func covering() -> bool:
	return notice.visible


func apply_snapshot(s: Dictionary) -> void:
	var age := int(s.get("age", 1))
	var phase := str(s.get("phase", ""))
	var txt := "Age %d · %s" % [age, str(s.get("age_name", ""))]
	if phase == "SETUP":
		var st: Dictionary = s.get("setup", {})
		txt = "The factions choose their first sites (%d of %d)" % [int(st.get("step", 0)), int(st.get("total", 12))]
	elif phase == "TRANSITIONING":
		txt = "A new age is being built: %s" % str(s.get("age_name", ""))
	var nxt = s.get("next_roll_in_ms")
	if nxt != null and phase == "RUNNING":
		txt += "   ·   next roll in %ds" % int(ceil(float(nxt) / 1000.0))
	var lr = s.get("last_roll")
	if lr != null and typeof(lr) == TYPE_DICTIONARY and int(s.get("game_ms", 0)) - int(lr.get("game_ms", 0)) < 4000:
		txt = "Rolled %d" % int(lr.get("total", 0)) + ("   ·   nothing produces on a 7" if int(lr.get("total", 0)) == 7 else "")
	age_lbl.text = txt
	pause_btn.text = "▶" if bool(s.get("paused", false)) else "❚❚"
	var sp := int(s.get("speed", 1))
	for b in speed_btns:
		var mine: bool = b.text.begins_with(str(sp))
		b.modulate = Color(1, 1, 1, 1) if mine else Color(0.7, 0.7, 0.75, 0.8)
	for f in s.get("factions", []):
		var fid := str(f["id"])
		var chip: Label = _chips.get(fid)
		if chip == null:
			chip = Label.new()
			chip.name = "Vp_" + fid
			chip.add_theme_font_size_override("font_size", 22)
			chip.add_theme_color_override("font_outline_color", Color(0.05, 0.03, 0.08))
			chip.add_theme_constant_override("outline_size", 5)
			chip.custom_minimum_size = Vector2(96, 30)
			chip.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			vp_row.add_child(chip)
			_chips[fid] = chip
		chip.text = "%s %d" % [str(f["name"]).substr(0, 5), int(f["vp"])]
		chip.add_theme_color_override("font_color", Color(str(f["colour"])).lightened(0.25))
	# event notices (small, non-modal)
	for e in s.get("events", []):
		var ms := int(e.get("game_ms", 0))
		if ms <= _last_event_ms:
			continue
		var line := _event_line(e, s)
		if line != "":
			show_toast(line)
	if not s.get("events", []).is_empty():
		_last_event_ms = int(s["events"][-1].get("game_ms", 0))
	# the age change and the final result: dismissible cards
	var t = s.get("transition")
	if t != null and typeof(t) == TYPE_DICTIONARY and int(t.get("age_to", 0)) > _age_shown and int(t.get("age_to", 0)) == age and not notice.visible:
		_age_shown = age
		var winner := _faction_name(s, str(t.get("winner", "")))
		notice.show_card("The %s age" % str(s.get("age_name", "")), "%s reached ten points" % winner,
			"Every faction keeps its two most productive villages and begins again as settlements. The old towns fall quiet; their roads remain as paths.", [], [{"id": "ok", "text": "Watch on"}])
	var fr = s.get("final_result")
	if fr != null and typeof(fr) == TYPE_DICTIONARY and not _final_shown and not notice.visible:
		_final_shown = true
		var winners: Array = fr.get("winners", [])
		var body := ""
		var k := 1
		for wnr in winners:
			body += "Age %d: %s\n" % [k, _faction_name(s, str(wnr))]
			k += 1
		notice.show_card("The world is complete", "%s reached ten points in the final age" % _faction_name(s, str(fr.get("winner", ""))), body.strip_edges() + "\n\nThe world keeps turning for as long as you watch.",
			[{"id": "new_world", "text": "A new world"}], [{"id": "ok", "text": "Keep watching"}])


func _faction_name(s: Dictionary, fid: String) -> String:
	for f in s.get("factions", []):
		if str(f["id"]) == fid:
			return str(f["name"])
	return fid


func _event_line(e: Dictionary, s: Dictionary) -> String:
	var kind := str(e.get("kind", ""))
	var who := _faction_name(s, str(e.get("faction", "")))
	match kind:
		"village_founded": return "%s founded %s" % [who, str(e.get("name", "a village"))]
		"city_complete": return "%s raised %s to a city" % [who, str(e.get("name", "a village"))]
		"expedition_departed": return "%s sent settlers along the road" % who
		"caravan_departed": return "%s sent a caravan to %s" % [who, _faction_name(s, str(e.get("partner", "")))]
		"trade_exchanged": return "%s and %s traded" % [who, _faction_name(s, str(e.get("partner", "")))]
		"bank_trade_done": return "%s traded four for one at the coast" % who
		"road_complete": return "%s finished a road" % who
		"age_started": return "The %s age begins" % str(e.get("name", ""))
		"setup_done": return "The world turns: the first dice roll soon"
	return ""


func show_toast(text: String, seconds: float = 3.5) -> void:
	toast.text = text
	toast.visible = true
	_toast_t = seconds


func _on_pause() -> void:
	world.toggle_pause()


func _on_menu() -> void:
	notice.show_card("God World", "seed %d" % int(world.snapshot.get("seed", 0)), "The world runs on its own. You watch, pan, pinch and tap.",
		[{"id": "save", "text": "Save"}, {"id": "new_world", "text": "Start a new world"}, {"id": "main_menu", "text": "Back to the main menu"}], [{"id": "ok", "text": "Close"}])


func _on_notice_footer(_id: String) -> void:
	notice.hide_card()


func _on_notice_choice(id: String) -> void:
	match id:
		"save":
			var r: Dictionary = world.sim_op({"op": "save", "slot": "manual"})
			show_toast("Saved" if str(r.get("status", "")) == "ok" else "Could not save: %s" % str(r.get("detail", r.get("reason", ""))))
			notice.hide_card()
		"new_world":
			notice.hide_card()
			notice.show_card("Start a new world?", "", "The world you are watching is put aside (its saves are kept) and a new island is settled from nothing.", [{"id": "new_world_yes", "text": "Yes, a new world"}], [{"id": "ok", "text": "Keep this one"}])
		"new_world_yes":
			notice.hide_card()
			world.new_world()
		"main_menu":
			notice.hide_card()
			world.leave_to_menu()
		_:
			notice.hide_card()
