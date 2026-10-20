extends SceneTree

## Headed acceptance for the village minigames (docs/PLAN_VILLAGE_MINIGAMES.md): the developer's village of games is started the way the developer
## menu starts it (a private hosted session on its own saves folder, built fresh on seed 507 with every host present), the client is put beside
## each host named in HYBRID_GAMES (default: the mentor's Rock Paper Scissors), talks, takes the game's offer, acknowledges "Lay out the game",
## plays on the REAL table (the buttons and widgets, one `minigame_act` each) until the result or a move cap, leaves, and sees the host's closing
## line on the conversation card. Screenshots go to HYBRID_SHOT_DIR. Needs HYBRID_DEV_OPS=1 for the host's teleport (set here before the host
## starts). Prints HYBRID_MINIGAMES_OK or HYBRID_MINIGAMES_FAIL <reasons>.

var _fails: Array[String] = []
var _world: Node
var _lan: Node
var _scratch := ""
var _dir := ""


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, label: String) -> void:
	print("MINIGAMES %s %s" % ["ok  " if ok else "FAIL", label])
	if not ok:
		_fails.append(label)


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _shot(name: String) -> void:
	if _dir == "":
		return
	await _frames(3)
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute(_dir)
	root.get_viewport().get_texture().get_image().save_png(_dir.path_join("%s.png" % name))
	print("MINIGAMES_SHOT %s" % name)


func _wait_for_scene(path: String, seconds: float) -> Node:
	var t := 0.0
	while t < seconds:
		await create_timer(0.1).timeout
		t += 0.1
		if current_scene != null and current_scene.scene_file_path == path:
			return current_scene
	return null


func _finish() -> void:
	if _world != null and is_instance_valid(_world) and _world.has_method("mp_leave"):
		_world.mp_leave()
	await _frames(5)
	_lan.stop_local_host()
	if _fails.is_empty():
		print("HYBRID_MINIGAMES_OK")
	else:
		print("HYBRID_MINIGAMES_FAIL %s" % "; ".join(PackedStringArray(_fails)))
	quit(0 if _fails.is_empty() else 1)


## The hosts of the games village with their games, from the world's own story snapshot (narrative residents and workers by role).
func _host_for(game: String) -> Dictionary:
	var wanted := {"rps": "mentor", "hanabi": "mentor", "nim": "mother", "pairs": "mother", "rummikub": "keeper", "guesswho": "sawyer", "blackjack": "sawyer",
		"roulette": "water_carrier", "ohhell": "official", "whist": "contestant", "cantstop": "lumberjack", "memory": "ranger", "yahtzee": "stonemason",
		"slide": "stonemason", "reaction": "hunter", "draw_poker": "hunter", "skull": "carrier", "holdem": "carrier"}
	var role := str(wanted.get(game, ""))
	for e in _world._snapshot.get("entities", []):
		if typeof(e) != TYPE_DICTIONARY:
			continue
		var cls := str(e.get("class", ""))
		if cls == "npc" and str(e.get("role", "")) == role and bool(e.get("alive", true)):
			return e
		if cls == "worker" and str(e.get("role", "")) == role and str(e.get("faction_name", "")) == "Red":
			return e
		if cls == "carrier" and role == "carrier" and str(e.get("faction_name", "")) == "Red":
			return e
	return {}


func _play(game: String, idx: int) -> void:
	var host := _host_for(game)
	_check(not host.is_empty(), "%s: a host stands in the village" % game)
	if host.is_empty():
		return
	var tp: Dictionary = _world._sim.op({"op": "teleport", "tx": int(host["tx"]) + 1, "ty": int(host["ty"])})
	_check(str(tp.get("status", "")) == "ok", "%s: teleported beside %s (%s)" % [game, str(host.get("label", "")), str(tp.get("status", ""))])
	_world.refresh_snapshot()
	_world._place_john_from_snapshot()
	await _frames(8)
	var ui = _world.story_ui
	ui.use_entity(host)
	await _frames(4)
	_check(ui.dialog.visible, "%s: the conversation card opened" % game)
	var offer := "game:" + game
	_check(ui.dialog_card.has_choice(offer), "%s: the host offers the game (%s)" % [game, str(ui.dialog_card.choice_ids())])
	if not ui.dialog_card.has_choice(offer):
		ui.close_dialog()
		return
	await _shot("%02d_%s_offer" % [idx, game])
	ui.dialog_card.activate_choice_id(offer)
	await _frames(4)
	_check(ui.conv_ends and not ui.conv_game.is_empty(), "%s: the intro card waits for 'Lay out the game'" % game)
	var btn: Button = ui.dialog_card.footer_button("ack")
	_check(btn != null and btn.text == "Lay out the game", "%s: the acknowledge button says 'Lay out the game'" % game)
	await _shot("%02d_%s_intro" % [idx, game])
	ui.acknowledge()
	await _frames(4)
	var table = _world.minigame_table
	_check(table.visible and _world.minigame_open(), "%s: the table is on screen" % game)
	_check(not ui.dialog.visible, "%s: the conversation card stepped aside" % game)
	_check(_world._input_locked, "%s: the world is locked while the table is open" % game)
	await _shot("%02d_%s_table" % [idx, game])
	print("MINIGAMES_LAYOUT %s" % JSON.stringify({"panel": [table._panel.position, table._panel.size], "inner": table._inner.size, "scroll": [table._scroll.position, table._scroll.size],
		"areas": table._areas.size, "message": [table._message.position, table._message.size], "actions": [table._actions.position, table._actions.size, table._actions.columns],
		"footer": [table._footer.position, table._footer.size], "buttons": table._action_buttons.size(), "btn0": (table._action_buttons[0].size if table._action_buttons.size() > 0 else Vector2.ZERO)}))
	var moves := 0
	var cap := 60
	while not bool(table.view.get("over", false)) and moves < cap:
		var buttons: Array = table._action_buttons
		var pressed := false
		for b in buttons:
			if not (b as Button).disabled:
				(b as Button).pressed.emit()
				pressed = true
				break
		if not pressed:
			break
		moves += 1
		await _frames(1)
	_check(moves > 0, "%s: at least one move was made through the table's buttons (%d)" % [game, moves])
	await _shot("%02d_%s_played" % [idx, game])
	var over := bool(table.view.get("over", false))
	print("MINIGAMES_RESULT %s" % JSON.stringify({"game": game, "moves": moves, "over": over, "result": str(table.view.get("result", ""))}))
	table.leave()
	await _frames(4)
	_check(not _world.minigame_open(), "%s: the table closed" % game)
	_check(ui.dialog.visible and ui.npc_id != "", "%s: the host's closing line came back on the conversation card" % game)
	_check(not _world._input_locked or ui.dialog.visible, "%s: the lock belongs to the card now" % game)
	await _shot("%02d_%s_after" % [idx, game])
	ui.close_dialog()
	await _frames(3)
	_check(not ui.dialog.visible, "%s: the conversation closed" % game)


func _run() -> void:
	DisplayServer.window_set_size(Vector2i(720, 1280))
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
	_scratch = ProjectSettings.globalize_path("user://").path_join("minigames_%d" % (Time.get_ticks_msec() % 100000))
	DirAccess.make_dir_recursive_absolute(_scratch)
	OS.set_environment("DMB_RUNS_DIR", _scratch)
	OS.set_environment("HYBRID_DEV_OPS", "1")
	OS.set_environment("HYBRID_AI", "0")
	_lan = root.get_node("LanSession")
	_lan.reset()
	# the developer menu's entry, without the menu: the same flags
	_lan.mode = "host"
	_lan.private_session = true
	_lan.fresh_world = true
	_lan.games_village = true
	_check(_lan.runs_dir().ends_with("games_village"), "the games village keeps its own saves folder")
	var lobby = load("res://client/scenes/lan_menu.tscn").instantiate()
	root.add_child(lobby)
	_world = await _wait_for_scene("res://client/scenes/hybrid_world.tscn", 240.0)
	if _world == null:
		_check(false, "the games village never opened (%s)" % str(_lan.host_status()))
		await _finish()
		return
	for _i in 90:
		await process_frame
	_check(_world.mp and _lan.private_session, "a private hosted session")
	if _world.story_ui != null and _world.story_ui.opening_card.visible:
		_world.story_ui.finish_opening()
		await _frames(4)
	var j: Dictionary = _world.story_ui.journal_data()
	var games: Dictionary = j.get("games", {}) if typeof(j.get("games", {})) == TYPE_DICTIONARY else {}
	_check(not games.is_empty() and games.has("all"), "the journal carries the Games page")
	await _shot("00_village")
	var which := OS.get_environment("HYBRID_GAMES")
	var list: Array = ["rps"] if which == "" else Array(which.split(","))
	var idx := 1
	for game in list:
		await _play(str(game), idx)
		idx += 1
	await _finish()
