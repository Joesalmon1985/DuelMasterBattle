extends SceneTree

## Headed Wizard Mode tutorial and first quest, played through the real Godot scene (execution plan B.4 and the gossip quest). Campaign profile, the six
## faction AIs on. The arrival text is read; the teacher is clicked and the lessons taken through the dialogue buttons; both lesson duels are played on the
## retained board with its real input helpers (ward set from the tray, cast through the loci, time advanced) and verified by the Python lease; the
## villagers' quarrel is played through the dialogue buttons. Needs HYBRID_PROFILE=campaign. Never uses ui_debug_finish_duel.

var _world: Node
var _ui: Node
var _fails: Array[String] = []
var _dir := ""
var _seq := 0


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, label: String) -> void:
	print("TUTORIAL %s %s" % ["ok  " if ok else "FAIL", label])
	if not ok:
		_fails.append(label)


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _win(pos: Vector2) -> Vector2:
	return pos * (Vector2(DisplayServer.window_get_size()) / get_root().get_visible_rect().size)


func _mouse(vpos: Vector2, pressed: bool) -> void:
	var pos := _win(vpos)
	var e := InputEventMouseButton.new()
	e.position = pos
	e.global_position = pos
	e.button_index = MOUSE_BUTTON_LEFT
	e.pressed = pressed
	e.button_mask = 1 if pressed else 0
	Input.parse_input_event(e)


func _click_at(vpos: Vector2) -> void:
	var m := InputEventMouseMotion.new()
	m.position = _win(vpos)
	m.global_position = _win(vpos)
	Input.parse_input_event(m)
	await _frames(1)
	_mouse(vpos, true)
	await _frames(1)
	_mouse(vpos, false)
	await _frames(4)


func _click_button(b: Button) -> void:
	await _click_at(b.get_global_rect().get_center())


## Let the camera move AND draw before a screen position is computed (a window that is not in front gets no draws: the canvas transform
## would be the old one and clicks would land in the wrong place).
func _settle() -> void:
	await _frames(3)
	await RenderingServer.frame_post_draw


func _key(code: int) -> void:
	for pressed in [true, false]:
		var e := InputEventKey.new()
		e.keycode = code
		e.physical_keycode = code
		e.pressed = pressed
		Input.parse_input_event(e)
		await _frames(1)
	await _frames(2)


func _shot(name: String) -> void:
	await _frames(4)
	await RenderingServer.frame_post_draw
	var image: Image = get_root().get_viewport().get_texture().get_image()
	DirAccess.make_dir_recursive_absolute(_dir)
	image.save_png(_dir.replace("\\", "/") + "/%s.png" % name)
	print("TUTORIAL_SHOT %s" % name)


func _wait_until(cond: Callable, seconds := 10.0) -> bool:
	var t0 := Time.get_ticks_msec()
	while not cond.call():
		await _frames(2)
		if (Time.get_ticks_msec() - t0) / 1000.0 > seconds:
			return false
	return true


func _sim_advance(seconds: int) -> void:
	var left := seconds
	while left > 0:
		var chunk := mini(left, 5)
		left -= chunk
		_seq = int(_world._snapshot.get("clock_sequence", _seq)) + 1
		var reply: Dictionary = _world._sim.op({"op": "advance", "ms": chunk * 1000, "sequence": _seq, "tree_delta": true})
		if str(reply.get("status", "")) == "ok":
			_world._apply_snapshot(reply.get("snapshot", {}))


func _by_id(id: String) -> Dictionary:
	for e in _world._snapshot.get("entities", []):
		if str(e.get("id", "")) == id:
			return e
	return {}


func _npcs() -> Array:
	var out: Array = []
	for e in _world._snapshot.get("entities", []):
		if typeof(e) == TYPE_DICTIONARY and str(e.get("class", "")) == "npc":
			out.append(e)
	return out


func _npc_named(name: String) -> Dictionary:
	for e in _npcs():
		if str(e.get("label", "")) == name:
			return e
	return {}


func _teacher() -> Dictionary:
	for e in _npcs():
		if str(e.get("role", "")) == "teacher":
			return e
	return {}


func _journal() -> Dictionary:
	# the world is paused, so the client's snapshot is not refreshed: ask the simulation (the same data the Journal panel shows)
	return _world._sim.op({"op": "journal"}).get("journal", {})


func _lesson_done(id: String) -> bool:
	for l in _journal().get("lessons", []):
		if str(l.get("id", "")) == id:
			return bool(l.get("done", false))
	return false


## Stand next to a person and click their picture (the real mouse path: story_ui picks the person, the dialogue opens).
func _talk_to(person: Dictionary) -> void:
	var e := _by_id(str(person["id"]))  # (the person's tile now, not where they were when the caller looked)
	for d in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1), Vector2i(2, 0), Vector2i(0, 2), Vector2i(-2, 0), Vector2i(0, -2)]:
		var t: Vector2i = Vector2i(int(e["tx"]), int(e["ty"])) + (d as Vector2i)
		if _world.is_walkable(t):
			_world.set_john_pos(t)
			_world._arrived()
			break
	await _frames(3)
	_world._camera.zoom = Vector2(1.0, 1.0)
	var wp: Vector2 = (Vector2(float(e["tx"]), float(e["ty"])) + Vector2(0.5, 0.0)) * float(_world.TPX)
	_world.camera_focus = wp
	await _settle()
	await _click_at(_world.get_canvas_transform() * (wp + Vector2(0, float(_world.TPX) * 0.2)))
	await _wait_until(func(): return _ui.dialog.visible, 4.0)


func _choice(id: String) -> Button:
	for c in _ui.choices_box.get_children():
		if str(c.name) == "Choice_" + id:
			return c
	return null


func _choice_ids() -> Array:
	var out: Array = []
	for c in _ui.choices_box.get_children():
		out.append(str(c.name).trim_prefix("Choice_"))
	return out


func _press_choice(id: String) -> bool:
	await _wait_until(func(): return _choice(id) != null, 3.0)
	var b := _choice(id)
	if b == null or b.disabled:
		return false
	await _click_button(b)
	return true


func _close_dialog() -> void:
	if _ui.dialog.visible:
		_ui.close_dialog()
	await _frames(3)



# ---------------------------------------------------------------- the real board

func _board() -> Node:
	return _world._adapter._board


func _on_board() -> bool:
	return _world._duel_open and _board() != null and is_instance_valid(_board())


## Set the wizard's own Ward from the tray (the SpellSlot press path) and lock it.
func _set_ward(board: Node, ward: Array) -> bool:
	for sp in ward:
		if not board.ui_pointer_press_tray_spell(int(sp)):
			return false
		await _frames(2)
	if not board.ui_pointer_press_lock_ward():
		return false
	await _frames(3)
	return true


## One real cast: choose a spell for each locus from the tray, press Cast, let the cast window run.
func _cast(board: Node, pattern: Array) -> void:
	for i in pattern.size():
		board.ui_action_select_locus(i)
		board.ui_pointer_press_tray_spell(int(pattern[i]))
		await _frames(1)
	board.ui_action_cast()
	await _frames(2)
	board.ui_advance_time(6.5)
	await _frames(3)


func _result_text(board: Node) -> String:
	return board.ui_get_result_text() if board.ui_is_result_visible() else ""


## Close the finished board with its own Continue button (the result overlay appears a moment after the duel ends).
func _finish_board(board: Node) -> bool:
	if not await _wait_until(func(): return board.ui_is_result_visible(), 6.0):
		return false
	return board.ui_pointer_press_overlay_button("Continue")


func _run() -> void:
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
	if _dir == "":
		_dir = "res://../WizardRTSHybrid/docs/evidence/narrative/b"
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	await _frames(40)
	_ui = _world.story_ui
	var prof: Dictionary = _world._sim.op({"op": "profile"})
	_check(str(prof.get("profile", "")) == "campaign", "the campaign profile")

	# ---- the opening
	_check(await _wait_until(func(): return _ui.dialog.visible and _ui.dialog_title.text == "Arrival", 4.0), "the arrival text opens by itself")
	_check(_world.paused, "the world waits while it is read")
	await _shot("opening")
	for _i in 3:
		var nb: Button = _ui.choices_box.get_child(0)
		await _click_button(nb)
	_check(not _ui.dialog.visible and not _world.paused, "after three pages the arrival closes and time runs again")
	_check(await _wait_until(func(): return _ui.journal_data().get("opening", ["x"]).is_empty(), 4.0), "the simulation has recorded that the arrival was seen")

	# ---- meet the teacher, learn the colours, burn something with the new magic
	_world.paused = true  # nobody wanders off between a click and its answer; the test advances time itself when it needs to
	var teacher := _teacher()
	_check(not teacher.is_empty() and bool(teacher.get("has_quest", false)) and str(teacher.get("hint", "")).begins_with("Lesson:"), "a teacher with a lesson marker stands near the wizard")
	var tree_id := ""
	for e in _world._snapshot.get("entities", []):
		if str(e.get("class", "")) == "tree" and str(e.get("stage", "")) in ["old", "mature"]:
			var d := maxi(absi(int(e["tx"]) - _world._john_pos.x), absi(int(e["ty"]) - _world._john_pos.y))
			if d <= 3:
				tree_id = str(e["id"])
				break
	var refused: Dictionary = _world._sim.op({"op": "fire", "target": tree_id if tree_id != "" else "tree:1"})
	_check(str(refused.get("reason", "")) == "spell_unknown", "fire magic is refused before the first lesson (%s)" % str(refused.get("reason", refused.get("status", ""))))
	await _talk_to(teacher)
	_check(_ui.dialog.visible and _ui.dialog_title.text == str(teacher["label"]), "clicking the teacher opens a dialogue with their name (%s)" % _ui.dialog_title.text)
	_check("learn_colours" in _choice_ids(), "the teacher offers to teach magic")
	await _shot("teacher")
	_check(_lesson_done("meet"), "the first meeting is a lesson done")
	_check(await _press_choice("learn_colours"), "choose: Teach me magic")
	_check(_lesson_done("colours") and _journal().get("spells", []).has("Flame"), "the colours are learned: %s, weave %d" % [str(_journal().get("spells", [])), int(_journal().get("weave_size", 0))])
	await _shot("colours")

	# ---- a Ward you were told: the teacher's Ward is Frost, Vine, Frost (1, 6, 1); break it on the real board
	_check(await _press_choice("told_practice"), "choose: Let me try to break your Ward")
	await _wait_until(func(): return _on_board(), 5.0)
	_check(_on_board(), "the retained board opens in the scene")
	var board := _board()
	if _on_board():
		board.ui_set_fast_cast(true)
		_check(board.ui_get_tray_count() == 3, "the tray offers the three colours (%d)" % board.ui_get_tray_count())
		_check(await _set_ward(board, [0, 1, 6]), "the wizard sets and locks a Ward of three from the tray")
		await _shot("told_ward_board")
		var casts := 0
		while casts < 8 and not board.ui_is_result_visible() and not board.game.result:
			await _cast(board, [1, 6, 1])
			casts += 1
		_check(board.game.result != null, "the duel ended after %d real casts" % casts)
		_check(await _finish_board(board), "Continue closes the board")
		await _frames(10)
		_check(await _wait_until(func(): return _ui.dialog.visible, 4.0), "the teacher answers after the duel")
		_check(_lesson_done("told_ward"), "the lesson is done after a verified duel")
		var wins: int = int(_world._sim.op({"op": "journal"}).get("journal", {}).get("lessons", []).size())
		print("TUTORIAL teacher says: ", _ui.dialog_text.text.replace("\n", " | "))
		await _shot("told_ward_result")
		_check(_choice("hidden_duel") != null, "the teacher now offers the hidden-Ward duel")

	# ---- a hidden Ward: a real fight. The wizard keeps every Ward that is consistent with the feedback so far and casts one of them each turn.
	_check(await _press_choice("hidden_duel"), "choose: Fight me properly, with hidden Wards")
	await _wait_until(func(): return _on_board(), 5.0)
	board = _board()
	_check(_on_board(), "the board opens for the hidden-Ward duel")
	if _on_board():
		board.ui_set_fast_cast(true)
		_check(await _set_ward(board, [6, 0, 1]), "the wizard sets and locks a Ward")
		var candidates: Array = []
		for a in [0, 1, 6]:
			for b in [0, 1, 6]:
				for c in [0, 1, 6]:
					candidates.append([a, b, c])
		var guesses := 0
		while guesses < 8 and not board.game.result and not candidates.is_empty():
			var attack: Array = candidates[0]
			await _cast(board, attack)
			guesses += 1
			if board.game.player_history.size() < guesses:
				continue
			var rec = board.game.player_history[guesses - 1]
			var kept: Array = []
			for cand in candidates:
				var r: Dictionary = DmbFeedback.score_attack(cand, attack)
				if int(r["fracture"]) == int(rec.fracture_count) and int(r["echo"]) == int(rec.echo_count):
					kept.append(cand)
			candidates = kept
		await _shot("hidden_ward_board")
		_check(board.game.result != null, "the hidden-Ward duel ended after %d real casts (%s)" % [guesses, str(board.game.result.outcome) if board.game.result != null else "?"])
		_check(await _finish_board(board), "Continue closes the board")
		await _frames(10)
		_check(await _wait_until(func(): return _ui.dialog.visible, 4.0), "the teacher answers after the duel")
		_check(_lesson_done("hidden_ward"), "having fought a hidden Ward completes the lesson")
		print("TUTORIAL teacher says: ", _ui.dialog_text.text.replace("\n", " | "))
		await _shot("hidden_ward_result")

	# ---- the village: the stories unlock, three villagers appear, the teacher says where
	_check("ask_village" in _choice_ids(), "the teacher offers the village question once the lessons are done (%s)" % str(_choice_ids()))
	_check(await _press_choice("ask_village"), "choose: Is anyone in the village in need of help?")
	await _close_dialog()
	_sim_advance(3)
	await _frames(4)
	var ilda := _npc_named("Ilda")
	var brenna := _npc_named("Brenna")
	var orrik := _npc_named("Orrik")
	_check(not ilda.is_empty() and not brenna.is_empty() and not orrik.is_empty(), "Brenna, Orrik and Ilda stand in the village")
	_check(bool(brenna.get("has_quest", false)) and str(brenna.get("hint", "")).begins_with("Quest:"), "they carry the quest marker")
	_check(str(_journal().get("quest", {}).get("status", "")) == "offered", "the journal lists the quarrel as offered")

	# ---- the quarrel, through the dialogue buttons
	await _talk_to(ilda)
	_check(_ui.dialog.visible and _ui.dialog_title.text == "Ilda", "Ilda talks")
	_check(await _press_choice("gossip"), "ask Ilda what people say")
	await _shot("gossip_ilda")
	await _close_dialog()
	await _talk_to(brenna)
	_check(await _press_choice("what_happened"), "hear Brenna's side")
	await _close_dialog()
	await _talk_to(orrik)
	_check(await _press_choice("what_happened"), "hear Orrik's side")
	await _close_dialog()
	await _talk_to(ilda)
	_check("say_fence" in _choice_ids() and "say_coins" in _choice_ids() and "say_nothing" in _choice_ids(), "having heard both, Ilda's advice is asked: %s" % str(_choice_ids()))
	_check(await _press_choice("say_fence"), "suggest that Orrik mends the fence first")
	await _close_dialog()
	await _talk_to(brenna)
	_check("hammer" in _ui.dialog_text.text, "Brenna has heard")
	await _close_dialog()
	await _talk_to(orrik)
	_check("fence" in _ui.dialog_text.text, "Orrik has heard")
	await _close_dialog()
	await _talk_to(ilda)
	_check("hammer" in _ui.dialog_text.text, "Ilda closes the story")
	await _close_dialog()
	_check(str(_journal().get("quest", {}).get("status", "")) == "done", "the quest is done")
	_check(_journal().get("notes", []).size() == 1, "the journal has the note")
	_sim_advance(2)
	await _frames(4)
	await _key(KEY_J)
	_check(_ui.journal.visible and _ui.journal_text.text.contains("The Hen and the Cart  (done)"), "the Journal (J) shows the finished quest")
	await _shot("journal")
	await _key(KEY_J)

	if _fails.is_empty():
		print("HYBRID_TUTORIAL_OK")
		quit(0)
	else:
		print("HYBRID_TUTORIAL_FAIL ", ", ".join(_fails))
		quit(1)
