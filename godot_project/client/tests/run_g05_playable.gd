extends SceneTree

## G05 playable — full Prehistoric board start settlement + exits.
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
	OS.set_environment("DMB_SEED", "507")
	var shell = Shell.new()
	root.add_child(shell)
	var deadline := Time.get_ticks_msec() + 25000
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
	var area: Dictionary = VillageTestRunner.get_area()
	if area.is_empty() or str(area.get("id", "")) == "":
		_fail("area empty")
		return
	var rows: Array = area.get("rows", [])
	if rows.is_empty():
		_fail("no terrain rows")
		return
	if int(area.get("width", 0)) != 48 or rows.size() != 48:
		_fail("local area not standard 48×48")
		return
	# Settlement content: at least one building door/sign + one person or exit.
	var buildings := 0
	var people := 0
	var exits := 0
	var talk_id := ""
	for raw in area.get("entities", []):
		if typeof(raw) != TYPE_DICTIONARY:
			continue
		var e: Dictionary = raw
		var kind := str(e.get("kind", ""))
		if kind in ["door", "sign"] and str(e.get("building", "")) != "":
			buildings += 1
		if kind == "npc" and bool(e.get("bridge_talk", false)):
			people += 1
			if talk_id == "":
				talk_id = str(e.get("id", ""))
		if kind == "exit" and bool(e.get("bridge_travel", false)):
			exits += 1
	if buildings < 1:
		_fail("no settlement buildings in area")
		return
	if exits < 1:
		_fail("no travel exits in area")
		return
	if talk_id != "":
		var talk: Dictionary = shell.talk_to(talk_id)
		if str(talk.get("status", "")) != "ACCEPTED":
			_fail("talk rejected: %s" % str(talk))
			return
	# Reproject preserves size/node.
	var node_id := str(area.get("node_id", ""))
	shell.reproject_from_python()
	await process_frame
	await process_frame
	var area2: Dictionary = VillageTestRunner.get_area()
	if int(area2.get("width", 0)) != 48:
		_fail("reproject lost standard size")
		return
	if node_id != "" and str(area2.get("node_id", "")) != node_id:
		_fail("reproject changed node")
		return
	# No quest landmarks in baseline.
	if not _entity(area2, "cube:demon").is_empty():
		_fail("demon should not appear in baseline world")
		return
	if not _entity(area2, "entrance:sluice").is_empty():
		_fail("sluice should not appear in baseline world")
		return
	print("G05_PLAYABLE_OK node=%s buildings=%s exits=%s people=%s" % [node_id, buildings, exits, people])
	quit(0)


func _entity(area: Dictionary, eid: String) -> Dictionary:
	for raw in area.get("entities", []):
		if typeof(raw) == TYPE_DICTIONARY and str(raw.get("id", "")) == eid:
			return raw
	return {}
