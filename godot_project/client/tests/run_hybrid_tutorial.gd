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


func _teacher() -> Dictionary:
	for e in _npcs():
		if str(e.get("role", "")) == "teacher":
			return e
	return {}


## The entity id of the person with this name (people near the wizard are published with their names).
func _id_of(person_name: String) -> String:
	for id in _ui.persons():
		if str(_ui.persons()[id].get("name", "")) == person_name:
			return str(id)
	for e in _npcs():
		if str(e.get("label", "")) == person_name:
			return str(e["id"])
	return ""


func _journal() -> Dictionary:
	# the world is paused, so the client's snapshot is not refreshed: ask the simulation (the same data the Journal panel shows)
	return _world._sim.op({"op": "journal"}).get("journal", {})


func _lesson_done(id: String) -> bool:
	for l in _journal().get("lessons", []):
		if str(l.get("id", "")) == id:
			return bool(l.get("done", false))
	return false


func _talking() -> Array:
	return _journal().get("talking", [])


## Stand next to a person, click their picture (the real mouse path: the inspect card opens), and press Talk on it.
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
	var pos := Vector2(float(e["tx"]), float(e["ty"]))
	var vis: Dictionary = _world._art._vis.get(str(e["id"]), {})
	if not vis.is_empty():
		pos = vis["pos"]  # click where the figure is drawn
	var wp: Vector2 = (pos + Vector2(0.5, 0.2)) * float(_world.TPX)
	_world.camera_focus = wp
	await _settle()
	await _click_at(_world.get_canvas_transform() * wp)
	await _wait_until(func(): return _world.wizard_labels.panel.visible and _world.wizard_labels.current_id == str(e["id"]), 3.0)
	var talk: Button = _world.wizard_labels.panel.choices_box.get_node_or_null("Choice_talk")
	if talk != null and not talk.disabled:
		await _click_button(talk)
	await _wait_until(func(): return _ui.dialog.visible, 3.0)


func _choice(id: String) -> Button:
	return _ui.dialog_card.choice_button(id)


func _choice_ids() -> Array:
	return _ui.dialog_card.choice_ids()


func _press_choice(id: String) -> bool:
	await _wait_until(func(): return _choice(id) != null, 3.0)
	await _settle()  # the card fits itself over two frames after its content changes: click where the button finally is
	var b := _choice(id)
	if b == null or b.disabled:
		return false
	_ui.dialog_card.scroll.ensure_control_visible(b)  # a long conversation scrolls: bring the button into view, as a player would
	await _settle()
	await _click_button(b)
	return true


## The visible footer button: Leave (Esc) while a conversation goes on, Continue / Begin the duel once it has ended.
func _footer(id: String) -> Button:
	return _ui.dialog_card.footer_button(id)


func _acknowledge() -> bool:
	await _settle()
	var b := _footer("ack")
	if b == null:
		return false
	await _click_button(b)
	return true


func _leave() -> void:
	await _settle()
	var b := _footer("leave")
	if b != null:
		await _click_button(b)
	elif _ui.dialog.visible:
		await _acknowledge()
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

	# ---- the opening: three pages, a progress indicator, Continue and Begin
	_check(await _wait_until(func(): return _ui.opening_card.visible, 4.0), "the arrival text opens by itself")
	_check(_world.paused, "the world waits while it is read")
	await _shot("opening")
	for _i in 3:
		var nb: Button = _ui.opening_card.footer_button("next")
		await _click_button(nb)
	_check(not _ui.opening_card.visible and not _world.paused, "after three pages the arrival closes and time runs again")
	_check(await _wait_until(func(): return _journal().get("opening", ["x"]).is_empty(), 4.0), "the simulation has recorded that the arrival was seen")
	_world.paused = true  # nobody wanders off between a click and its answer; the test advances time itself when it needs to

	# ---- meet the teacher: click, inspect, Talk
	var teacher := _teacher()
	_check(not teacher.is_empty() and bool(teacher.get("has_quest", false)), "a teacher with a small lesson mark stands near the wizard")
	var refused: Dictionary = _world._sim.op({"op": "fire", "target": "tree:1"})
	_check(str(refused.get("reason", "")) == "spell_unknown", "fire magic is refused before the first lesson (%s)" % str(refused.get("reason", refused.get("status", ""))))
	await _talk_to(teacher)
	_check(_ui.dialog.visible and _ui.dialog_title.text == str(teacher["label"]), "clicking the teacher, then Talk, opens a conversation with their name (%s)" % _ui.dialog_title.text)
	_check(_ui.dialog_card.subtitle_label.text == "Teacher", "the card says who they are (%s)" % _ui.dialog_card.subtitle_label.text)
	_check("learn_colours" in _choice_ids() and _footer("leave") != null, "the teacher offers to teach magic, and Leave is there")
	await _shot("teacher")
	_check(_lesson_done("meet"), "the first meeting is a lesson done")
	_check(await _press_choice("learn_colours"), "choose: Teach me magic")
	_check(_lesson_done("colours") and _journal().get("spells", []).has("Flame"), "the colours are learned: %s, weave %d" % [str(_journal().get("spells", [])), int(_journal().get("weave_size", 0))])
	_check(_ui.dialog.visible and not _ui.conv_ends, "the conversation goes on after a choice that leads to more")
	await _shot("colours")
	await _leave()
	_check(not _ui.dialog.visible and _talking().is_empty(), "Leave closes it and the teacher is released")

	# ---- a Ward you were told. The teacher's closing line is shown and acknowledged BEFORE the board opens.
	await _talk_to(_teacher())
	_check(await _press_choice("told_practice"), "choose: Let me try to break your Ward")
	_check(_ui.dialog.visible and _ui.conv_ends and _ui.dialog_text.text.contains("Frost, Vine, Frost") and _ui.choices_box.get_child_count() == 0,
		"the teacher's last words are shown, with no other choices (%s)" % _ui.dialog_text.text.replace("\n", " "))
	_check(not _world._duel_open and _footer("ack") != null and _footer("ack").text == "Begin the duel", "the board has not opened yet: one button, 'Begin the duel'")
	await _shot("told_ward_intro")
	_check(await _acknowledge(), "acknowledge")
	await _wait_until(func(): return _on_board(), 5.0)
	_check(_on_board() and not _ui.dialog.visible, "the retained board opens in the scene and the conversation is closed")
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
		print("TUTORIAL teacher says: ", _ui.dialog_text.text.replace("\n", " | "))
		await _shot("told_ward_result")
		_check(_choice("hidden_duel") != null, "the teacher now offers the hidden-Ward duel")

	# ---- a hidden Ward: a real fight. The wizard keeps every Ward consistent with the feedback so far and casts one of them each turn.
	_check(await _press_choice("hidden_duel"), "choose: Fight me properly, with hidden Wards")
	_check(await _acknowledge(), "acknowledge the teacher's closing words")
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
		await _shot("hidden_ward_result")

	# ---- the village: the stories unlock and the teacher says who and where, by the names of people who really work here
	_check("ask_village" in _choice_ids(), "the teacher offers the village question once the lessons are done (%s)" % str(_choice_ids()))
	_check(await _press_choice("ask_village"), "choose: Is anyone in the village in need of help?")
	var tell: String = _ui.dialog_text.text
	await _leave()
	_sim_advance(2)
	await _frames(4)
	var quest: Dictionary = {}
	for q in _journal().get("quests", []):
		quest = q
	_check(not quest.is_empty() and str(quest.get("status", "")) == "offered" and str(quest.get("title", "")) == "The Forest Dispute", "the journal lists The Forest Dispute as offered")
	var people: Dictionary = {}
	for who in quest.get("people", []):
		people[str(who["role"])] = who
	_check(people.size() == 3 and str(people["cutter"]["occupation"]) == "lumberjack" and str(people["planter"]["occupation"]) == "forester", "three people: a lumberjack, a forester and a witness (%s)" % str(people.keys()))
	for role in people:
		_check(tell.contains(str(people[role]["name"])), "the teacher named %s" % str(people[role]["name"]))
		_check(str(people[role]["where"]).contains("tiles"), "the journal says where %s is: '%s'" % [str(people[role]["name"]), str(people[role]["where"])])
	var ids := {}
	for role in people:
		ids[role] = _id_of(str(people[role]["name"]))
		_check(ids[role] != "", "%s is one of the settlement's own figures on the map (%s)" % [str(people[role]["name"]), str(ids[role])])
		var row := _by_id(str(ids[role]))
		_check(not row.is_empty() and str(row.get("class", "")) in ["worker", "unit"] and not row.has("has_quest"), "and looks like any other worker: class %s, no quest mark" % str(row.get("class", "")))
	await _shot("quest_offered")

	# ---- the quarrel, through real conversations with ordinary people
	var woodcutter: String = ids["cutter"]
	var forester: String = ids["planter"]
	var witness: String = ids["witness"]
	await _talk_to(_by_id(woodcutter))
	_check(_ui.dialog_title.text == str(people["cutter"]["name"]) and _ui.dialog_card.subtitle_label.text.begins_with("Lumberjack"), "the woodcutter talks, as himself (%s, %s)" % [_ui.dialog_title.text, _ui.dialog_card.subtitle_label.text])
	_check("what_happened" in _choice_ids() and "farewell" in _choice_ids() or "leave" in _choice_ids(), "he has the dispute to tell about, and also the ordinary things a lumberjack says: %s" % str(_choice_ids()))
	var topic := ""
	for id in _choice_ids():
		if str(id).begins_with("topic:"):
			topic = str(id)
	_check(topic != "" and await _press_choice(topic), "ask him an everyday question")
	_check(topic != "" and _choice(topic) == null, "the answer is shown and that question is not offered again")
	await _shot("worker_conversation")
	_check(await _press_choice("what_happened"), "hear the woodcutter's side")
	await _leave()
	await _talk_to(_by_id(forester))
	_check(_ui.dialog_card.subtitle_label.text.begins_with("Forester"), "the forester talks (%s)" % _ui.dialog_card.subtitle_label.text)
	_check(await _press_choice("what_happened"), "hear the forester's side")
	await _leave()
	await _talk_to(_by_id(witness))
	_check(_ui.dialog_card.subtitle_label.text.begins_with("Soldier"), "the witness is a soldier (%s)" % _ui.dialog_card.subtitle_label.text)
	_check("say_compromise" in _choice_ids() and "say_cutter" in _choice_ids() and "say_planter" in _choice_ids() and "say_nothing" in _choice_ids(), "having heard both, the four ways to answer are offered")
	_check(str(_choice("say_compromise").text).contains(str(people["cutter"]["name"])), "and they name the real people")
	_check(await _press_choice("say_compromise"), "suggest they share the clearing")
	await _leave()
	await _talk_to(_by_id(woodcutter))
	_check(_ui.dialog_text.text.contains("Share the clearing"), "the woodcutter reacts: '%s'" % _ui.dialog_text.text.substr(0, 60).replace("\n", " "))
	await _leave()
	await _talk_to(_by_id(forester))
	await _leave()
	await _talk_to(_by_id(witness))
	_check(_ui.dialog_text.text.contains("shared clearing"), "and the witness closes it")
	await _leave()
	var done: Dictionary = {}
	for q in _journal().get("quests", []):
		done = q
	_check(str(done.get("status", "")) == "done", "the quest is done")
	_check(_journal().get("notes", []).size() == 1 and str(_journal()["notes"][0]["text"]).contains(str(people["cutter"]["name"])), "the journal has the note, with real names")
	_sim_advance(2)
	await _frames(4)
	await _key(KEY_J)
	_check(_ui.journal.visible and _ui.journal_text.text.contains("THE FOREST DISPUTE  (done)"), "the Journal (J) shows the finished quest")
	await _shot("journal")
	await _key(KEY_J)
	# afterwards they are still ordinary people
	await _talk_to(_by_id(woodcutter))
	var everyday := false
	for id in _choice_ids():
		everyday = everyday or str(id).begins_with("topic:")
	_check(everyday and "what_happened" not in _choice_ids(), "afterwards the woodcutter is still an ordinary person with ordinary things to say")
	await _leave()

	if _fails.is_empty():
		print("HYBRID_TUTORIAL_OK")
		quit(0)
	else:
		print("HYBRID_TUTORIAL_FAIL ", ", ".join(_fails))
		quit(1)
