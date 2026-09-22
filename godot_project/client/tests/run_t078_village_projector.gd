extends SceneTree

## T078 village projector binds projection views by entity ID.
## godot --headless --path godot_project --script res://client/tests/run_t078_village_projector.gd

const Projector = preload("res://client/world/village_projector.gd")

var _failures: Array = []


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	await process_frame
	var projector = Projector.new()
	var view := {
		"node_id": "node:v",
		"width": 48,
		"height": 48,
		"buildings": [{"id": "building:1", "grid": [10, 12]}],
		"people": [{"id": "person:1", "grid": [10, 16]}],
		"carts": [],
		"units": [],
		"exits_reachable": ["exit.north", "exit.south"],
		"destroyed_ids": [],
	}
	projector.apply_projection(view)
	_assert(projector.has_actor("building:1"), "building actor missing")
	_assert(projector.has_actor("person:1"), "person actor missing")
	_assert(projector.actor_grid("person:1") == [10, 16], "person grid mismatch")
	_assert(projector.world_position("building:1") == Vector2(640, 768), "world pos mismatch")
	_assert(projector.area_size() == Vector2i(48, 48), "area size mismatch")

	# Destroyed entities stay absent on re-apply.
	var view2 := view.duplicate(true)
	view2["people"] = []
	view2["destroyed_ids"] = ["person:1"]
	projector.apply_projection(view2)
	_assert(not projector.has_actor("person:1"), "destroyed person must stay absent")
	_assert(projector.has_actor("building:1"), "building must remain")
	_assert(projector.destroyed_ids().has("person:1"), "destroyed_ids exposed")

	# Re-entry with same IDs does not invent extras.
	projector.apply_projection(view2)
	_assert(projector.actor_ids() == ["building:1"], "unexpected actors %s" % str(projector.actor_ids()))

	if _failures.is_empty():
		print("T078_VILLAGE_PROJECTOR_OK")
		quit(0)
	else:
		for f in _failures:
			push_error(str(f))
		print("T078_VILLAGE_PROJECTOR_FAIL count=", _failures.size())
		quit(1)


func _assert(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)
