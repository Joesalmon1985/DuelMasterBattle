extends SceneTree

## Headed visual QA for pz_01 The Four Offerings. Run WITHOUT --headless:
##   godot --path godot_project --resolution 1280x720 --script res://client/tools/capture_puzzle_r01.gd
## Plays the room through the REAL production Overworld UI (walk / take / read
## riddle / choose offering), saving initial / partial / solved / through-gate
## shots to qa/screenshots/pz_01/.

const _Runner = preload("res://client/scripts/puzzle_test_runner.gd")

var _out_dir: String
var _world
var _adv

# item tile -> alcove x (alcoves sit on row 4; John stands row 5 facing north)
const PLAN := [
	{"item": "mirror_shard", "at": Vector2i(2, 8), "alcove": 2},
	{"item": "tallow_candle", "at": Vector2i(4, 7), "alcove": 4},
	{"item": "charcoal", "at": Vector2i(8, 7), "alcove": 8},
	{"item": "copper_coin", "at": Vector2i(10, 8), "alcove": 10},
]

const DIRS := [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, -1), Vector2i(0, 1)]


func _init() -> void:
	var root_path := ProjectSettings.globalize_path("res://..")
	_out_dir = root_path + "/qa/screenshots/pz_01"
	DirAccess.make_dir_recursive_absolute(_out_dir)
	call_deferred("_run")


func _run() -> void:
	await process_frame
	_Runner.set_puzzle("pz_01")
	_world = load("res://client/scenes/overworld.tscn").instantiate()
	_world.test_mode = true
	root.add_child(_world)
	await process_frame
	await process_frame
	await process_frame
	_adv = _world._adv()
	_capture("01_initial.png")
	var done := 0
	for step in PLAN:
		await _take(step["at"])
		await _install(step["alcove"])
		done += 1
		if done == 2:
			_capture("02_partial_two_installed.png")
	_capture("03_solved_door_open.png")
	# Walk through the open gate to the goal.
	await _walk_to(Vector2i(6, 3))
	await _step(Vector2i(0, -1))  # (6,2) open gate: John stands in the doorway
	print("SHOT john=", _world.john_pos(), " solved=", _Runner.kit_state().get("solved", false))
	_capture("04_through_gate.png")
	await _step(Vector2i(0, -1))  # (6,1) goal triggers the solved flow
	print("SHOT john=", _world.john_pos(), " solved=", _Runner.kit_state().get("solved", false))
	if _Runner.is_active():
		_Runner.end(_adv)
	else:
		_Runner.clear()
	quit(0)


func _capture(file: String) -> void:
	await process_frame
	await process_frame
	await process_frame
	var img: Image = root.get_viewport().get_texture().get_image()
	img.save_png(_out_dir + "/" + file)
	print("shot ", file)


func _walk_to(target: Vector2i) -> void:
	var guard := 0
	while _world.john_pos() != target and guard < 200:
		guard += 1
		var path := _bfs(_world.john_pos(), target)
		if path.is_empty():
			print("SHOT no path to ", target)
			return
		await _step(path[0])


func _bfs(from: Vector2i, to: Vector2i) -> Array:
	var prev := {from: Vector2i(-999, -999)}
	var queue := [from]
	while not queue.is_empty():
		var cur: Vector2i = queue.pop_front()
		if cur == to:
			break
		for d in DIRS:
			var nxt: Vector2i = cur + d
			if nxt.x < 0 or nxt.y < 0 or nxt.x > 12 or nxt.y > 9:
				continue
			if prev.has(nxt):
				continue
			if nxt != to and not _world.is_walkable(nxt):
				continue
			prev[nxt] = cur
			queue.append(nxt)
	if not prev.has(to):
		return []
	var rev := []
	var cur := to
	while cur != from:
		rev.push_front(cur - prev[cur])
		cur = prev[cur]
	return rev


func _step(dir: Vector2i) -> void:
	_world.ui_step(dir)
	await _settle()


func _settle() -> void:
	var guard := 0
	while guard < 600 and (_world.ui_is_moving() or _world.ui_input_locked()):
		if _world.ui_dialogue_waiting_choice():
			return
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


func _face(stand: Vector2i, face: Vector2i) -> void:
	# Arrive from stand-face so the last step leaves John facing the target.
	await _walk_to(stand - face)
	await _step(face)


func _take(at: Vector2i) -> void:
	for f in DIRS:
		var stand: Vector2i = at + f
		var src: Vector2i = at + f * 2
		if _in_bounds(stand) and _in_bounds(src) and _world.is_walkable(stand) and _world.is_walkable(src):
			await _face(stand, -f)
			break
	_world.ui_action()
	var guard := 0
	while guard < 600 and (_world.ui_is_moving() or _world.ui_input_locked()):
		if _world.ui_dialogue_waiting_choice():
			_world.ui_dialogue_choose("Take")
		elif _world.ui_dialogue_open():
			_world.ui_dialogue_advance()
		await process_frame
		guard += 1
	await _drain_dialogue()
	print("DBG take ", at, " john=", _world.john_pos(), " inv=", _adv.items())


func _install(alcove_x: int) -> void:
	await _face(Vector2i(alcove_x, 5), Vector2i(0, -1))
	_world.ui_action()
	var guard := 0
	while guard < 900 and (_world.ui_is_moving() or _world.ui_input_locked()):
		if _world.ui_dialogue_waiting_choice():
			_world.ui_dialogue_choose_index(0)  # Place X (Leave is last)
		elif _world.ui_dialogue_open():
			_world.ui_dialogue_advance()  # tap through the riddle first
		await process_frame
		guard += 1
	await _drain_dialogue()
	print("DBG install x=", alcove_x, " john=", _world.john_pos(), " rec=", _Runner.kit_state().get("rec", {}), " inv=", _adv.items())


func _in_bounds(t: Vector2i) -> bool:
	return t.x >= 0 and t.y >= 0 and t.x <= 12 and t.y <= 9
