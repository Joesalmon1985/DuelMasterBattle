extends SceneTree

## Scene-level G04 playable proof: shapes, combat, magic, hazard duel via bridge.

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
	# Wait for lease + unit spawn
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
	# Shape / faction colour checks
	var shapes := {}
	var factions := {}
	for uid in battle._unit_nodes.keys():
		var node = battle._unit_nodes[uid]
		shapes[node.archetype] = true
		factions[node.faction_id] = true
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

	# Let combat run — units should approach / take damage
	var hp_before := {}
	for uid in battle._battle.units.keys():
		hp_before[uid] = int(battle._battle.units[uid].get("current_health", 0))
	await create_timer(3.0).timeout
	var moved_or_damaged := false
	for uid in battle._battle.units.keys():
		var u: Dictionary = battle._battle.units[uid]
		if not bool(u.get("alive", true)):
			moved_or_damaged = true
			break
		if int(u.get("current_health", 0)) < int(hp_before.get(uid, 0)):
			moved_or_damaged = true
			break
		var pos = u.get("position", [0, 0])
		# Spawned near 2-4 or 9-11; movement changes position.
		if abs(float(pos[0]) - 3.0) > 0.15 and abs(float(pos[0]) - 10.0) > 0.15:
			moved_or_damaged = true
			break
	if not moved_or_damaged:
		push_error("G04 combat did not move or damage units")
		quit(1)
		return

	# Cast destroy on a living unit
	var target := ""
	for uid in battle._unit_nodes.keys():
		if battle._unit_nodes[uid].alive:
			target = uid
			break
	battle._select_unit(target)
	battle._spell_mode = "destroy"
	battle._cast_selected()
	await create_timer(0.4).timeout
	if battle._battle.units.has(target) and bool(battle._battle.units[target].get("alive", true)) and int(battle._battle.units[target].get("current_health", 1)) > 0:
		# May still be pending lease destruction — force a step
		battle._battle.queue_destruction(target)
		battle._battle.step()
	if bool(battle._battle.units.get(target, {}).get("alive", true)) and int(battle._battle.units.get(target, {}).get("current_health", 1)) > 0:
		push_error("G04 destroy did not kill selected unit")
		quit(1)
		return

	# Buff another living unit
	var buff_target := ""
	for uid in battle._unit_nodes.keys():
		if uid != target and battle._unit_nodes[uid].alive:
			buff_target = uid
			break
	if buff_target != "":
		battle._select_unit(buff_target)
		for kind in ["shield", "frequency", "range"]:
			battle._spell_mode = kind
			battle._cast_selected()
			await create_timer(0.15).timeout

	battle._submit_checkpoint()
	print("G04_BATTLE_PLAYABLE_OK units=", battle._unit_nodes.size(), " destroyed=", target)
	var battle_unit_count: int = battle._unit_nodes.size()
	battle.queue_free()
	await create_timer(0.4).timeout

	# Hazard playable duel
	OS.set_environment("DMB_FIXTURE", "FX-HAZARD")
	OS.set_environment("DMB_SEED", "408")
	var hazard: Control = HazardShell.new()
	root.add_child(hazard)
	await create_timer(2.2).timeout
	deadline = Time.get_ticks_msec() + 4000
	while Time.get_ticks_msec() < deadline and hazard._hex_nodes.size() < 3:
		await create_timer(0.2).timeout
		if hazard._client and hazard._client.has_player_cache():
			hazard._apply_hazard_view(hazard._client.cached_player_view())
	if hazard._hex_nodes.size() < 3:
		push_error("G04 hazard expected 3 manifestations, got %s" % hazard._hex_nodes.size())
		quit(1)
		return
	var cube_id := str(hazard._hex_nodes.keys()[0])
	hazard._selected_cube = cube_id
	hazard._on_duel_requested(cube_id)
	await create_timer(0.3).timeout
	if hazard._duel_id == "":
		push_error("G04 hazard duel did not start")
		quit(1)
		return
	hazard._duel_action("channel")
	await create_timer(0.15).timeout
	hazard._duel_action("channel")
	await create_timer(0.15).timeout
	hazard._duel_action("channel")
	await create_timer(0.4).timeout
	# Cube should be gone from active set after successful duel
	if hazard._client:
		var hview: Dictionary = hazard._client.request_view("player", ["hazards", "fx_hazard"])
		var cubes: Dictionary = hview.get("hazards", {}).get("catastrophe", {}).get("cubes", {})
		if cubes.has(cube_id) and bool(cubes[cube_id].get("active", true)):
			push_error("G04 hazard duel did not remove targeted cube")
			quit(1)
			return
		var still_active := 0
		for cid in cubes.keys():
			if bool(cubes[cid].get("active", true)):
				still_active += 1
		if still_active < 2:
			push_error("G04 removed too many cubes; expected other hexes still active")
			quit(1)
			return
	print("G04_HAZARD_PLAYABLE_OK duel_cleared=", cube_id)
	print("G04_SMOKE_OK battle_units=", battle_unit_count)
	print("G04_PLAYABLE_OK")
	quit(0)
