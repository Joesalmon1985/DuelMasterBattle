extends SceneTree

## Headed acceptance for mortal apprentices (plan M1, scenario A): this Godot client joins a Python-hosted world where a scripted second human
## (scripts/lan_bot.py, playing the host's wizard) walks up and challenges us. We accept and break the bot's Ward with our first cast: the bot dies
## where it stood (a body row appears on screen, its standing avatar goes), our mother walks over and has words (a conversation she opens
## herself), we promise to put the friend back, open the body's inspect card, choose "Bring them back", watch the channel, and the bot lives again.
## Env: HYBRID_LAN_HOST (127.0.0.1), HYBRID_LAN_PORT, HYBRID_LAN_CODE, HYBRID_SHOT_DIR. Prints HYBRID_MORTALITY_OK.

var _lan: Node


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	DisplayServer.window_set_size(Vector2i(720, 1280))
	Engine.time_scale = 1.0
	var host := OS.get_environment("HYBRID_LAN_HOST")
	if host == "":
		host = "127.0.0.1"
	var port := int(OS.get_environment("HYBRID_LAN_PORT"))
	var code := OS.get_environment("HYBRID_LAN_CODE")
	_lan = root.get_node("/root/LanSession")
	_lan.reset()
	_lan.mode = "join"
	_lan.player_name = "GodotPlayer"
	var hello: Dictionary = _lan.connect_and_hello(host, port, code, "GodotPlayer")
	if str(hello.get("status", "")) != "ok":
		return _die("hello failed: %s" % str(hello))
	var deadline := Time.get_ticks_msec() + 60000
	while Time.get_ticks_msec() < deadline:
		var lob: Dictionary = _lan.sim.op({"op": "lobby"})
		if str(lob.get("session", {}).get("state", "")) == "playing":
			break
		await create_timer(0.3).timeout
	var world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(world)
	for _i in 40:
		await process_frame
	if world._snapshot.is_empty() or not world.mp:
		return _die("no snapshot or not in LAN mode")
	if world.story_ui != null:
		world.story_ui.finish_opening()  # the arrival text: read
	# 1. the other wizard comes to us and challenges; we accept
	deadline = Time.get_ticks_msec() + 90000
	while world.ui_mp_invite().is_empty() and Time.get_ticks_msec() < deadline:
		await process_frame
	if world.ui_mp_invite().is_empty():
		return _die("no invite arrived from the bot")
	var other_id: String = str(world.ui_mp_invite().get("from", ""))
	var acc: Dictionary = world.mp_respond(true)
	if str(acc.get("status", "")) != "ok":
		return _die("accept failed: %s" % str(acc))
	print("HYBRID_MORTALITY_ACCEPTED %s" % other_id)
	deadline = Time.get_ticks_msec() + 30000
	while world.ui_mp_board() == null and Time.get_ticks_msec() < deadline:
		await process_frame
	var board = world.ui_mp_board()
	if board == null:
		return _die("board did not open")
	for _f in 10:
		await process_frame
	for i in 3:
		board.ui_action_select_locus(i)
		board.ui_action_pick_spell([0, 1, 6][i])
	board.ui_action_lock_ward()
	for _f in 10:
		await process_frame
	var sim = world.ui_mp_sim()
	if sim == null or not sim.ward_locked():
		return _die("ward not locked")
	# 2. the bot's Ward is 1,1,3 (the launcher says so): one cast breaks it, and the duel is to the death
	deadline = Time.get_ticks_msec() + 120000
	var cast_done := false
	while Time.get_ticks_msec() < deadline and sim.result == null:
		if sim.phase == sim.Phase.DUELING and not cast_done:
			if sim.can_player_cast():
				board.ui_action_cast()
				cast_done = true
			elif sim.is_player_window_open():
				for i in 3:
					board.ui_action_select_locus(i)
					board.ui_action_pick_spell([1, 1, 6][i])
		await process_frame
	if sim.result == null:
		return _die("duel did not finish")
	print("HYBRID_MORTALITY_RESULT %s" % JSON.stringify({"outcome": sim.result.outcome, "reason": sim.result.reason}))
	if str(sim.result.outcome) != "victory":
		return _die("expected to win with the known Ward: %s" % str(sim.result.outcome))
	deadline = Time.get_ticks_msec() + 5000
	while Time.get_ticks_msec() < deadline and not board.ui_is_result_visible():
		await process_frame
	if not board.ui_pointer_press_overlay_button("Continue"):
		return _die("no Continue button")
	for _f in 10:
		await process_frame
	# 3. the loser is a body on the ground: the players row says dead, the standing avatar is gone, an npc body row is drawn
	deadline = Time.get_ticks_msec() + 15000
	var body_id := ""
	while Time.get_ticks_msec() < deadline and body_id == "":
		var rows: Dictionary = world.ui_mp_players()
		if rows.has(other_id) and bool(rows[other_id].get("dead", false)):
			body_id = str(rows[other_id].get("body", ""))
		await process_frame
	if body_id == "":
		return _die("the loser did not die")
	if world.actor("lan:" + other_id) != null:
		return _die("the dead wizard's standing avatar is still drawn")
	var body := _entity(world, body_id)
	if body.is_empty() or not bool(body.get("body", false)) or not bool(body.get("dead", false)):
		return _die("no body row on screen: %s" % str(body))
	print("HYBRID_MORTALITY_BODY %s" % JSON.stringify({"id": body_id, "tile": [body.get("tx"), body.get("ty")], "seat": body.get("seat")}))
	await _shot(world, "mortality_body")
	# 4. the mother walks over and has words: a conversation she opens, shown on the same card as any other
	deadline = Time.get_ticks_msec() + 120000
	while Time.get_ticks_msec() < deadline and not world.story_ui.dialog.visible:
		await process_frame
	if not world.story_ui.dialog.visible:
		return _die("the mother never came to have words")
	var mother_title: String = world.story_ui.dialog_title.text
	var text: String = world.story_ui.dialog_text.text
	print("HYBRID_MORTALITY_MOTHER %s" % JSON.stringify({"name": mother_title, "text": text.substr(0, 120)}))
	if not text.to_lower().contains("put them back"):
		return _die("the mother's line is not hers: %s" % text)
	await _shot(world, "mortality_mother")
	# a protest, then the promise (the card's choice buttons, as a finger would press them)
	if not world.story_ui.dialog_card.activate_choice_id("protest"):
		return _die("no protest choice")
	for _f in 10:
		await process_frame
	var answer: String = world.story_ui.dialog_text.text
	if not answer.contains("Resurrect them"):
		return _die("she did not answer the protest: %s" % answer)
	if not world.story_ui.dialog_card.activate_choice_id("will_do"):
		return _die("no will_do choice")
	for _f in 10:
		await process_frame
	if world.story_ui.conv_ends:
		world.story_ui.acknowledge()
	for _f in 10:
		await process_frame
	# 5. grounded: a step out of the village is refused in her words (we are beside the settlement; the refusal line is a toast)
	# 6. the body's inspect card offers "Bring them back"; the channel runs; the friend lives
	world.wizard_labels.open(body_id)
	for _f in 10:
		await process_frame
	if not world.wizard_labels.panel.visible:
		return _die("the body's inspect card did not open")
	await _shot(world, "mortality_inspect_body")
	if not world.wizard_labels.panel.activate_choice_id("resurrect"):
		return _die("no Bring them back action (distance %d)" % world.wizard_labels._manhattan(body))
	deadline = Time.get_ticks_msec() + 8000
	while Time.get_ticks_msec() < deadline and world.ui_resurrection().is_empty():
		await process_frame
	if world.ui_resurrection().is_empty():
		return _die("the channel did not start")
	print("HYBRID_MORTALITY_CHANNEL %s" % JSON.stringify(world.ui_resurrection()))
	for _f in 30:
		await process_frame
	await _shot(world, "mortality_channel")
	deadline = Time.get_ticks_msec() + 30000
	var alive := false
	while Time.get_ticks_msec() < deadline and not alive:
		var rows: Dictionary = world.ui_mp_players()
		alive = rows.has(other_id) and not bool(rows[other_id].get("dead", false))
		await process_frame
	if not alive:
		return _die("the friend never came back")
	for _f in 20:
		await process_frame
	if world.actor("lan:" + other_id) == null:
		return _die("the resurrected wizard is not drawn standing")
	if not _entity(world, body_id).is_empty():
		return _die("the body row is still on screen after the resurrection")
	await _shot(world, "mortality_alive")
	print("HYBRID_MORTALITY_OK")
	quit(0)


func _entity(world: Node, id: String) -> Dictionary:
	for e in world._snapshot.get("entities", []):
		if typeof(e) == TYPE_DICTIONARY and str(e.get("id", "")) == id:
			return e
	return {}


func _die(msg: String) -> void:
	print("HYBRID_MORTALITY_FAIL %s" % msg)
	quit(1)


func _shot(world: Node, name: String) -> bool:
	var dir := OS.get_environment("HYBRID_SHOT_DIR")
	if dir == "":
		return true
	world.queue_redraw()
	await process_frame
	await process_frame
	var img := root.get_viewport().get_texture().get_image()
	if img == null:
		return false
	DirAccess.make_dir_recursive_absolute(dir)
	var ok := img.save_png(dir.path_join(name + ".png")) == OK
	print("HYBRID_MORTALITY_SHOT %s %s" % [name, "ok" if ok else "fail"])
	return ok
