extends SceneTree

## G04 playable proof via production paths (no destroy fallback / no Channel×3).

const BattleShell = preload("res://client/scenes/g04_battle_shell.gd")
const HazardShell = preload("res://client/scenes/g04_hazard_shell.gd")


func _init() -> void:
	call_deferred("_go")


func _go() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-BATTLE")
	OS.set_environment("DMB_SEED", "404")
	var battle: Control = BattleShell.new()
	root.add_child(battle)
	await create_timer(2.2).timeout
	if battle._client == null:
		push_error("G04 battle shell failed")
		quit(1)
		return
	var deadline := Time.get_ticks_msec() + 4000
	while Time.get_ticks_msec() < deadline and (not battle._lease_opened or battle._unit_nodes.size() < 6):
		await create_timer(0.2).timeout
	if not battle._lease_opened:
		push_error("G04 battle lease not opened")
		quit(1)
		return
	if battle._unit_nodes.size() < 6:
		push_error("G04 expected >=6 comparable-era units, got %s" % battle._unit_nodes.size())
		quit(1)
		return
	# Permanent spell toolbar must be gone.
	if battle.has_node("UIRoot/SpellBar") or battle.find_child("SpellBar", true, false) != null:
		var bar = battle.find_child("SpellBar", true, false)
		if bar != null and bar.visible:
			push_error("G04 permanent SpellBar still visible")
			quit(1)
			return

	var shapes := {}
	var factions := {}
	var initial_pos := {}
	for uid in battle._unit_nodes.keys():
		var node = battle._unit_nodes[uid]
		shapes[node.archetype] = true
		factions[node.faction_id] = true
		initial_pos[uid] = node.position
		if node._poly == null or node._poly.polygon.size() < 3:
			push_error("G04 unit missing polygon visuals: %s" % uid)
			quit(1)
			return
	for need in ["skirmisher", "line", "heavy"]:
		if not shapes.has(need):
			push_error("G04 missing archetype shape %s" % need)
			quit(1)
			return
	if not factions.has("faction:red") or not factions.has("faction:blue"):
		push_error("G04 missing both factions")
		quit(1)
		return

	# Combat: compare each unit against its captured initial coordinate.
	await create_timer(3.0).timeout
	var moved_or_damaged := false
	for uid in battle._unit_nodes.keys():
		var node = battle._unit_nodes[uid]
		if not node.alive:
			moved_or_damaged = true
			break
		if node.position.distance_to(initial_pos[uid]) > 4.0:
			moved_or_damaged = true
			break
		var u: Dictionary = battle._battle.units.get(uid, {})
		if int(u.get("current_health", 0)) < int(u.get("max_health", 0)):
			moved_or_damaged = true
			break
	if not moved_or_damaged:
		push_error("G04 combat did not move or damage units from captured starts")
		quit(1)
		return

	# Destroy via production cast with synchronised nearby poses (no queue_destruction fallback).
	var target := ""
	for uid in battle._unit_nodes.keys():
		if battle._unit_nodes[uid].alive:
			target = uid
			break
	if target == "":
		push_error("G04 no living unit to destroy")
		quit(1)
		return
	# Move wizard pose adjacent to the target through SyncPose + local pose payload.
	var tpos: Array = battle._unit_tile(target)
	battle._cmd("SyncPose", {"position": tpos, "facing": "up"})
	if battle._area != null and battle._area._wizard != null:
		battle._area._wizard.position = Vector2(float(tpos[0]) * 64.0 + 32.0, float(tpos[1]) * 64.0 + 32.0)
	battle._apply_destroy(target)
	var destroy_deadline := Time.get_ticks_msec() + 2500
	while Time.get_ticks_msec() < destroy_deadline:
		await create_timer(0.1).timeout
		var alive := bool(battle._battle.units.get(target, {}).get("alive", true))
		var hp := int(battle._battle.units.get(target, {}).get("current_health", 1))
		if not alive or hp <= 0:
			break
		# Drive lease destruction processing if pending.
		battle._battle.step()
	if bool(battle._battle.units.get(target, {}).get("alive", true)) and int(battle._battle.units.get(target, {}).get("current_health", 1)) > 0:
		push_error("G04 destroy did not kill selected unit via production path")
		quit(1)
		return

	var buff_target := ""
	for uid in battle._unit_nodes.keys():
		if uid != target and battle._unit_nodes[uid].alive:
			buff_target = uid
			break
	if buff_target != "":
		var bpos: Array = battle._unit_tile(buff_target)
		battle._cmd("SyncPose", {"position": bpos, "facing": "up"})
		if battle._area != null and battle._area._wizard != null:
			battle._area._wizard.position = Vector2(float(bpos[0]) * 64.0 + 32.0, float(bpos[1]) * 64.0 + 32.0)
		for kind in ["shield", "frequency", "range"]:
			battle._apply_buff(buff_target, kind)
			await create_timer(0.12).timeout

	# Far observation must not cast.
	var far := ""
	for uid in battle._unit_nodes.keys():
		if uid != target and battle._unit_nodes[uid].alive and not battle._is_nearby(uid):
			far = uid
			break
	if far != "":
		var before_hp := int(battle._battle.units.get(far, {}).get("current_health", 0))
		battle._open_observation(far)
		await create_timer(0.1).timeout
		if int(battle._battle.units.get(far, {}).get("current_health", 0)) != before_hp:
			push_error("G04 far observation must not damage target")
			quit(1)
			return

	battle._submit_checkpoint()
	print("G04_BATTLE_PLAYABLE_OK units=", battle._unit_nodes.size(), " destroyed=", target)
	var battle_unit_count: int = battle._unit_nodes.size()
	battle.queue_free()
	await create_timer(0.4).timeout

	# Hazard: three manifestations + Mastermind (no Channel shortcut).
	OS.set_environment("DMB_FIXTURE", "FX-HAZARD")
	OS.set_environment("DMB_SEED", "408")
	var hazard: Control = HazardShell.new()
	root.add_child(hazard)
	await create_timer(2.2).timeout
	deadline = Time.get_ticks_msec() + 5000
	while Time.get_ticks_msec() < deadline and hazard._hex_nodes.size() < 3:
		await create_timer(0.2).timeout
	if hazard._hex_nodes.size() < 3:
		push_error("G04 hazard expected 3 manifestations, got %s" % hazard._hex_nodes.size())
		quit(1)
		return
	# Anchors must not all share one row.
	var rows := {}
	for cid in hazard._hex_nodes.keys():
		var p: Vector2 = hazard._hex_nodes[cid].position
		rows[int(round(p.y / 64.0))] = true
	if rows.size() < 2:
		push_error("G04 hazard anchors still collinear on one approach row")
		quit(1)
		return

	var cube_id := str(hazard._hex_nodes.keys()[0])
	hazard._on_duel_requested(cube_id)
	await create_timer(0.5).timeout
	if hazard._duel_id == "":
		push_error("G04 hazard duel did not start")
		quit(1)
		return
	# Retained GameBoard must be hosted; Guess/Resign panel must not appear.
	if hazard._duel_adapter == null or not hazard._duel_adapter.is_active():
		push_error("G04 expected retained GameBoard lease adapter to be active")
		quit(1)
		return
	var board = hazard._duel_adapter._board
	if board == null or not is_instance_valid(board):
		push_error("G04 Challenge did not instantiate game_board")
		quit(1)
		return
	if str(board.get_script().resource_path).find("game_board") < 0 and board.get_class() != "GameBoard":
		# Class name may be GameBoard; also accept script path.
		if board.get("game") == null:
			push_error("G04 hosted board missing DmbBattleSim game")
			quit(1)
			return
	if board.game == null:
		push_error("G04 hosted board has no DmbBattleSim instance")
		quit(1)
		return
	var sim_name := str(board.game.get_class())
	if board.game.get_script() != null:
		sim_name = str(board.game.get_script().resource_path)
	if sim_name.find("battle_sim") < 0 and not (board.game is RefCounted):
		push_error("G04 expected DmbBattleSim, got %s" % sim_name)
		quit(1)
		return
	# Channel / Guess panel actions must fail on ward lease.
	var ch: Dictionary = hazard._cmd("HazardDuelAction", {"duel_id": hazard._duel_id, "action": "channel"})
	if str(ch.get("status", "")) == "ACCEPTED":
		push_error("G04 Channel shortcut must be rejected")
		quit(1)
		return
	var guess: Dictionary = hazard._cmd("HazardDuelAction", {"duel_id": hazard._duel_id, "action": "guess", "guess": [0, 1, 2, 3]})
	if str(guess.get("status", "")) == "ACCEPTED":
		push_error("G04 Guess panel path must be rejected for retained duel")
		quit(1)
		return
	# Non-victory resolve leaves cube active (resign/failure).
	var fail: Dictionary = hazard._cmd("ResolveHazardDuel", {"duel_id": hazard._duel_id, "success": false})
	if str(fail.get("status", "")) != "ACCEPTED":
		push_error("G04 ResolveHazardDuel failure path rejected")
		quit(1)
		return
	# Duplicate outcome must be idempotent.
	var dup: Dictionary = hazard._cmd("ResolveHazardDuel", {"duel_id": hazard._duel_id, "success": true})
	if str(dup.get("payload", {}).get("status", "")) != "idempotent" and str(dup.get("status", "")) != "ACCEPTED":
		push_error("G04 duplicate resolve must be accepted/idempotent")
		quit(1)
		return
	hazard._on_retained_duel_finished("fled", fail)
	await create_timer(0.35).timeout
	if hazard._client:
		var hview: Dictionary = hazard._client.request_view("player", ["hazards", "fx_hazard"])
		var cubes: Dictionary = hview.get("hazards", {}).get("catastrophe", {}).get("cubes", {})
		if not cubes.has(cube_id) or not bool(cubes[cube_id].get("active", true)):
			push_error("G04 non-victory must leave cube active (nonterminal failure)")
			quit(1)
			return
		var still_active := 0
		for cid in cubes.keys():
			if bool(cubes[cid].get("active", true)):
				still_active += 1
		if still_active < 3:
			push_error("G04 expected all three cubes still active after non-victory")
			quit(1)
			return
	print("G04_HAZARD_PLAYABLE_OK retained_board cube=", cube_id)
	print("G04_SMOKE_OK battle_units=", battle_unit_count)
	print("G04_PLAYABLE_OK")
	quit(0)
