extends SceneTree

## Loads every LAN multiplayer script (a parse error fails the run), opens the LAN menu pages without a network and
## screenshots them. No simulator needed.


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	DisplayServer.window_set_size(Vector2i(720, 1280))
	var failed := false
	for path in ["res://client/hybrid/sim_client.gd", "res://client/net/lan_session.gd", "res://client/net/lan_discovery.gd",
			"res://client/duel/net_duel_sim.gd", "res://client/scenes/lan_menu.gd", "res://client/scripts/game_board.gd",
			"res://client/scenes/hybrid_world.gd", "res://client/scripts/main_menu.gd", "res://client/scripts/dev_menu.gd", "res://client/scripts/dev_mode.gd", "res://client/scripts/asset_loader.gd", "res://client/hybrid/trial_mode.gd"]:
		var s = load(path)
		if s == null or not (s is GDScript) or not s.can_instantiate():
			print("HYBRID_LAN_PARSE_FAIL %s" % path)
			failed = true
		else:
			print("parsed %s" % path)
	if failed:
		quit(1)
		return
	# the net duel sim mirrors a host view without a connection
	var NetSim = load("res://client/duel/net_duel_sim.gd")
	var view := {"duel_id": "pvp1", "state": "setup", "you": "p2", "rival": {"id": "p1", "name": "Alice"}, "your_ward": [], "your_history": [], "rival_history": [],
		"format": {"slots": 3, "colours": 3, "max_casts": 10, "allow_repeats": true, "pool": [0, 1, 6]}, "cast_seq": 0,
		"encounter": {"player_combatant": {"id": "player", "display_name": "You", "archetype": "player", "kind": "player", "weave_size": 3, "ward_size": 3, "attack_pool": [0, 1, 6], "ward_pool": [0, 1, 6], "allow_repeats": true, "max_casts": 10, "min_cast_seconds": 0.0, "max_cast_seconds": 60.0},
			"enemy_combatant": {"id": "rival", "display_name": "Alice", "archetype": "wizard", "kind": "player", "weave_size": 3, "ward_size": 3, "attack_pool": [0, 1, 6], "ward_pool": [0, 1, 6], "allow_repeats": true, "max_casts": 10, "min_cast_seconds": 0.0, "max_cast_seconds": 60.0}}}
	var sim = NetSim.new(null, view)
	sim.attach(DmbCombatant.make(view["encounter"]["player_combatant"]), DmbCombatant.make(view["encounter"]["enemy_combatant"]))
	sim.set_player_ward_locus(0, 0)
	sim.set_player_ward_locus(1, 1)
	sim.set_player_ward_locus(2, 6)
	if not sim.can_lock_player_ward():
		print("HYBRID_LAN_PARSE_FAIL net sim cannot lock a complete ward")
		quit(1)
		return
	view["state"] = "active"
	view["your_ward"] = [0, 1, 6]
	view["your_cast_pending"] = true
	view["rival_cast_pending"] = false
	view["rival_history"] = [{"n": 1, "round": 1, "attack": [1, 1, 1], "fracture": 1, "echo": 0, "fade": 2, "broken": false, "auto": false}]
	sim.apply_view(view)
	var ev: Array = sim.get_pending_events()
	if sim.phase != sim.Phase.DUELING or sim.enemy_history.size() != 1 or ev.size() < 2 or not sim.get_enemy_ward()[0] == null:
		print("HYBRID_LAN_PARSE_FAIL net sim view mirror phase=%s hist=%d ev=%d" % [sim.phase, sim.enemy_history.size(), ev.size()])
		quit(1)
		return
	# no rounds: having cast, and the rival not having cast, never produces a "waiting" message and never blocks the next cast
	view["rival_history"] = []
	view["rival_cast_pending"] = true
	sim.apply_view(view)
	var block: String = sim.player_cast_block_reason()
	if block.to_lower().find("waiting") >= 0 or not sim.is_player_window_open():
		print("HYBRID_LAN_PARSE_FAIL net sim blocks a free cast: '%s'" % block)
		quit(1)
		return
	view["rival_history"] = [{"n": 1, "attack": [1, 1, 1], "fracture": 1, "echo": 0, "fade": 2, "broken": false, "auto": false}]
	view["state"] = "finished"
	view["result"] = {"outcome": "victory", "reason": "solved", "your_casts": 2, "rival_casts": 2, "rival_ward": [1, 1, 6]}
	view["rival_ward"] = [1, 1, 6]
	sim.apply_view(view)
	if sim.result == null or sim.result.outcome != "victory" or sim.get_enemy_ward() != [1, 1, 6]:
		print("HYBRID_LAN_PARSE_FAIL net sim result")
		quit(1)
		return
	# a four-colour duel (a wizard's fourth duel on): the host's view lists four spells and the sim accepts the fourth in a Ward
	var view4 := view.duplicate(true)
	view4["state"] = "setup"
	view4["format"] = {"slots": 3, "colours": 4, "max_casts": 10, "allow_repeats": true, "pool": [0, 1, 6, 4]}
	view4["your_ward"] = []
	view4["rival_history"] = []
	view4.erase("result")
	view4.erase("rival_ward")
	for who in ["player_combatant", "enemy_combatant"]:
		view4["encounter"][who]["attack_pool"] = [0, 1, 6, 4]
		view4["encounter"][who]["ward_pool"] = [0, 1, 6, 4]
	var sim4 = NetSim.new(null, view4)
	sim4.attach(DmbCombatant.make(view4["encounter"]["player_combatant"]), DmbCombatant.make(view4["encounter"]["enemy_combatant"]))
	sim4.set_player_ward_locus(0, 4)
	sim4.set_player_ward_locus(1, 1)
	sim4.set_player_ward_locus(2, 4)
	if not sim4.can_lock_player_ward():
		print("HYBRID_LAN_PARSE_FAIL a four-colour duel cannot lock a ward using the fourth colour")
		quit(1)
		return
	# the LAN menu pages
	var menu = load("res://client/scenes/lan_menu.tscn").instantiate()
	root.add_child(menu)
	for _i in 4:
		await process_frame
	for page in ["home", "host", "join"]:
		menu.show_page(page)
		for _i in 6:
			await process_frame
		await _shot("lan_menu_" + page)
	menu.queue_free()
	var main = load("res://client/scenes/main_menu.tscn").instantiate()
	root.add_child(main)
	for _i in 6:
		await process_frame
	await _shot("main_menu_lan_buttons")
	print("HYBRID_LAN_PARSE_OK")
	quit(0)


func _shot(name: String) -> bool:
	var dir := OS.get_environment("HYBRID_SHOT_DIR")
	if dir == "":
		return true
	await process_frame
	await process_frame
	var img := root.get_viewport().get_texture().get_image()
	if img == null:
		return false
	DirAccess.make_dir_recursive_absolute(dir)
	return img.save_png(dir.path_join(name + ".png")) == OK
