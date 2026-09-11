extends SceneTree

## Puzzle movement smoke test: pz_01 through the REAL production Overworld.
## Boots overworld.tscn with a pending PuzzleTestRunner session, steps John
## onto adjacent free floor via ui_step (real _try_step → _arrived → kit
## on-step), walks to the closed gate, and proves the gate cannot be entered.
## No fake movement system; generic production path only.
##
## godot --headless --path godot_project --script res://client/tests/run_puzzle_walk.gd

const _Runner = preload("res://client/scripts/puzzle_test_runner.gd")

var _failures: Array = []
var _world = null
var _adv = null


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	await process_frame
	_ensure_autoloads()
	_adv = root.get_node("Adventure")
	_adv.delete_save()
	await process_frame
	_Runner.set_puzzle("pz_01")
	_world = load("res://client/scenes/overworld.tscn").instantiate()
	_world.test_mode = true
	root.add_child(_world)
	await process_frame
	await process_frame
	assert_true(_Runner.is_active(), "kit session active after production boot")
	assert_eq(_world.john_pos(), Vector2i(6, 9), "John starts at pz_01 start tile")
	await _step(Vector2i(0, -1))
	assert_eq(_world.john_pos(), Vector2i(6, 8), "John steps onto adjacent free floor")
	assert_true(not _world.is_walkable(Vector2i(6, 7)), "loose key tile blocks until taken (kit rule)")
	await _interact()
	assert_true(_adv.has_item("glass_bead"), "facing interaction takes the loose glass bead")
	assert_true(_world.is_walkable(Vector2i(6, 7)), "taken key tile frees up")
	# North up column 6 from (6,8), sidestep the plaque (6,4) via x=5, reach (6,3).
	for d in [Vector2i(0, -1), Vector2i(0, -1), Vector2i(-1, 0), Vector2i(0, -1), Vector2i(0, -1), Vector2i(0, -1), Vector2i(1, 0)]:
		await _step(d)
	assert_eq(_world.john_pos(), Vector2i(6, 3), "John detours round the plaque to the gate")
	await _step(Vector2i(0, -1))
	assert_eq(_world.john_pos(), Vector2i(6, 3), "closed gate cannot be entered")
	assert_true(_world.is_walkable(Vector2i(6, 8)), "free floor walkable via production path")
	assert_true(not _world.is_walkable(Vector2i(6, 2)), "closed gate blocked via production path")
	await _free_world()
	if _Runner.is_active():
		_Runner.end(_adv)
	else:
		_Runner.clear()
	_report()


func _step(dir: Vector2i) -> void:
	_world.ui_step(dir)
	var guard := 0
	while guard < 600 and (_world.ui_is_moving() or _world.ui_input_locked()):
		await process_frame
		guard += 1
	await _drain_dialogue()


func _interact() -> void:
	_world.ui_action()
	var guard := 0
	while guard < 600 and (_world.ui_is_moving() or _world.ui_input_locked()):
		if _world.ui_dialogue_waiting_choice():
			_world.ui_dialogue_choose("Take")
		await process_frame
		guard += 1
	await _drain_dialogue()


func _drain_dialogue(max_lines: int = 40) -> void:
	var warm := 0
	while warm < 120 and not _world.ui_dialogue_open() and not _world.ui_input_locked():
		await process_frame
		warm += 1
	var guard := 0
	while guard < max_lines * 60:
		guard += 1
		await process_frame
		if _world.ui_dialogue_open():
			if _world.ui_dialogue_waiting_choice():
				return
			_world.ui_dialogue_advance()
			await process_frame
		elif not _world.ui_input_locked():
			return


func _free_world() -> void:
	if _world and is_instance_valid(_world):
		_world.queue_free()
		_world = null
	await process_frame


func _ensure_autoloads() -> void:
	for pair in [["EncounterSession", "res://client/scripts/encounter_session.gd"], ["Sfx", "res://client/scripts/sfx.gd"], ["Adventure", "res://client/scripts/adventure.gd"]]:
		if root.get_node_or_null(pair[0]) == null:
			var n = load(pair[1]).new()
			n.name = pair[0]
			root.add_child(n)


func assert_true(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)


func assert_eq(actual, expected, msg: String) -> void:
	if actual != expected:
		_failures.append("%s expected %s got %s" % [msg, str(expected), str(actual)])


func _report() -> void:
	if _failures.is_empty():
		print("PUZZLE WALK: PASS")
	else:
		print("PUZZLE WALK: FAIL")
		for f in _failures:
			print("  - %s" % f)
	quit(1 if not _failures.is_empty() else 0)
