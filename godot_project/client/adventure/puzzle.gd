extends RefCounted
class_name DmbPuzzlePresenter

## Client puzzle controller (C10 / T089).
## Executes the whitelisted mechanism graph under an ACTIVE Python lease.
## Inventory mutations and finish effects remain Python-owned — this presenter
## only tracks local poses, drafts actions, and submits versioned commands.

signal pose_sync_requested(lease_id: String, expected_version: int, actor_id: String, position: Vector2)
signal action_requested(lease_id: String, expected_version: int, mechanism_id: String, action: String, item_id: String)
signal finish_requested(lease_id: String, expected_version: int)

var lease_id: String = ""
var expected_version: int = 0
var puzzle_id: String = ""
var mechanisms: Dictionary = {}
var local_actors: Dictionary = {}
var solved: bool = false
var finish_applied: bool = false


func apply_lease(lease: Dictionary) -> void:
	lease_id = str(lease.get("lease_id", lease.get("id", "")))
	expected_version = int(lease.get("version", 0))
	puzzle_id = str(lease.get("puzzle_id", ""))
	var checkpoint: Dictionary = lease.get("checkpoint", {})
	mechanisms = (checkpoint.get("mechanisms", {}) as Dictionary).duplicate(true)
	local_actors = (checkpoint.get("local_actors", {}) as Dictionary).duplicate(true)
	solved = bool(checkpoint.get("solved", false))
	finish_applied = bool(checkpoint.get("finish_applied", false))


func mechanism_active(mechanism_id: String) -> bool:
	var mech: Dictionary = mechanisms.get(mechanism_id, {})
	return bool(mech.get("active", false)) or bool(mech.get("open", false)) or bool(mech.get("on", false))


func box_position(box_id: String) -> Vector2:
	var mech: Dictionary = mechanisms.get(box_id, {})
	var pos = mech.get("position", [0.0, 0.0])
	if typeof(pos) == TYPE_ARRAY and pos.size() >= 2:
		return Vector2(float(pos[0]), float(pos[1]))
	return Vector2.ZERO


func push_box(box_id: String, to: Vector2) -> void:
	## Local presentation update; authority follows after Python sync_local_pose.
	if not mechanisms.has(box_id):
		return
	var mech: Dictionary = mechanisms[box_id]
	mech["position"] = [to.x, to.y]
	mechanisms[box_id] = mech
	local_actors[box_id] = {"id": box_id, "kind": "movable_box", "position": [to.x, to.y]}
	pose_sync_requested.emit(lease_id, expected_version, box_id, to)


func request_action(mechanism_id: String, action: String, item_id: String = "") -> void:
	action_requested.emit(lease_id, expected_version, mechanism_id, action, item_id)


func request_finish() -> void:
	if solved and not finish_applied:
		finish_requested.emit(lease_id, expected_version)


func apply_server_result(result: Dictionary) -> void:
	var lease: Dictionary = result.get("lease", {})
	if not lease.is_empty():
		apply_lease(lease)
