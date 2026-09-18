class_name WorkerController
extends Node2D

## Disposable worker presentation keyed by persistent Python person IDs.
## Navigation / obstruction are presentation-only — never send production commands.

signal layout_diagnostic(person_id: String, message: String)

const TILE := 64.0
const WALK_SPEED := 72.0
const STOP_RADIUS := 28.0

var _workers: Dictionary = {}  # person_id -> Node2D
var _phase: Dictionary = {}  # person_id -> float progress along route 0..n
var _blocked_manual := false
var _wizard_world := Vector2(9999, 9999)
var _frozen := false


func set_frozen(frozen: bool) -> void:
	_frozen = frozen


func set_manual_path_block(blocked: bool) -> void:
	_blocked_manual = blocked


func set_wizard_world_position(pos: Vector2) -> void:
	_wizard_world = pos


func apply_projection(rows: Array) -> void:
	var present: Dictionary = {}
	for row_variant in rows:
		var row: Dictionary = row_variant
		var person_id := str(row.get("person_id", ""))
		if person_id.is_empty():
			continue
		present[person_id] = true
		var worker: Node2D = _workers.get(person_id)
		if worker == null:
			worker = _spawn_worker(person_id, row)
			_workers[person_id] = worker
			_phase[person_id] = 0.0
		_sync_meta(worker, row)
	for person_id in _workers.keys():
		if not present.has(person_id):
			_workers[person_id].queue_free()
			_workers.erase(person_id)
			_phase.erase(person_id)


func tick(delta: float) -> void:
	if _frozen:
		return
	for person_id in _workers.keys():
		var worker: Node2D = _workers[person_id]
		var row: Dictionary = worker.get_meta("row", {})
		var waypoints: Array = row.get("waypoints", [])
		if waypoints.is_empty():
			continue
		var cue := str(row.get("activity", row.get("cue", "idle")))
		if cue == "on_strike":
			_set_activity(worker, "on strike", null)
			continue
		if cue == "waiting" or cue == "idle":
			_set_activity(worker, "waiting", null)
			continue

		var n: int = waypoints.size()
		var phase: float = float(_phase.get(person_id, 0.0))
		var idx: int = int(floor(phase)) % n
		var next_idx: int = (idx + 1) % n
		var from_pt: Vector2 = _grid_to_world(waypoints[idx].get("grid", [0, 0]))
		var to_pt: Vector2 = _grid_to_world(waypoints[next_idx].get("grid", [0, 0]))
		var seg_len: float = maxf(from_pt.distance_to(to_pt), 1.0)
		var local_t: float = phase - float(idx)
		var target: Vector2 = from_pt.lerp(to_pt, clampf(local_t, 0.0, 1.0))

		var obstructed: bool = _blocked_manual or _segment_obstructed(from_pt, to_pt, worker.position)
		if obstructed:
			var detour: Vector2 = _detour_around(worker.position, to_pt)
			worker.position = worker.position.move_toward(detour, WALK_SPEED * delta * 0.55)
			_set_activity(worker, "blocked", row.get("carry_resource"))
			continue

		var step: float = WALK_SPEED * delta / seg_len
		phase = fmod(phase + step, float(n))
		_phase[person_id] = phase
		worker.position = worker.position.move_toward(target, WALK_SPEED * delta)

		var kind: String = str(waypoints[idx].get("kind", ""))
		var activity: String = "carrying"
		if kind == "source":
			activity = "collecting" if local_t < 0.35 else "carrying"
		elif kind == "processor":
			activity = "working" if local_t < 0.55 else "carrying"
		elif kind == "factory":
			activity = "working" if local_t < 0.4 else "carrying"
		if cue == "carrying":
			activity = "carrying"
		_set_activity(worker, activity, row.get("carry_resource"))


func worker_for_person(person_id: String) -> Node2D:
	return _workers.get(person_id)


func report_visual_route_failure(person_id: String, detail: String) -> void:
	var worker: Node2D = _workers.get(person_id)
	if worker != null:
		_set_activity(worker, "waiting", null)
	layout_diagnostic.emit(person_id, "worker_layout_route_failed:%s" % detail)


func _spawn_worker(person_id: String, row: Dictionary) -> Node2D:
	var worker := Node2D.new()
	worker.name = "Worker_%s" % person_id.validate_node_name()
	worker.set_meta("person_id", person_id)
	add_child(worker)
	var body := Polygon2D.new()
	body.name = "Body"
	body.polygon = PackedVector2Array([
		Vector2(-12, -18), Vector2(12, -18), Vector2(15, 16), Vector2(-15, 16)
	])
	body.color = Color(0.95, 0.62, 0.18)
	worker.add_child(body)
	var tag := Label.new()
	tag.name = "Tag"
	tag.position = Vector2(-40, -58)
	tag.add_theme_font_size_override("font_size", 12)
	worker.add_child(tag)
	var carry := ColorRect.new()
	carry.name = "Carry"
	carry.size = Vector2(14, 14)
	carry.position = Vector2(14, -10)
	carry.color = Color(0.85, 0.75, 0.2)
	carry.visible = false
	worker.add_child(carry)
	var waypoints: Array = row.get("waypoints", [])
	if not waypoints.is_empty():
		worker.position = _grid_to_world(waypoints[0].get("grid", [4, 5]))
	else:
		worker.position = Vector2(4.0 * TILE + 32.0, 5.0 * TILE + 32.0)
	_sync_meta(worker, row)
	return worker


func _sync_meta(worker: Node2D, row: Dictionary) -> void:
	worker.set_meta("row", row)
	worker.set_meta("industry_cue", str(row.get("cue", "idle")))
	var tag: Label = worker.get_node_or_null("Tag")
	if tag:
		var name := str(row.get("name", row.get("person_id", "Worker")))
		var job := str(row.get("job_id", "job"))
		tag.text = "%s\n%s" % [name, job]


func _set_activity(worker: Node2D, activity: String, carry_resource) -> void:
	worker.set_meta("industry_cue", activity)
	var tag: Label = worker.get_node_or_null("Tag")
	if tag:
		var row: Dictionary = worker.get_meta("row", {})
		var name := str(row.get("name", "Worker"))
		tag.text = "%s\n%s" % [name, activity]
	var carry: ColorRect = worker.get_node_or_null("Carry")
	if carry:
		var show := activity in ["carrying", "collecting"] and carry_resource != null
		carry.visible = show
		if show:
			carry.tooltip_text = str(carry_resource)


func _grid_to_world(grid) -> Vector2:
	var gx := 0.0
	var gy := 0.0
	if typeof(grid) == TYPE_ARRAY:
		gx = float(grid[0])
		gy = float(grid[1])
	elif typeof(grid) == TYPE_PACKED_INT32_ARRAY or typeof(grid) == TYPE_PACKED_FLOAT32_ARRAY:
		gx = float(grid[0])
		gy = float(grid[1])
	return Vector2(gx * TILE + TILE * 0.5, gy * TILE + TILE * 0.5)


func _segment_obstructed(from_pt: Vector2, to_pt: Vector2, worker_pos: Vector2) -> bool:
	# Wizard near the worker or near the upcoming segment blocks visual progress.
	if _wizard_world.distance_to(worker_pos) <= STOP_RADIUS:
		return true
	var closest := _closest_point_on_segment(_wizard_world, from_pt, to_pt)
	return _wizard_world.distance_to(closest) <= STOP_RADIUS


func _closest_point_on_segment(point: Vector2, a: Vector2, b: Vector2) -> Vector2:
	var ab := b - a
	var len_sq := ab.length_squared()
	if len_sq <= 0.001:
		return a
	var t := clampf(((point - a).dot(ab)) / len_sq, 0.0, 1.0)
	return a + ab * t


func _detour_around(from_pos: Vector2, goal: Vector2) -> Vector2:
	var away := from_pos - _wizard_world
	if away.length() < 1.0:
		away = Vector2(0, -1)
	var side := away.normalized().rotated(PI * 0.5) * 40.0
	# Prefer the side that still advances toward the goal.
	var option_a := from_pos + side
	var option_b := from_pos - side
	if option_a.distance_to(goal) <= option_b.distance_to(goal):
		return option_a
	return option_b
