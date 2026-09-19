extends SceneTree

## T089 puzzle presenter smoke.
## godot --headless --path godot_project --script res://client/tests/run_t089_puzzle.gd

const Puzzle = preload("res://client/adventure/puzzle.gd")

var _failures: Array = []
var _pose_calls: Array = []
var _action_calls: Array = []


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	await process_frame
	var ui = Puzzle.new()
	ui.pose_sync_requested.connect(
		func(lid, ver, actor, pos): _pose_calls.append([lid, ver, actor, pos])
	)
	ui.action_requested.connect(
		func(lid, ver, mid, action, item): _action_calls.append([lid, ver, mid, action, item])
	)
	ui.apply_lease({
		"lease_id": "lease:1",
		"version": 3,
		"puzzle_id": "puzzle.t089_sample",
		"checkpoint": {
			"solved": false,
			"finish_applied": false,
			"mechanisms": {
				"box.1": {"id": "box.1", "kind": "movable_box", "position": [0.0, 0.0]},
				"plate.1": {"id": "plate.1", "kind": "pressure_plate", "active": false},
			},
			"local_actors": {},
		},
	})
	_assert(ui.lease_id == "lease:1", "lease id")
	_assert(ui.expected_version == 3, "version")
	_assert(ui.box_position("box.1") == Vector2(0, 0), "box pos")
	ui.push_box("box.1", Vector2(2, 0))
	_assert(ui.box_position("box.1") == Vector2(2, 0), "box moved")
	_assert(_pose_calls.size() == 1, "pose signal")
	ui.request_action("receptor.handle", "place", "item:1")
	_assert(_action_calls.size() == 1, "action signal")
	_assert(_action_calls[0][3] == "place", "action kind")
	if _failures.is_empty():
		print("T089_PUZZLE_OK")
		ui.free()
		quit(0)
	else:
		for f in _failures:
			push_error(str(f))
		print("T089_PUZZLE_FAIL")
		ui.free()
		quit(1)


func _assert(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)
