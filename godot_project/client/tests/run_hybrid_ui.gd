extends SceneTree

## Headed UI geometry test for the narrative interface: the arrival text, a conversation (ordinary and very long), the journal (very long), the inspect
## card, the pause menu and the campaign HUD at five window sizes: 450x800 (small portrait), 720x1280 (portrait), 800x450 (small landscape), 1280x720
## (desktop) and 1920x1080 (large). The laptop screen cannot open every size, so each size is set on the real window and, if the window manager did not
## give that size, the layout is computed for it anyway (meta "sim_window": same stretch maths, panels laid out for that window) and the log says which
## sizes were real. For every panel it asserts what a player would notice: the card is fully inside the viewport, no text or button sticks out of it,
## body text is at least 16 physical pixels, every button is at least 44 physical pixels tall, long content scrolls to its last line, the footer stays
## visible, the HUD steps aside for a conversation, and Escape, the Leave button and the acknowledge button all close a conversation the same way.

const ResponsiveModal = preload("res://client/ui/responsive_modal.gd")
const SIZES := [Vector2i(450, 800), Vector2i(800, 450), Vector2i(1280, 720), Vector2i(720, 1280), Vector2i(1920, 1080)]

var _world: Node
var _ui: Node
var _fails: Array[String] = []
var _dir := ""
var _seq := 0
var _real: Dictionary = {}


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, label: String) -> void:
	print("UI %s %s" % ["ok  " if ok else "FAIL", label])
	if not ok:
		_fails.append(label)


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _settle() -> void:
	await _frames(4)
	await RenderingServer.frame_post_draw
	await _frames(2)


func _shot(name: String) -> void:
	await _settle()
	if _world.has_meta("sim_window"):
		return  # a simulated layout is not a picture of that window: no screenshot
	var image: Image = get_root().get_viewport().get_texture().get_image()
	DirAccess.make_dir_recursive_absolute(_dir)
	image.save_png(_dir.replace("\\", "/") + "/%s.png" % name)
	print("UI_SHOT %s" % name)


func _info() -> Dictionary:
	return ResponsiveModal.window_info(_world)


func _set_window(size: Vector2i) -> void:
	if _world.has_meta("sim_window"):
		_world.remove_meta("sim_window")
	DisplayServer.window_set_size(size)
	var t0 := Time.get_ticks_msec()
	while Vector2i(get_root().get_window().size) != size and Time.get_ticks_msec() - t0 < 3000:
		await _frames(5)  # the window manager applies a resize a few frames later
	await _frames(10)
	var got := Vector2i(get_root().get_window().size)
	var real := got == size
	if not real:
		_world.set_meta("sim_window", size)
	_real[size] = real
	_world.relayout_ui()
	await _settle()
	print("UI window %s -> %s (%s)" % [str(size), str(got), "real window" if real else "simulated layout"])


func _buttons(node: Node, out: Array) -> void:
	for c in node.get_children():
		if c is Button and (c as Button).is_visible_in_tree():
			out.append(c)
		_buttons(c, out)


## Everything a player would see wrong with a card, as assertions.
func _geometry(card: Control, label: String) -> void:
	var info := _info()
	var vis := Rect2(Vector2.ZERO, info["vis"])
	var s: float = info["scale"]
	var r: Rect2 = card.panel.get_global_rect()
	_check(vis.grow(1.5).encloses(r), "%s: the card is inside the viewport (card %s, viewport %s)" % [label, str(r), str(vis)])
	var m := ResponsiveModal.metrics(info, card.kind)
	_check(r.size.x * s <= float(m["width"]) + 2.0, "%s: the card is no wider than %d px (%.0f)" % [label, int(m["width"]), r.size.x * s])
	for lbl in [card.title_label, card.subtitle_label, card.body_label]:
		if lbl.visible and (lbl as Control).size.x > 0:
			_check(r.grow(1.5).encloses((lbl as Control).get_global_rect()) or (lbl == card.body_label and r.grow(1.5).intersects((lbl as Control).get_global_rect())),
				"%s: %s stays inside the card" % [label, lbl.name])
			_check((lbl as Control).get_global_rect().end.x <= r.end.x + 1.5, "%s: %s does not run past the right edge" % [label, lbl.name])
	var fs: int = card.body_label.get_theme_font_size("normal_font_size")
	if card.body_label.visible:
		_check(float(fs) * s >= 15.5, "%s: body text is %.1f physical px (at least 16)" % [label, float(fs) * s])
	var bs: Array = []
	_buttons(card.panel, bs)
	var small := 0
	var outside := 0
	for b in bs:
		if (b as Button).size.y * s < 43.5:
			small += 1
		if (b as Button).get_global_rect().end.x > r.end.x + 1.5 or (b as Button).get_global_rect().position.x < r.position.x - 1.5:
			outside += 1
	_check(small == 0, "%s: all %d buttons are at least 44 physical px tall" % [label, bs.size()])
	_check(outside == 0, "%s: no button sticks out sideways" % label)
	if card.footer_box.get_child_count() > 0:
		_check(r.grow(1.5).encloses(card.footer_box.get_global_rect()), "%s: the footer buttons are visible" % label)


## Content longer than the card scrolls, and the last line can be reached.
func _scrolls_to_end(card: Control, label: String) -> void:
	var sb: VScrollBar = card.scroll.get_v_scroll_bar()
	_check(sb.max_value > sb.page + 1.0, "%s: long content scrolls (max %.0f, page %.0f)" % [label, sb.max_value, sb.page])
	card.scroll.scroll_vertical = int(sb.max_value)
	await _frames(3)
	var last: Control = card.choices_box.get_child(card.choices_box.get_child_count() - 1) if card.choices_box.get_child_count() > 0 else card.body_label
	_check(card.scroll.get_global_rect().grow(2.0).encloses(last.get_global_rect()), "%s: the last line is reachable by scrolling" % label)
	card.scroll.scroll_vertical = 0


func _long_reply() -> Dictionary:
	var lines: Array = []
	for i in 6:
		lines.append("Paragraph %d. The lumberjack leans on the axe and takes his time: the trees near the hut are tall, the store is thin, and whatever you decide to do about it, he would like it decided before the next frost." % (i + 1))
	var choices: Array = []
	for i in 12:
		choices.append({"id": "c%d" % i, "text": "Choice %d: ask about the forest, the sawmill, the builders, the weather and anything else that could possibly be worth asking about." % (i + 1), "available": true})
	return {"status": "ok", "npc": "worker:none", "name": "Ragtor Blackshield with a Rather Long Name", "subtitle": "Lumberjack of the Red settlement", "lines": lines, "choices": choices, "ends": false}


func _sim_advance(seconds: int) -> void:
	_seq = int(_world._snapshot.get("clock_sequence", _seq)) + 1
	var reply: Dictionary = _world._sim.op({"op": "advance", "ms": seconds * 1000, "sequence": _seq, "tree_delta": true})
	if str(reply.get("status", "")) == "ok":
		_world._apply_snapshot(reply.get("snapshot", {}))


func _red_worker() -> Dictionary:
	for e in _world._snapshot.get("entities", []):
		if str(e.get("class", "")) == "worker" and str(e.get("faction_name", "")) == "Red" and not bool(e.get("inside", false)):
			return e
	return {}


func _entity_of(cls: String) -> Dictionary:
	for e in _world._snapshot.get("entities", []):
		if str(e.get("class", "")) == cls and (cls != "building" or str(e.get("faction_name", "")) == "Red"):
			return e
	return {}


func _talking() -> Array:
	return _world._sim.op({"op": "journal"}).get("journal", {}).get("talking", [])


func _key(code: int) -> void:
	for pressed in [true, false]:
		var e := InputEventKey.new()
		e.keycode = code
		e.physical_keycode = code
		e.pressed = pressed
		Input.parse_input_event(e)
		await _frames(1)
	await _frames(2)


func _run() -> void:
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
	if _dir == "":
		_dir = "res://../WizardRTSHybrid/docs/evidence/narrative/polish"
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	await _frames(40)
	_ui = _world.story_ui
	DisplayServer.window_set_min_size(Vector2i(300, 300))
	print("UI window min size ", DisplayServer.window_get_min_size(), " mode ", DisplayServer.window_get_mode(), " screen ", DisplayServer.screen_get_size())

	# ---- the arrival: a centred card, a progress indicator, Continue and Skip; Escape and Skip do the same thing
	await _set_window(Vector2i(450, 800))
	_check(await _wait(func(): return _ui.opening_card.visible, 5.0), "the arrival text opens by itself")
	_geometry(_ui.opening_card, "arrival 450x800")
	_check(_ui.opening_card.progress_label.text.contains("1 / 3"), "the arrival shows its progress (%s)" % _ui.opening_card.progress_label.text)
	_check(_ui.opening_card.footer_button("next") != null and _ui.opening_card.footer_button("skip") != null, "the arrival has Continue and Skip")
	await _shot("ui_450x800_arrival")
	_ui.opening_card.footer_pressed.emit("next")
	await _settle()
	_check(_ui.opening_card.progress_label.text.contains("2 / 3"), "Continue turns the page (%s)" % _ui.opening_card.progress_label.text)
	await _key(KEY_ESCAPE)
	_check(not _ui.opening_card.visible and not _world.paused, "Escape closes the arrival and time runs again")
	_check(await _wait(func(): return (_world._sim.op({"op": "journal"}).get("journal", {}).get("opening", ["x"]) as Array).is_empty(), 3.0), "the arrival is recorded as seen")
	_world.paused = true

	var worker := _red_worker()
	_check(not worker.is_empty(), "a Red worker is out in the open")
	var building := _entity_of("building")
	var tree := _entity_of("tree")

	for size in SIZES:
		await _set_window(size)
		var tag := "%dx%d" % [size.x, size.y]
		# -- the HUD: inside the viewport, objective first, hidden behind a conversation
		var info := _info()
		var vis := Rect2(Vector2.ZERO, info["vis"])
		_check(vis.grow(1.5).encloses(_world.hud.panel.get_global_rect()), "hud %s: inside the viewport" % tag)
		_check(_world.hud.objective_label.visible and _world.hud.title_button.text.begins_with("Prehistoric"), "hud %s: era and cycle, then the objective (%s)" % [tag, _world.hud.title_button.text])
		await _shot("ui_%s_hud" % tag)
		# -- a conversation with a real worker
		if not worker.is_empty():
			var e := _by_id(str(worker["id"]))
			_world.set_john_pos(Vector2i(int(e["tx"]) + 1, int(e["ty"])))
			_world._arrived()
			await _frames(3)
			_sim_advance(1)
			e = _by_id(str(worker["id"]))
			_world.set_john_pos(Vector2i(int(e["tx"]) + 1, int(e["ty"])))
			_world._arrived()
			_ui.talk_to(str(worker["id"]))
			await _settle()
			_check(_ui.dialog.visible, "conversation %s: opens" % tag)
			_geometry(_ui.dialog_card, "conversation %s" % tag)
			_check(not _world.hud.visible, "conversation %s: the HUD steps aside" % tag)
			await _shot("ui_%s_conversation" % tag)
			# Escape, the Leave button and a second conversation closed by acknowledging all end it on the server
			await _key(KEY_ESCAPE)
			_check(not _ui.dialog.visible and _world.hud.visible and not (_talking() as Array).has(str(worker["id"])), "conversation %s: Escape closes it, the HUD returns, the person is released" % tag)
			_ui.talk_to(str(worker["id"]))
			await _settle()
			_ui.dialog_card.footer_pressed.emit("leave")
			await _settle()
			_check(not _ui.dialog.visible and not (_talking() as Array).has(str(worker["id"])), "conversation %s: the Leave button closes it the same way" % tag)
			_ui.talk_to(str(worker["id"]))
			await _settle()
			var ids: Array = _ui.dialog_card.choice_ids()
			_check(ids.has("farewell"), "conversation %s: there is a Goodbye choice" % tag)
			if ids.has("farewell"):
				_ui.dialog_card.choice_pressed.emit("farewell")
				await _settle()
				_check(_ui.dialog.visible and _ui.conv_ends and _ui.dialog_card.choice_ids().is_empty() and _ui.dialog_card.footer_button("ack") != null,
					"conversation %s: a closing reply is shown with one Continue button and no other choices" % tag)
				_check((_talking() as Array).has(str(worker["id"])), "conversation %s: the person is still held while the last line is read" % tag)
				await _shot("ui_%s_conversation_end" % tag)
				_ui.dialog_card.footer_pressed.emit("ack")
				await _settle()
				_check(not _ui.dialog.visible and not (_talking() as Array).has(str(worker["id"])), "conversation %s: Continue closes it and releases the person" % tag)
			else:
				_ui.close_dialog()
		# -- a very long conversation scrolls
		_ui._show_dialog(_long_reply())
		await _settle()
		_geometry(_ui.dialog_card, "long conversation %s" % tag)
		await _scrolls_to_end(_ui.dialog_card, "long conversation %s" % tag)
		await _shot("ui_%s_conversation_long" % tag)
		_ui.close_dialog()
		await _settle()
		# -- the journal, long
		var notes: PackedStringArray = []
		for i in 25:
			notes.append("  - Note %d: a line about what happened in the forest that is long enough to wrap across more than one line of the journal." % (i + 1))
		_ui.set_process(false)  # (the journal refreshes its own text while open: the test puts a long text in and keeps it there)
		_ui.journal.show_card("Journal", "", _ui.journal_string() + "\n\nNOTES\n" + "\n".join(notes), [], [{"id": "close", "text": "Close (J)", "kind": "primary"}])
		await _settle()
		_geometry(_ui.journal, "journal %s" % tag)
		var sb: VScrollBar = _ui.journal.scroll.get_v_scroll_bar()
		_check(sb.max_value > sb.page + 1.0, "journal %s: long content scrolls (max %.0f, page %.0f, scroll h %.0f, body h %.0f)" % [tag, sb.max_value, sb.page, _ui.journal.scroll.size.y, _ui.journal.body_box.get_combined_minimum_size().y])
		await _shot("ui_%s_journal" % tag)
		await _key(KEY_ESCAPE)
		_ui.set_process(true)
		_check(not _ui.journal.visible, "journal %s: Escape closes it" % tag)
		await _key(KEY_J)
		_check(_ui.journal.visible, "journal %s: J opens it" % tag)
		await _key(KEY_J)
		_check(not _ui.journal.visible, "journal %s: J closes it" % tag)
		# -- the inspect card: a person, a building, a tree
		for what in [worker, building, tree]:
			if what.is_empty():
				continue
			var cur := _by_id(str(what["id"]))
			_world.wizard_labels.open(str(cur["id"]))
			await _settle()
			_check(_world.wizard_labels.panel.visible, "inspect %s %s: opens" % [str(what.get("class", "")), tag])
			_geometry(_world.wizard_labels.panel, "inspect %s %s" % [str(what.get("class", "")), tag])
			if str(what.get("class", "")) == "worker":
				await _shot("ui_%s_inspect" % tag)
			_world.wizard_labels.close()
		# -- the pause menu
		_world._on_menu()
		await _settle()
		_check(_world.menu_card.visible, "menu %s: opens" % tag)
		_geometry(_world.menu_card, "menu %s" % tag)
		await _shot("ui_%s_menu" % tag)
		await _key(KEY_ESCAPE)
		_check(not _world.menu_card.visible and not _world._input_locked, "menu %s: Escape closes it" % tag)

	var real_n := 0
	for s in SIZES:
		if bool(_real.get(s, false)):
			real_n += 1
	print("UI window sizes opened for real: %d of %d (the rest were laid out by the same stretch maths)" % [real_n, SIZES.size()])
	if _fails.is_empty():
		print("HYBRID_UI_OK")
		quit(0)
	else:
		print("HYBRID_UI_FAIL ", ", ".join(_fails))
		quit(1)


func _by_id(id: String) -> Dictionary:
	for e in _world._snapshot.get("entities", []):
		if str(e.get("id", "")) == id:
			return e
	return {}


func _wait(cond: Callable, seconds := 8.0) -> bool:
	var t0 := Time.get_ticks_msec()
	while not cond.call():
		await _frames(2)
		if (Time.get_ticks_msec() - t0) / 1000.0 > seconds:
			return false
	return true
