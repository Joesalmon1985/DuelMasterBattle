class_name WorkerController
extends Node2D

## Persistent carriers keyed by Python person IDs.
## Each carrier walks one directed connection: loaded outbound, empty return.
## Obstruction is presentation-only — never sends production commands.

signal layout_diagnostic(person_id: String, message: String)

const TILE := 64.0
const WALK_SPEED := 78.0
const STOP_RADIUS := 30.0

var _workers: Dictionary = {}  # person_id -> Node2D
var _phase: Dictionary = {}  # person_id -> float 0..2 (0-1 outbound, 1-2 return)
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
			_phase[person_id] = float(hash(person_id) % 100) / 100.0
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
		if bool(row.get("stationary", false)):
			_hold_stationary(worker, row)
			continue
		var outbound: Array = row.get("waypoints", [])
		var inbound: Array = row.get("return_waypoints", [])
		if outbound.size() < 2:
			continue
		var cue := str(row.get("activity", row.get("cue", "idle")))
		if cue == "on_strike":
			_set_activity(worker, "on strike", null, false)
			continue
		if cue == "waiting" or cue == "idle":
			# Park at the origin of their connection.
			var origin: Vector2 = _grid_to_world(outbound[0].get("grid", [0, 0]))
			worker.position = worker.position.move_toward(origin, WALK_SPEED * delta)
			_set_activity(worker, "waiting", null, false)
			continue

		var phase: float = float(_phase.get(person_id, 0.0))
		var loaded: bool = phase < 1.0
		var leg: Array = outbound if loaded else inbound
		if leg.size() < 2:
			leg = outbound
			loaded = true
		var from_pt: Vector2 = _grid_to_world(leg[0].get("grid", [0, 0]))
		var to_pt: Vector2 = _grid_to_world(leg[1].get("grid", [0, 0]))
		var seg_len: float = maxf(from_pt.distance_to(to_pt), 1.0)
		var local_t: float = phase if loaded else (phase - 1.0)
		var target: Vector2 = from_pt.lerp(to_pt, clampf(local_t, 0.0, 1.0))

		var obstructed: bool = _path_obstructed(from_pt, to_pt, worker.position)
		if obstructed:
			var detour: Vector2 = _detour_around(worker.position, to_pt)
			worker.position = worker.position.move_toward(detour, WALK_SPEED * delta * 0.55)
			_set_activity(worker, "blocked", row.get("resource_label") if loaded else null, loaded)
			continue

		var step: float = WALK_SPEED * delta / seg_len
		phase = fmod(phase + step, 2.0)
		_phase[person_id] = phase
		worker.position = worker.position.move_toward(target, WALK_SPEED * delta)
		if loaded:
			_set_activity(worker, "carrying", row.get("resource_label"), true)
		else:
			_set_activity(worker, "returning empty", null, false)


func worker_for_person(person_id: String) -> Node2D:
	return _workers.get(person_id)


func report_visual_route_failure(person_id: String, detail: String) -> void:
	var worker: Node2D = _workers.get(person_id)
	if worker != null:
		_set_activity(worker, "waiting", null, false)
	layout_diagnostic.emit(person_id, "worker_layout_route_failed:%s" % detail)


func _spawn_worker(person_id: String, row: Dictionary) -> Node2D:
	var worker := Node2D.new()
	worker.name = "Carrier_%s" % person_id.validate_node_name()
	worker.set_meta("person_id", person_id)
	add_child(worker)
	var body := Polygon2D.new()
	body.name = "Body"
	body.polygon = PackedVector2Array([
		Vector2(-11, -16), Vector2(11, -16), Vector2(14, 14), Vector2(-14, 14)
	])
	body.color = Color(0.95, 0.62, 0.18)
	worker.add_child(body)
	var tag := Label.new()
	tag.name = "Tag"
	tag.position = Vector2(-46, -52)
	tag.add_theme_font_size_override("font_size", 11)
	worker.add_child(tag)
	var carry := Polygon2D.new()
	carry.name = "Carry"
	carry.polygon = PackedVector2Array([
		Vector2(12, -12), Vector2(26, -12), Vector2(26, 2), Vector2(12, 2)
	])
	carry.color = Color(0.85, 0.75, 0.2)
	carry.visible = false
	worker.add_child(carry)
	var mark := Label.new()
	mark.name = "Mark"
	mark.position = Vector2(13, -14)
	mark.add_theme_font_size_override("font_size", 11)
	mark.text = "?"
	worker.add_child(mark)
	var waypoints: Array = row.get("waypoints", [])
	if not waypoints.is_empty():
		worker.position = _grid_to_world(waypoints[0].get("grid", [4, 5]))
	else:
		worker.position = Vector2(4.0 * TILE + 32.0, 5.0 * TILE + 32.0)
	_sync_meta(worker, row)
	return worker


func _hold_stationary(worker: Node2D, row: Dictionary) -> void:
	var waypoints: Array = row.get("waypoints", [])
	if waypoints.is_empty():
		return
	var pos: Vector2 = _grid_to_world(waypoints[0].get("grid", [6, 3]))
	worker.position = pos
	_set_activity(worker, str(row.get("activity", "working")), null, false)


func _sync_meta(worker: Node2D, row: Dictionary) -> void:
	worker.set_meta("row", row)
	worker.set_meta("industry_cue", str(row.get("cue", "idle")))
	var marker: Dictionary = row.get("marker", {})
	var mark: Label = worker.get_node_or_null("Mark")
	if mark:
		mark.text = str(marker.get("symbol", "?"))


func _set_activity(worker: Node2D, activity: String, carry_resource, loaded: bool) -> void:
	worker.set_meta("industry_cue", activity)
	var row: Dictionary = worker.get_meta("row", {})
	var tag: Label = worker.get_node_or_null("Tag")
	if tag:
		var name := str(row.get("name", "Carrier"))
		var resource := str(carry_resource) if carry_resource != null else ""
		if loaded and resource != "":
			tag.text = "%s\n%s [%s]" % [name, activity, resource]
		else:
			tag.text = "%s\n%s" % [name, activity]
	var carry: Polygon2D = worker.get_node_or_null("Carry")
	var mark: Label = worker.get_node_or_null("Mark")
	if carry:
		carry.visible = true
		if loaded:
			carry.color = Color(0.9, 0.78, 0.2)
		else:
			carry.color = Color(0.55, 0.55, 0.58)
	if mark:
		if loaded:
			var marker: Dictionary = row.get("marker", {})
			mark.text = str(marker.get("symbol", "?"))
			mark.modulate = Color(1, 1, 1, 1)
		else:
			mark.text = "∅"
			mark.modulate = Color(0.75, 0.75, 0.8, 1)


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


func _path_obstructed(from_pt: Vector2, to_pt: Vector2, worker_pos: Vector2) -> bool:
	if _blocked_manual:
		return true
	if _wizard_world.distance_to(worker_pos) <= STOP_RADIUS:
		return true
	var closest: Vector2 = _closest_point_on_segment(_wizard_world, from_pt, to_pt)
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
	var side := away.normalized().rotated(PI * 0.5) * 42.0
	var option_a := from_pos + side
	var option_b := from_pos - side
	if option_a.distance_to(goal) <= option_b.distance_to(goal):
		return option_a
	return option_b
