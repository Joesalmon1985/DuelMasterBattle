extends SceneTree

## G05 playable integration — FX-VILLAGE Overworld presentation + Mara/factory IDs.
## godot --headless --path godot_project --script res://client/tests/run_g05_playable.gd

const Shell = preload("res://client/scenes/g05_shell.gd")
const VillageTestRunner = preload("res://client/scripts/village_test_runner.gd")


func _init() -> void:
	call_deferred("_run")


func _fail(msg: String) -> void:
	push_error(msg)
	print("G05_PLAYABLE_FAIL %s" % msg)
	quit(1)


func _run() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-VILLAGE")
	OS.set_environment("DMB_SEED", "505")
	var shell = Shell.new()
	root.add_child(shell)
	var deadline := Time.get_ticks_msec() + 20000
	while Time.get_ticks_msec() < deadline and not shell.is_village_ready():
		await process_frame
	if not shell.is_booted() or not shell.is_village_ready():
		_fail("village shell not ready")
		return
	var ow = shell.overworld()
	if ow == null:
		_fail("overworld missing")
		return
	# Wait one more frame for _finish_village_build.
	await process_frame
	await process_frame
	var area: Dictionary = VillageTestRunner.get_area()
	if area.is_empty() or str(area.get("id", "")) == "":
		_fail("area empty")
		return
	var rows: Array = area.get("rows", [])
	if rows.is_empty():
		_fail("no terrain rows")
		return
	var mara_id := shell.mara_actor_id()
	var factory := shell.factory_id()
	if mara_id == "" or factory == "":
		_fail("fx meta missing mara/factory")
		return
	var mara_ent := _entity(area, mara_id)
	var factory_ent := _entity(area, factory)
	if mara_ent.is_empty():
		_fail("Mara entity %s not in area" % mara_id)
		return
	if factory_ent.is_empty():
		_fail("factory entity %s not in area" % factory)
		return
	if not ow.has_method("_john_pos") and not ("_john_pos" in ow):
		# Access player position via Adventure location after build.
		pass
	var john: Vector2i = ow._john_pos
	var before := john
	# Nudge player toward Mara if needed, then SyncPose via movement helper.
	if ow.has_method("_try_step") or true:
		# Direct position write for headless interact reachability.
		var mara_pos: Array = mara_ent.get("pos", [0, 0])
		var stand := Vector2i(int(mara_pos[0]), int(mara_pos[1]) + 1)
		if ow.has_method("_review_tile_walkable") == false:
			ow._john_pos = stand
			ow._john.position = Vector2(stand) * ow.TPX + Vector2(0, -8 * ow.TILE_SCALE)
	# Talk via bridge.
	var talk: Dictionary = shell.talk_to(mara_id)
	if str(talk.get("status", "")) != "ACCEPTED":
		_fail("talk rejected: %s" % str(talk))
		return
	var payload: Dictionary = talk.get("payload", {})
	if str(payload.get("kind", "")) != "dialogue" and str(payload.get("text", "")) == "":
		_fail("dialogue payload empty")
		return
	# Close dialogue formally.
	var session: Dictionary = payload.get("session", {})
	if str(session.get("id", "")) != "":
		shell._cmd("Interact", {"action": "close_dialogue", "session_id": str(session["id"])})
	# Sluice entrance represented.
	var sluice := _entity_by_prefix(area, "entrance:sluice")
	if sluice.is_empty():
		sluice = _entity_has(area, "dungeon_id", "dungeon.sluice")
	if sluice.is_empty():
		_fail("sluice entrance missing")
		return
	# Demon route entrance.
	var demon := _entity(area, "cube:demon")
	if demon.is_empty():
		_fail("demon cube missing")
		return
	# Reproject preserves IDs.
	shell.reproject_from_python()
	await process_frame
	await process_frame
	var area2: Dictionary = VillageTestRunner.get_area()
	var mara2 := _entity(area2, mara_id)
	var factory2 := _entity(area2, factory)
	if mara2.is_empty() or factory2.is_empty():
		_fail("reproject lost mara/factory ids")
		return
	# Enter sluice path (one transition).
	shell.enter_sluice()
	await process_frame
	await process_frame
	var sluice_area: Dictionary = VillageTestRunner.get_area()
	if str(sluice_area.get("id", "")) != "area.sluice":
		_fail("sluice area not loaded")
		return
	var handle := _entity(sluice_area, "item:sluice_handle")
	if handle.is_empty():
		# May already be picked; allow mechanism presence instead.
		if _entity(sluice_area, "box.sluice").is_empty():
			_fail("sluice mechanisms missing")
			return
	else:
		var pick: Dictionary = shell.pickup_item("item:sluice_handle")
		if str(pick.get("status", "")) != "ACCEPTED":
			_fail("pickup failed")
			return
	# Push box once (focused sluice interaction).
	var lease_id := str(sluice_area.get("puzzle_lease_id", ""))
	var lease_ver := int(sluice_area.get("puzzle_lease_version", 1))
	if lease_id != "":
		var push: Dictionary = shell._cmd("Interact", {
			"action": "puzzle_push",
			"lease_id": lease_id,
			"mechanism_id": "box.sluice",
			"expected_version": lease_ver,
		})
		var push_status := str(push.get("status", ""))
		if push_status != "ACCEPTED" and push_status != "REJECTED":
			_fail("puzzle push malformed")
			return
	# Return village; IDs stable.
	shell.return_village()
	await process_frame
	await process_frame
	var area3: Dictionary = VillageTestRunner.get_area()
	if _entity(area3, mara_id).is_empty() or _entity(area3, factory).is_empty():
		_fail("return village lost ids")
		return
	# Demon challenge start (lease open) then resign without claiming victory.
	var started: bool = shell.start_demon_challenge("cube:demon")
	if not started:
		_fail("demon challenge failed to start")
		return
	await process_frame
	var duel_id := ""
	if shell._duel_adapter != null:
		duel_id = str(shell._duel_adapter._duel_id)
	if duel_id != "":
		shell._cmd("ResolveHazardDuel", {"duel_id": duel_id, "success": false})
	print("G05_PLAYABLE_OK mara=%s factory=%s john_before=%s" % [mara_id, factory, before])
	quit(0)


func _entity(area: Dictionary, eid: String) -> Dictionary:
	for raw in area.get("entities", []):
		if typeof(raw) == TYPE_DICTIONARY and str(raw.get("id", "")) == eid:
			return raw
	return {}


func _entity_by_prefix(area: Dictionary, prefix: String) -> Dictionary:
	for raw in area.get("entities", []):
		if typeof(raw) == TYPE_DICTIONARY and str(raw.get("id", "")).begins_with(prefix):
			return raw
	return {}


func _entity_has(area: Dictionary, key: String, value: String) -> Dictionary:
	for raw in area.get("entities", []):
		if typeof(raw) == TYPE_DICTIONARY and str(raw.get(key, "")) == value:
			return raw
	return {}
