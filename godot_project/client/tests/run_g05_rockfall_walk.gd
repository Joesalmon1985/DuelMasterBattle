extends SceneTree

## G05 rockfall local-walk regression — corridor must free after clear without
## requiring a LocalArea leave/re-enter. Uses the same _apply_world_layers path
## as periodic industry refresh (not a full rebuild-only emergency).
## godot --headless --path godot_project --script res://client/tests/run_g05_rockfall_walk.gd

const Shell = preload("res://client/scenes/g05_shell.gd")
const VillageTestRunner = preload("res://client/scripts/village_test_runner.gd")

const ROCKFALL_ID := "rockfall:1"
const SAVE_SLOT := "g05_rockfall_walk"


func _init() -> void:
	call_deferred("_run")


func _fail(msg: String) -> void:
	push_error(msg)
	print("G05_ROCKFALL_WALK_FAIL %s" % msg)
	quit(1)


func _dict(v) -> Dictionary:
	return v if typeof(v) == TYPE_DICTIONARY else {}


func _run() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-VILLAGE")
	OS.set_environment("DMB_SEED", "507")
	var shell = Shell.new()
	root.add_child(shell)
	var deadline := Time.get_ticks_msec() + 30000
	while Time.get_ticks_msec() < deadline and not shell.is_village_ready():
		await process_frame
	if not shell.is_booted() or not shell.is_village_ready():
		_fail("village shell not ready")
		return
	var ow = shell.overworld()
	if ow == null:
		_fail("overworld missing")
		return
	await process_frame
	await process_frame

	var rock := _rockfall_entity(VillageTestRunner.get_area())
	if rock.is_empty():
		_fail("rockfall entity missing from area")
		return
	if not bool(rock.get("blocks_walk", false)):
		_fail("rockfall should start blocking")
		return
	var corridor: Array = rock.get("blocked_tiles", [])
	if corridor.is_empty():
		_fail("rockfall blocked_tiles empty while blocking")
		return
	var sample := Vector2i(int(corridor[0][0]), int(corridor[0][1]))
	if ow.is_walkable(sample):
		_fail("expected corridor tile blocked before clear: %s" % str(sample))
		return

	# Python Travel rejected while blocked.
	if shell.travel_to_node("node:35", "node:29"):
		_fail("Travel should be rejected while rockfall blocks")
		return
	var fb := str(shell.last_travel_feedback()).to_lower()
	if "rockfall" not in fb and "block" not in fb:
		_fail("expected rockfall Travel feedback, got: %s" % fb)
		return

	# Discover + ask any eligible worker (normal quest route).
	var obs: Dictionary = shell._cmd("Observe", {"entity_id": ROCKFALL_ID})
	if str(obs.get("status", "")) != "ACCEPTED":
		_fail("Observe rockfall rejected: %s" % str(obs))
		return
	var helper := _first_helper(shell)
	if helper == "":
		_fail("no eligible helper found via talk choices")
		return
	var talk: Dictionary = shell.talk_to(helper)
	if str(talk.get("status", "")) != "ACCEPTED":
		_fail("talk rejected: %s" % str(talk))
		return
	var session: Dictionary = _dict(_dict(talk.get("payload")).get("session"))
	var choose: Dictionary = shell._cmd(
		"Interact",
		{
			"action": "choose_dialogue",
			"session_id": str(session.get("id", "")),
			"choice_id": "ask_clear_rockfall",
			"entity_id": helper,
		}
	)
	if str(choose.get("status", "")) != "ACCEPTED":
		_fail("ask_clear_rockfall rejected: %s" % str(choose))
		return
	shell._cmd("Interact", {"action": "close_dialogue", "session_id": str(session.get("id", ""))})

	# Advance Game Time past move duration (production AdvanceGame path).
	var cleared := false
	for _i in 16:
		var clk_view: Dictionary = shell.probe_economy(["clock", "overworld_area"])
		var seq := int(_dict(clk_view.get("clock")).get("clock_sequence", 0)) + 1
		var adv: Dictionary = shell._cmd("AdvanceGame", {"delta_ms": 500, "clock_sequence": seq})
		if str(adv.get("status", "")) != "ACCEPTED":
			seq = int(_dict(adv.get("payload")).get("clock_sequence", seq)) + 1
			adv = shell._cmd("AdvanceGame", {"delta_ms": 500, "clock_sequence": seq})
		await process_frame
		var area_probe: Dictionary = _coerce_area(shell)
		var rf := _rockfall_entity(area_probe)
		if str(rf.get("status", "")) == "cleared" or not bool(rf.get("blocks_walk", true)):
			cleared = true
			break
	if not cleared:
		_fail("rockfall never reached cleared status after AdvanceGame")
		return

	# Critical: refresh via _apply_world_layers only (industry path), not full rebuild.
	var view: Dictionary = shell.probe_economy([
		"clock", "overworld_area", "player", "industry_workers", "industry_connections", "fx_village"
	])
	var area: Dictionary = _dict(view.get("overworld_area"))
	if area.is_empty():
		area = VillageTestRunner.get_area()
	VillageTestRunner.replace_area(area)
	shell._apply_world_layers(area)
	await process_frame

	for tile_v in corridor:
		var t := Vector2i(int(tile_v[0]), int(tile_v[1]))
		if not ow.is_walkable(t):
			_fail("former corridor tile still blocked after layer sync: %s" % str(t))
			return

	var start := Vector2i(int(ow._john_pos.x), int(ow._john_pos.y))
	var exit_tile := _south_exit_tile(area)
	if exit_tile.x < 0:
		_fail("south exit tile not found")
		return
	if not ow.path_reachable(start, exit_tile):
		var centre := Vector2i(24, 24)
		if not ow.path_reachable(centre, exit_tile):
			_fail("south exit not reachable from village after clear")
			return

	if not shell.travel_to_node("node:35", "node:29"):
		_fail("Travel to node:29 rejected after clear: %s" % shell.last_travel_feedback())
		return
	var landed: Dictionary = shell.probe_economy(["player"])
	if str(_dict(landed.get("player")).get("node_id", "")) != "node:29":
		_fail("did not land on node:29")
		return

	# Return + save/load — road stays open.
	if not shell.travel_to_node("node:29", "node:35"):
		_fail("return Travel to node:35 failed")
		return
	if str(shell.save_slot(SAVE_SLOT).get("status", "")) != "ACCEPTED":
		_fail("save failed")
		return
	if str(shell.load_slot(SAVE_SLOT).get("status", "")) != "ACCEPTED":
		_fail("load failed")
		return
	await process_frame
	ow = shell.overworld()
	area = VillageTestRunner.get_area()
	rock = _rockfall_entity(area)
	if bool(rock.get("blocks_walk", true)):
		_fail("rockfall blocking again after load")
		return
	for tile_v in corridor:
		var t2 := Vector2i(int(tile_v[0]), int(tile_v[1]))
		if not ow.is_walkable(t2):
			_fail("corridor blocked after save/load: %s" % str(t2))
			return
	if not shell.travel_to_node("node:35", "node:29"):
		_fail("Travel after load rejected")
		return

	print("G05_ROCKFALL_WALK_OK helper=%s corridor=%s exit=%s" % [helper, corridor.size(), str(exit_tile)])
	quit(0)


func _coerce_area(shell) -> Dictionary:
	var view: Dictionary = shell.probe_economy(["overworld_area"])
	var area: Dictionary = _dict(view.get("overworld_area"))
	if area.is_empty():
		area = VillageTestRunner.get_area()
	return area


func _rockfall_entity(area: Dictionary) -> Dictionary:
	for raw in area.get("entities", []):
		if typeof(raw) == TYPE_DICTIONARY and str(raw.get("id", "")) == ROCKFALL_ID:
			return raw
	return {}


func _south_exit_tile(area: Dictionary) -> Vector2i:
	for raw in area.get("entities", []):
		if typeof(raw) != TYPE_DICTIONARY:
			continue
		var e: Dictionary = raw
		if str(e.get("kind", "")) != "exit":
			continue
		if str(e.get("to_node", "")) != "node:29":
			continue
		var pos = e.get("pos", e.get("grid", []))
		if typeof(pos) == TYPE_ARRAY and pos.size() >= 2:
			return Vector2i(int(pos[0]), int(pos[1]))
	return Vector2i(-1, -1)


func _first_helper(shell) -> String:
	var candidates := [
		"person:16", "person:17", "person:18", "person:19",
		"person:20", "person:21", "person:22",
	]
	for pid in candidates:
		var talk: Dictionary = shell.talk_to(pid)
		if str(talk.get("status", "")) != "ACCEPTED":
			continue
		var payload: Dictionary = _dict(talk.get("payload"))
		var choices = payload.get("choices", [])
		if typeof(choices) != TYPE_ARRAY:
			choices = []
		var session: Dictionary = _dict(payload.get("session"))
		var found := false
		for c in choices:
			if typeof(c) != TYPE_DICTIONARY:
				continue
			if str(c.get("id", "")) == "ask_clear_rockfall":
				found = true
				break
		if not session.is_empty():
			shell._cmd("Interact", {"action": "close_dialogue", "session_id": str(session.get("id", ""))})
		if found:
			return pid
	return ""
