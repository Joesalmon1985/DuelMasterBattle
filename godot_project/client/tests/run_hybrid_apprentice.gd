extends SceneTree

## Headed test of the whole apprentice opening, played through the real Godot scene at the project's default 450 x 800 window: the arrival text, the
## mentor's lessons (including two Aspect checks and a worldview answer), both practice duels on the retained board, free exploration among ordinary people,
## the stranger's arrival and the confrontation (scene cards, camera guidance, the mentor's death), the lethal Ward Duel fought on the REAL board, and then
## either ending: HYBRID_APPRENTICE_ENDING=win (the aftermath conversations and the final objective) or =lose (Game Over, and New game). No test shortcut
## decides a duel (never ui_debug_finish_duel): every cast is a real board action and the Python lease verifies the report.
## Needs HYBRID_PROFILE=campaign and the shortened timings the suite sets (HYBRID_EXPLORE_MIN_MS and friends).

var _world: Node
var _ui: Node
var _cam: Node
var _fails: Array[String] = []
var _dir := ""
var _seq := 0
var _ending := "win"


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, label: String) -> void:
	print("APPRENTICE %s %s" % ["ok  " if ok else "FAIL", label])
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


func _settle() -> void:
	await _frames(3)
	await RenderingServer.frame_post_draw


func _shot(name: String) -> void:
	await _frames(4)
	await RenderingServer.frame_post_draw
	var image: Image = get_root().get_viewport().get_texture().get_image()
	DirAccess.make_dir_recursive_absolute(_dir)
	image.save_png(_dir.replace("\\", "/") + "/%s.png" % name)
	print("APPRENTICE_SHOT %s" % name)


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
	await _frames(2)


func _by_id(id: String) -> Dictionary:
	for e in _world._snapshot.get("entities", []):
		if str(e.get("id", "")) == id:
			return e
	return {}


func _find(pred: Callable) -> Dictionary:
	for e in _world._snapshot.get("entities", []):
		if typeof(e) == TYPE_DICTIONARY and pred.call(e):
			return e
	return {}


func _journal() -> Dictionary:
	return _world._sim.op({"op": "journal"}).get("journal", {})


func _campaign() -> Dictionary:
	return _journal().get("campaign", {})


func _lesson_done(id: String) -> bool:
	for l in _journal().get("lessons", []):
		if str(l.get("id", "")) == id:
			return bool(l.get("done", false))
	return false


# ---------------------------------------------------------------- talking to people (the real mouse path)

func _talk_to(person: Dictionary) -> void:
	var e := _by_id(str(person["id"]))
	for d in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1), Vector2i(2, 0), Vector2i(0, 2), Vector2i(-2, 0), Vector2i(0, -2)]:
		var t: Vector2i = Vector2i(int(e["tx"]), int(e["ty"])) + (d as Vector2i)
		if _world.is_walkable(t):
			_world.set_john_pos(t)
			_world._arrived()
			break
	await _frames(3)
	var pos := Vector2(float(e["tx"]), float(e["ty"]))
	var vis: Dictionary = _world._art._vis.get(str(e["id"]), {})
	if not vis.is_empty():
		pos = vis["pos"]
	var wp: Vector2 = (pos + Vector2(0.5, 0.2)) * float(_world.TPX)
	_world.camera_focus = wp
	await _settle()
	await _click_at(_world.get_canvas_transform() * wp)
	await _wait_until(func(): return _world.wizard_labels.panel.visible and _world.wizard_labels.current_id == str(e["id"]), 3.0)
	var talk: Button = _world.wizard_labels.panel.choices_box.get_node_or_null("Choice_talk")
	if talk != null and not talk.disabled:
		await _click_button(talk)
	await _wait_until(func(): return _ui.dialog.visible, 3.0)
	_world.camera_focus = Vector2.INF


func _choice(id: String) -> Button:
	return _ui.dialog_card.choice_button(id)


func _choice_ids() -> Array:
	return _ui.dialog_card.choice_ids()


func _press_choice(id: String) -> bool:
	await _wait_until(func(): return _choice(id) != null, 3.0)
	await _settle()
	var b := _choice(id)
	if b == null or b.disabled:
		return false
	_ui.dialog_card.scroll.ensure_control_visible(b)
	await _settle()
	await _click_button(b)
	return true


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


# ---------------------------------------------------------------- scene cards

func _scene_visible() -> bool:
	return _cam.scene_active and _cam.scene_card.visible


func _scene_next_button() -> Button:
	return _cam.scene_card.footer_button("next")


func _scene_choice_ids() -> Array:
	return _cam.scene_card.choice_ids()


## Press Continue on the open scene card; `pick` answers a page that needs an answer (a response id suffix) first.
func _scene_step(pick := "") -> void:
	await _settle()
	if _cam.scene_card.choice_ids().size() > 0:
		var chosen := ""
		for id in _cam.scene_card.choice_ids():
			if pick != "" and str(id).ends_with(":" + pick):
				chosen = str(id)
		if chosen == "":
			chosen = str(_cam.scene_card.choice_ids()[0])
		var cb: Button = _cam.scene_card.choice_button(chosen)
		_cam.scene_card.scroll.ensure_control_visible(cb)
		await _settle()
		await _click_button(cb)
		await _settle()
	var nb := _scene_next_button()
	if nb == null:
		return
	await _click_button(nb)
	await _frames(3)


func _scene_text() -> String:
	return _cam.scene_card.body_label.text


func _scene_title() -> String:
	return _cam.scene_card.title_label.text


# ---------------------------------------------------------------- the real board

func _board() -> Node:
	return _world._adapter._board


func _on_board() -> bool:
	return _world._duel_open and _board() != null and is_instance_valid(_board())


func _set_ward(board: Node, ward: Array) -> bool:
	for sp in ward:
		if not board.ui_pointer_press_tray_spell(int(sp)):
			return false
		await _frames(2)
	if not board.ui_pointer_press_lock_ward():
		return false
	await _frames(3)
	return true


func _cast(board: Node, pattern: Array) -> void:
	for i in pattern.size():
		board.ui_action_select_locus(i)
		board.ui_pointer_press_tray_spell(int(pattern[i]))
		await _frames(1)
	board.ui_action_cast()
	await _frames(2)
	board.ui_advance_time(6.5)
	await _frames(3)


func _finish_board(board: Node) -> bool:
	if not await _wait_until(func(): return board.ui_is_result_visible(), 8.0):
		return false
	return board.ui_pointer_press_overlay_button("Continue")


## A real fight: keep every Ward consistent with the feedback so far, cast one each turn (a careful player).
func _fight_carefully(board: Node, ward: Array) -> int:
	board.ui_set_fast_cast(true)
	await _set_ward(board, ward)
	var candidates: Array = []
	for a in [0, 1, 6]:
		for b in [0, 1, 6]:
			for c in [0, 1, 6]:
				candidates.append([a, b, c])
	var guesses := 0
	while guesses < 12 and not board.game.result and not candidates.is_empty():
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
	return guesses


## A careless fight: the same cast again and again until the apprentice has no casts left.
func _fight_carelessly(board: Node, ward: Array) -> int:
	board.ui_set_fast_cast(true)
	await _set_ward(board, ward)
	var guesses := 0
	while guesses < 14 and not board.game.result:
		await _cast(board, [0, 0, 0])
		guesses += 1
	return guesses


func _lesson_duel(choice: String, label: String, ward: Array, told: bool) -> void:
	_check(await _press_choice(choice), "choose: " + label)
	_check(await _acknowledge(), "acknowledge the mentor's closing words")
	await _wait_until(func(): return _on_board(), 5.0)
	_check(_on_board(), "the retained board opens for the lesson duel")
	if not _on_board():
		return
	var board := _board()
	var n := 0
	if told:
		board.ui_set_fast_cast(true)
		await _set_ward(board, ward)
		while n < 8 and not board.game.result:
			await _cast(board, [1, 6, 1])
			n += 1
	else:
		n = await _fight_carefully(board, ward)
	_check(board.game.result != null, "%s ended after %d real casts" % [label, n])
	_check(await _finish_board(board), "Continue closes the board")
	await _frames(10)
	_check(await _wait_until(func(): return _ui.dialog.visible, 4.0), "the mentor answers after the duel")


func _run() -> void:
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
	if _dir == "":
		_dir = "res://../WizardRTSHybrid/docs/evidence/narrative/apprentice"
	_ending = OS.get_environment("HYBRID_APPRENTICE_ENDING") if OS.get_environment("HYBRID_APPRENTICE_ENDING") != "" else "win"
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(450, 800))
	await _frames(40)
	_ui = _world.story_ui
	_cam = _world.campaign_ui
	var prof: Dictionary = _world._sim.op({"op": "profile"})
	_check(str(prof.get("profile", "")) == "campaign", "the campaign profile (ending: %s)" % _ending)
	_check(Vector2i(DisplayServer.window_get_size()).x <= 600, "a portrait window (%s)" % str(DisplayServer.window_get_size()))

	# ---- the opening: an apprentice who knows their mentor
	_check(await _wait_until(func(): return _ui.opening_card.visible, 4.0), "the arrival text opens by itself")
	var first_page: String = _ui.opening_card.body_label.text
	_check(first_page.contains("apprentice") and first_page.contains("took you in"), "it says the player is an apprentice taught by the mentor: '%s'" % first_page.substr(0, 80))
	await _shot("a01_opening")
	for _i in 3:
		await _click_button(_ui.opening_card.footer_button("next"))
	_check(not _ui.opening_card.visible, "after three pages the arrival closes")
	_world.paused = true

	# ---- the mentor
	var mentor := _find(func(e): return str(e.get("class", "")) == "npc" and str(e.get("role", "")) == "mentor")
	_check(not mentor.is_empty() and bool(mentor.get("has_quest", false)), "the mentor stands near the wizard with a lesson mark")
	await _talk_to(mentor)
	_check(_ui.dialog.visible and _ui.dialog_card.subtitle_label.text == "Mentor", "clicking the mentor, then Talk: the card says Mentor (%s)" % _ui.dialog_card.subtitle_label.text)
	_check(_ui.dialog_text.text.contains("There you are"), "the mentor greets the apprentice as someone they know")
	await _shot("a02_mentor")
	_check(await _press_choice("learn_colours"), "choose: Teach me magic")
	var spells: Array = _journal().get("spells", [])
	_check(spells.has("Flame") and spells.has("Frost") and spells.has("Vine") and int(_journal().get("weave_size", 0)) == 3, "Flame, Frost and Vine are really learned, weave of three (%s)" % str(spells))
	_check(_ui.dialog_text.text.contains("Fracture") and _ui.dialog_text.text.contains("Echo") and _ui.dialog_text.text.contains("Fade"), "fracture, echo and fade are explained")
	# Aspect checks at the mentor: Wonder is harder (3 against 4) and fails, with another path; Curiosity passes; the evidence it gives makes Wonder possible
	_check("ask_wards" in _choice_ids() and str(_choice("ask_wards").text).begins_with("[Curiosity]"), "a Curiosity question is offered, labelled with its Aspect")
	_check(await _press_choice("ask_glow"), "ask about the light around the staff (Wonder, demanding)")
	_check(_ui.dialog_text.text.contains("evening light") and _choice("ask_glow") != null and _choice("ask_glow").disabled, "it fails, there is another path, and asking again is not offered")
	await _shot("a02b_failed_check")
	_check(await _press_choice("ask_wards"), "ask why a Ward has three places (Curiosity)")
	_check(_ui.dialog_text.text.contains("Three is the smallest number"), "Curiosity 3 and the mentor's warmth carry the check: the mentor tells the lore")
	_check(_choice("ask_glow") != null and not _choice("ask_glow").disabled, "what the apprentice learned is evidence: the harder question can now be asked again")
	_check(await _press_choice("ask_glow"), "ask again, with the lore in hand")
	_check(_ui.dialog_text.text.contains("older than the schools"), "and this time the mentor admits something about their craft")
	# a worldview answer
	_check(await _press_choice("why_not_rule"), "ask why wizards do not rule")
	_check(_choice("creed_d") != null and _choice("creed_s") != null, "the answers are real ideological positions, not a list in every conversation")
	await _shot("a03_mentor_creed")
	_check(await _press_choice("creed_d"), "answer: the gift belongs to the land (Druidic)")
	_check(_journal().get("campaign", {}).get("worldview", {}).get("D", 0) == 3, "the apprentice's leanings moved once: Druidic 3")
	await _leave()

	# ---- both practice duels on the real board (the first lost on purpose: a practice duel is not lethal)
	await _talk_to(_find(func(e): return str(e.get("role", "")) == "mentor"))
	await _lesson_duel("told_practice", "break the Ward you were told", [0, 1, 6], true)
	_check(_lesson_done("told_ward") and _lesson_done("colours"), "the lesson is done after a verified duel")
	print("APPRENTICE mentor says: ", _ui.dialog_text.text.replace("\n", " | "))
	await _lesson_duel("hidden_duel", "fight with hidden Wards", [6, 0, 1], false)
	_check(_lesson_done("hidden_ward"), "the hidden-Ward duel completes the lesson")
	await _shot("a04_explore_hint")
	_check(await _press_choice("ask_village_none") or await _press_choice("ask_village"), "choose: What should I do now?")
	_check(_ui.dialog_text.text.contains("Walk through the village"), "the mentor encourages the apprentice to go out and speak with the people")
	await _leave()
	await _sim_advance(2)
	_check(str(_campaign().get("stage", "")) == "explore", "the training is over and the exploration has begun (%s)" % str(_campaign().get("stage", "")))

	# ---- free exploration: ordinary people, with their own beliefs
	await _sim_advance(1)
	var worker_ids: Array = []
	for role in ["lumberjack", "ranger"]:
		var w := _find(func(e): return str(e.get("class", "")) == "worker" and str(e.get("role", "")) == role and str(e.get("faction_name", "")) == "Red" and not bool(e.get("inside", false)))
		if not w.is_empty():
			worker_ids.append(w)
	var carrier := _find(func(e): return str(e.get("class", "")) == "carrier" and str(e.get("faction_name", "")) == "Red")
	if not carrier.is_empty():
		worker_ids.append(carrier)
	_check(worker_ids.size() == 3, "a lumberjack, a forester and a carrier are out and about (%d)" % worker_ids.size())
	var everyday := 0
	var opinion_text := ""
	for p in worker_ids:
		await _talk_to(p)
		if _ui.dialog.visible:
			var ids := _choice_ids()
			for id in ids:
				if str(id).begins_with("topic:opinion"):
					await _press_choice(str(id))
					opinion_text += _ui.dialog_text.text + " || "
					everyday += 1
					break
			await _leave()
	_check(everyday >= 1 and opinion_text != "", "people answer as themselves about wizards, the mentor and the apprentice: %s" % opinion_text.substr(0, 160).replace("\n", " "))
	await _shot("a05_worker_opinion")
	_check(str(_campaign().get("stage", "")) == "explore", "no attack yet: the exploration is still going")
	_world.paused = false
	await _sim_advance(25)
	_world.paused = true

	# ---- the stranger arrives
	_check(await _wait_until(func(): return _scene_visible(), 6.0), "a scene card opens: a stranger is walking in")
	_check(_world.paused and _world.camera_focus != Vector2.INF, "the world waits and the camera is guided to the stranger")
	_check(_scene_text().contains("stranger"), "it says what is happening: '%s'" % _scene_text().substr(0, 70))
	await _shot("b01_stranger_notice")
	await _scene_step()
	_check(not _scene_visible() and not _world.paused, "control returns: the stranger is a figure in the live world")
	var stranger := _find(func(e): return str(e.get("role", "")) == "stranger")
	_check(not stranger.is_empty() and bool(stranger.get("hostile", false)), "the stranger is drawn in the world")
	_world.paused = true
	var walking := true
	for _i in 40:
		await _sim_advance(2)
		if _scene_visible():
			break
	_check(_scene_visible(), "after he has walked up to the mentor the confrontation begins")
	_check(_scene_text().contains("has stopped what they were doing"), "the mentor meets him")
	await _shot("b02_mentor_meets_stranger")

	# ---- the confrontation: each page is acknowledged; the mentor dies; the apprentice answers
	var pages := 0
	var saw_death_page := false
	var answered := false
	while _scene_visible() and pages < 20:
		if _scene_text().contains("falls. The staff rolls"):
			saw_death_page = true
			var fresh_snap: Dictionary = _world._sim.op({"op": "snapshot"}).get("snapshot", {})
			_world._apply_snapshot(fresh_snap)
			_check(bool(_by_id(str(mentor["id"])).get("dead", false)), "the mentor is dead in the world as the page is shown")
			await _shot("b03_mentor_falls")
		if _cam.scene_card.choice_ids().size() > 0 and not answered:
			await _shot("b04_apprentice_answers")
			answered = true
		await _scene_step("s" if _ending == "win" else "d")
		pages += 1
	_check(saw_death_page, "the page where the mentor falls was shown")
	_check(answered, "the apprentice was given a chance to answer, in their own belief")
	_check(_on_board() or await _wait_until(func(): return _on_board(), 6.0), "the scene ends by opening the lethal duel on the real board")
	var camp := _campaign()
	_check(bool(camp.get("mentor_dead", false)) and str(camp.get("mentor_fate", "")) == "killed_by_stranger", "the server records the mentor's death")
	var md: Dictionary = _world._sim.op({"op": "talk", "npc": str(mentor["id"])})
	_check(str(md.get("reason", "")) == "dead", "nobody can talk to the dead mentor (%s)" % str(md.get("reason", "")))
	await _shot("c01_lethal_duel_board")

	# ---- the lethal duel
	var board := _board()
	var n := 0
	if _ending == "win":
		n = await _fight_carefully(board, [6, 0, 1])
	else:
		n = await _fight_carelessly(board, [6, 0, 1])
	_check(board.game.result != null, "the lethal duel ended after %d real casts (%s)" % [n, str(board.game.result.outcome) if board.game.result != null else "?"])
	await _shot("c02_lethal_duel_result")
	_check(await _finish_board(board), "Continue closes the board")
	await _frames(10)

	if _ending == "lose":
		await _finish_lose()
	else:
		await _finish_win()

	if _fails.is_empty():
		print("HYBRID_APPRENTICE_OK")
		quit(0)
	else:
		print("HYBRID_APPRENTICE_FAIL ", ", ".join(_fails))
		quit(1)


func _finish_lose() -> void:
	_check(await _wait_until(func(): return _cam.over_shown, 6.0), "defeat: the Game Over screen opens")
	_check(_cam.over_card.title_label.text == "Game over" and _cam.over_card.subtitle_label.text.contains("defeated"), "it says the apprentice was defeated")
	_check(_cam.over_card.footer_button("new") != null and _cam.over_card.footer_button("quit") != null, "New game and Quit are offered")
	await _shot("d01_game_over")
	var camp := _campaign()
	_check(not (camp.get("game_over", {}) as Dictionary).is_empty() and str(camp.get("stage", "")) != "game_over", "the server holds the apprentice's death (terminal alone), the stage goes on")
	var denied: Dictionary = _world._sim.op({"op": "talk", "npc": "worker:1"})
	_check(str(denied.get("reason", "")) == "game_over", "the dead apprentice cannot act (%s)" % str(denied.get("reason", "")))
	var saved: Dictionary = _world.save_slot("manual")
	_check(str(saved.get("status", "")) == "ok", "the world, with the body in it, is saved all the same (%s)" % str(saved.get("status", "")))
	_check(_world._input_locked and _world.paused, "the client is locked")
	_world._on_menu()
	_check(not _world._menu_open, "the pause menu does not open behind the Game Over screen")
	await _click_button(_cam.over_card.footer_button("new"))
	_check(await _wait_until(func(): return not _cam.over_shown, 4.0), "New game closes the screen")
	var fresh := _campaign()
	_check(str(fresh.get("stage", "")) == "training" and (fresh.get("game_over", {}) as Dictionary).is_empty(), "a fresh world is under way: training again")
	_check(await _wait_until(func(): return _ui.opening_card.visible, 4.0), "and the arrival text shows again")
	await _shot("d02_new_game")


func _finish_win() -> void:
	_check(await _wait_until(func(): return _scene_visible(), 6.0), "victory: the scene of the stranger's retreat opens")
	_check(_scene_text().contains("Ward breaks"), "the Ward broke (%s)" % _scene_text().substr(0, 50))
	await _shot("e01_victory")
	var pages := 0
	while _scene_visible() and pages < 12:
		await _scene_step()
		pages += 1
	_check(not _scene_visible() and not _world._input_locked, "the scene ends and control returns")
	_world.paused = true
	_check(str(_campaign().get("stage", "")) == "aftermath" and (_campaign().get("game_over", {}) as Dictionary).is_empty(), "the story moves to the aftermath")
	var body := _find(func(e): return bool(e.get("dead", false)))
	_check(not body.is_empty(), "the mentor's body lies in the settlement")
	# ordinary people, who react as themselves (whoever is out of doors: the settlement is alive, not arranged)
	await _sim_advance(8)
	var reactions: Array = []
	var talked := 0
	var candidates: Array = []
	for role in ["lumberjack", "ranger", "stonemason", "hunter"]:
		candidates.append(_find(func(e): return str(e.get("class", "")) == "worker" and str(e.get("role", "")) == role and str(e.get("faction_name", "")) == "Red" and not bool(e.get("inside", false))))
	candidates.append(_find(func(e): return str(e.get("class", "")) == "carrier" and str(e.get("faction_name", "")) == "Red"))
	candidates.append(_find(func(e): return str(e.get("class", "")) == "unit" and str(e.get("kind", "")) == "soldier" and str(e.get("faction_name", "")) == "Red"))
	for w in candidates:
		if w.is_empty() or talked >= 2:
			continue
		await _talk_to(w)
		if not _ui.dialog.visible:
			continue
		talked += 1
		reactions.append(_ui.dialog_text.text)
		_check(_choice("topic:t_happened") != null and _choice("topic:t_leave") != null, "%s has things to say about what happened and where to learn more" % str(w.get("label", w.get("role", ""))))
		if talked == 1:
			await _shot("e02_aftermath_first_reaction")
		if _choice("topic:t_meaning") != null:
			await _press_choice("topic:t_meaning")
			var s_choice := ""
			for id in _choice_ids():
				if str(id).begins_with("resp:topic:t_meaning:d"):
					s_choice = str(id)
			if s_choice != "":
				await _press_choice(s_choice)
				if talked == 1:
					await _shot("e03_worldview_answer")
		await _press_choice("topic:t_leave")
		reactions.append(_ui.dialog_text.text)
		await _leave()
	_check(reactions.size() >= 4 and reactions[0] != reactions[2], "two different people react differently: %s || %s" % [reactions[0].substr(0, 70).replace("\n", " ") if reactions.size() > 0 else "", reactions[2].substr(0, 70).replace("\n", " ") if reactions.size() > 2 else ""])
	await _sim_advance(5)
	await _frames(5)
	_check(str(_campaign().get("stage", "")) == "complete", "after a few conversations the introduction is complete")
	await _key(KEY_J)
	_check(_ui.journal.visible and _ui.journal_text.text.contains("seek greater magical power"), "the Journal records the final objective")
	_check(_ui.journal_text.text.contains("ASPECTS") and _ui.journal_text.text.contains("LEANINGS"), "and shows the apprentice's Aspects and leanings")
	await _shot("e04_journal_objective")
	await _key(KEY_J)
	_check(_world.hud != null and _ui.objective_text().contains("Seek greater magical power"), "the HUD shows the objective: %s" % _ui.objective_text())
	await _shot("e05_hud_objective")


func _key(code: int) -> void:
	for pressed in [true, false]:
		var e := InputEventKey.new()
		e.keycode = code
		e.physical_keycode = code
		e.pressed = pressed
		Input.parse_input_event(e)
		await _frames(1)
	await _frames(2)
