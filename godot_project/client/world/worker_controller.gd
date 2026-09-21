class_name WorkerController
extends Node2D

## Persistent carriers keyed by Python person IDs.
## Each carrier walks one directed connection: loaded outbound, empty return.
## Obstruction is presentation-only — never sends production commands.
## Uses ActorVisual + existing character sprites at Overworld TILE_SCALE.

signal person_spawned(person_id: String, actor: Node2D, row: Dictionary)
signal person_updated(person_id: String, actor: Node2D, row: Dictionary)
signal person_removed(person_id: String)
## Optional diagnostic for G03 industry shells (no-op unless emitted).
signal layout_diagnostic(person_id: String, message: String)

const ActorVisual = preload("res://client/world/actor_visual.gd")
const PIXEL_ROOT := "res://assets/pixel/"
const TILE := 16
const TILE_SCALE := 4
const TPX := TILE * TILE_SCALE
const WALK_SPEED := 110.0
const STOP_RADIUS := 30.0
## Prefer readable geometric workers in the living-world pass.
const GEOMETRIC_MODE := true

var _workers: Dictionary = {}  # person_id -> Node2D
var _phase: Dictionary = {}  # person_id -> float 0..2 (0-1 outbound, 1-2 return)
var _pause: Dictionary = {}  # person_id -> remaining pause seconds (presentation only)
var _blocked_manual := false
var _wizard_world := Vector2(9999, 9999)
var _frozen := false

const LOAD_PAUSE_SEC := 0.55
const UNLOAD_PAUSE_SEC := 0.45


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
			person_spawned.emit(person_id, worker, row)
		else:
			_sync_meta(worker, row)
			person_updated.emit(person_id, worker, row)
	for person_id in _workers.keys():
		if not present.has(person_id):
			_workers[person_id].queue_free()
			_workers.erase(person_id)
			_phase.erase(person_id)
			_pause.erase(person_id)
			person_removed.emit(str(person_id))


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
			_set_activity(worker, "idle", null, false)
			continue
		if cue == "waiting" or cue == "idle":
			var origin: Vector2 = _grid_to_world(outbound[0].get("grid", [0, 0]))
			worker.position = worker.position.move_toward(origin, WALK_SPEED * delta)
			_set_activity(worker, "waiting", null, false)
			continue

		# Presentation-only pause at endpoints (does not affect throughput).
		var pause_left: float = float(_pause.get(person_id, 0.0))
		if pause_left > 0.0:
			_pause[person_id] = pause_left - delta
			continue

		var phase: float = float(_phase.get(person_id, 0.0))
		var loaded: bool = phase < 1.0
		var leg: Array = outbound if loaded else inbound
		if leg.size() < 2:
			leg = outbound
		var from_pt: Vector2 = _grid_to_world(leg[0].get("grid", [0, 0]))
		var to_pt: Vector2 = _grid_to_world(leg[1].get("grid", [0, 0]))
		# Small deterministic offset so co-routed workers don't stack perfectly.
		var offset := float(hash(str(person_id)) % 7) - 3.0
		from_pt += Vector2(offset, -offset * 0.35)
		to_pt += Vector2(offset, -offset * 0.35)
		var local_t := phase if loaded else (phase - 1.0)
		var target: Vector2 = from_pt.lerp(to_pt, clampf(local_t, 0.0, 1.0))
		if _path_obstructed(from_pt, to_pt, worker.position):
			target = _detour_around(worker.position, target)
		var prev: Vector2 = worker.position
		worker.position = worker.position.move_toward(target, WALK_SPEED * delta)
		_face_sprite(worker, worker.position - prev)
		var step: float = (WALK_SPEED * delta) / maxf(from_pt.distance_to(to_pt), 1.0)
		var prev_phase := phase
		phase += step
		if prev_phase < 1.0 and phase >= 1.0:
			_pause[person_id] = UNLOAD_PAUSE_SEC
		elif prev_phase < 2.0 and phase >= 2.0:
			_pause[person_id] = LOAD_PAUSE_SEC
		if phase >= 2.0:
			phase -= 2.0
		_phase[person_id] = phase
		if loaded:
			_set_activity(worker, "carrying", row.get("resource_label"), true)
		else:
			_set_activity(worker, "returning", null, false)


func worker_for_person(person_id: String) -> Node2D:
	return _workers.get(person_id)


func person_ids() -> Array:
	return _workers.keys()


func report_visual_route_failure(person_id: String, detail: String) -> void:
	var worker: Node2D = _workers.get(person_id)
	if worker != null:
		_set_activity(worker, "waiting", null, false)
	# Diagnostic only — never shown as player UI.


func _ready() -> void:
	y_sort_enabled = true


func _spawn_worker(person_id: String, row: Dictionary) -> Node2D:
	var worker := Node2D.new()
	worker.name = "Person_%s" % person_id.validate_node_name()
	worker.set_meta("person_id", person_id)
	worker.z_index = 8
	add_child(worker)
	var display := _standing_label(row)
	worker.set_meta("label", display)
	if GEOMETRIC_MODE:
		var body := Polygon2D.new()
		body.name = "Body"
		body.polygon = PackedVector2Array([
			Vector2(-10, -22), Vector2(10, -22), Vector2(10, 10), Vector2(-10, 10)
		])
		body.color = Color(0.85, 0.75, 0.45)
		worker.add_child(body)
		var head := Polygon2D.new()
		head.name = "Head"
		head.polygon = PackedVector2Array([
			Vector2(-7, -34), Vector2(7, -34), Vector2(7, -22), Vector2(-7, -22)
		])
		head.color = Color(0.95, 0.85, 0.65)
		worker.add_child(head)
	else:
		var spr := Sprite2D.new()
		spr.name = "Sprite"
		spr.centered = false
		worker.add_child(spr)
		var sprite_key := str(row.get("sprite", row.get("visual_profile", "worker")))
		if sprite_key.is_empty():
			sprite_key = "worker"
		ActorVisual.apply(spr, PIXEL_ROOT, sprite_key, "down", 0, display)
	var waypoints: Array = row.get("waypoints", [])
	if not waypoints.is_empty():
		worker.position = _grid_to_world(waypoints[0].get("grid", [4, 5]))
	else:
		worker.position = Vector2(4, 5) * TPX
	# Stagger phase so workers don't move in lockstep.
	_phase[person_id] = float(hash(person_id) % 100) / 100.0
	_pause[person_id] = float(hash(person_id + ":pause") % 40) / 80.0
	_sync_meta(worker, row)
	return worker


func _standing_label(row: Dictionary) -> String:
	var role := str(row.get("public_occupation", row.get("public_role", row.get("occupation", ""))))
	if role != "" and not role.begins_with("person:") and role.to_lower() != "carrier":
		return role
	var display := str(row.get("name", "Villager"))
	if display.begins_with("person:") or display.begins_with("Carrier"):
		return "Villager"
	return display


func _hold_stationary(worker: Node2D, row: Dictionary) -> void:
	var waypoints: Array = row.get("waypoints", [])
	if waypoints.is_empty():
		return
	var pos: Vector2 = _grid_to_world(waypoints[0].get("grid", [6, 3]))
	# Soft work bob so stationary workers remain visibly active.
	var t := Time.get_ticks_msec() * 0.006 + float(hash(str(worker.get_meta("person_id", ""))) % 20)
	pos += Vector2(0, sin(t) * 3.0)
	worker.position = pos
	_set_activity(worker, str(row.get("activity", "working")), null, false)


func _sync_meta(worker: Node2D, row: Dictionary) -> void:
	worker.set_meta("row", row)
	worker.set_meta("industry_cue", str(row.get("cue", "idle")))
	var display := _standing_label(row)
	worker.set_meta("public_role", display)
	worker.set_meta("label", display)
	if GEOMETRIC_MODE:
		return
	var spr: Sprite2D = worker.get_node_or_null("Sprite")
	if spr != null:
		var sprite_key := str(row.get("sprite", row.get("visual_profile", "worker")))
		if sprite_key.is_empty():
			sprite_key = "worker"
		var facing := str(spr.get_meta("facing", "down"))
		ActorVisual.apply(spr, PIXEL_ROOT, sprite_key, facing, 0, display)


func _face_sprite(worker: Node2D, delta: Vector2) -> void:
	if delta.length() < 0.4:
		return
	if GEOMETRIC_MODE:
		return
	var spr: Sprite2D = worker.get_node_or_null("Sprite")
	if spr == null:
		return
	var facing := "down"
	if absf(delta.x) >= absf(delta.y):
		facing = "right" if delta.x > 0.0 else "left"
	else:
		facing = "down" if delta.y > 0.0 else "up"
	var sprite_key := str(spr.get_meta("sprite", "worker"))
	var label := str(spr.get_meta("label", "Worker"))
	ActorVisual.apply(spr, PIXEL_ROOT, sprite_key, facing, 0, label)


func _set_activity(worker: Node2D, activity: String, carry_resource, loaded: bool) -> void:
	worker.set_meta("industry_cue", activity)
	worker.set_meta("carry_resource", str(carry_resource) if carry_resource != null else "")
	worker.set_meta("loaded", bool(loaded))
	var pip_name := "CarryPip"
	var pip: Polygon2D = worker.get_node_or_null(pip_name)
	var label: Label = worker.get_node_or_null("ActivityLabel")
	if label == null:
		label = Label.new()
		label.name = "ActivityLabel"
		label.position = Vector2(-40, -52)
		label.add_theme_font_size_override("font_size", 11)
		label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		label.custom_minimum_size = Vector2(80, 0)
		label.modulate = Color(1, 1, 1, 0.92)
		worker.add_child(label)
	var occ := str(worker.get_meta("label", "Worker"))
	var act := str(activity)
	if bool(loaded) and carry_resource != null and str(carry_resource) != "":
		label.text = "%s\ncarrying %s" % [occ, str(carry_resource)]
	elif act in ["waiting", "idle"]:
		label.text = "%s\n%s" % [occ, act]
	elif act == "working":
		label.text = "%s\nworking" % occ
	elif act in ["carrying"] or bool(loaded):
		label.text = "%s\ncarrying" % occ
	else:
		label.text = "%s\n%s" % [occ, "returning" if act == "returning" else act]
	# Large resource-tinted pip (presentation only).
	if bool(loaded) and carry_resource != null and str(carry_resource) != "":
		if pip == null:
			pip = Polygon2D.new()
			pip.name = pip_name
			worker.add_child(pip)
		pip.polygon = _resource_pip_shape(str(carry_resource))
		pip.color = _resource_pip_color(str(carry_resource))
		pip.position = Vector2(22, -36)
		pip.z_index = 2
		pip.visible = true
	elif pip != null:
		pip.visible = false


func _resource_pip_color(resource_label: String) -> Color:
	var low := resource_label.to_lower()
	if "berr" in low or "nut" in low:
		return Color(0.75, 0.2, 0.35)
	if "flint" in low or "ore" in low:
		return Color(0.45, 0.48, 0.55)
	if "clay" in low:
		return Color(0.72, 0.45, 0.28)
	if "water" in low or "spring" in low:
		return Color(0.25, 0.55, 0.9)
	if "grain" in low or "food" in low or "forag" in low:
		return Color(0.9, 0.75, 0.2)
	if "wool" in low or "sheep" in low or "goat" in low:
		return Color(0.92, 0.9, 0.82)
	if "infusion" in low or "paste" in low or "processed" in low:
		return Color(0.55, 0.35, 0.75)
	return Color(0.45, 0.75, 0.35)


func _resource_pip_shape(resource_label: String) -> PackedVector2Array:
	var low := resource_label.to_lower()
	var r := 9.0
	if "flint" in low or "ore" in low:
		return PackedVector2Array([Vector2(0, -r), Vector2(r, 0), Vector2(0, r), Vector2(-r, 0)])
	if "clay" in low:
		return PackedVector2Array([
			Vector2(-r, -r), Vector2(r, -r), Vector2(r, r), Vector2(-r, r)
		])
	if "infusion" in low or "paste" in low or "processed" in low:
		var pts := PackedVector2Array()
		for i in 6:
			var a := TAU * float(i) / 6.0 - PI * 0.5
			pts.append(Vector2(cos(a), sin(a)) * r)
		return pts
	# default circle-ish octagon
	var circ := PackedVector2Array()
	for i in 8:
		var a2 := TAU * float(i) / 8.0
		circ.append(Vector2(cos(a2), sin(a2)) * r)
	return circ


func _grid_to_world(grid) -> Vector2:
	var gx := 0.0
	var gy := 0.0
	if typeof(grid) == TYPE_ARRAY:
		gx = float(grid[0])
		gy = float(grid[1])
	elif typeof(grid) == TYPE_PACKED_INT32_ARRAY or typeof(grid) == TYPE_PACKED_FLOAT32_ARRAY:
		gx = float(grid[0])
		gy = float(grid[1])
	# Match Overworld NPC anchoring (top-left of cell at TILE_SCALE).
	return Vector2(gx, gy) * TPX


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


## Draw industry connection ribbons (presentation only).
func draw_connections(connections: Array) -> void:
	var existing := get_node_or_null("ConnectionRibbons")
	if existing != null:
		existing.queue_free()
	var root := Node2D.new()
	root.name = "ConnectionRibbons"
	root.z_index = 1
	add_child(root)
	move_child(root, 0)
	for raw in connections:
		if typeof(raw) != TYPE_DICTIONARY:
			continue
		var row: Dictionary = raw
		var waypoints: Array = row.get("waypoints", [])
		if waypoints.size() < 2:
			continue
		var line := Line2D.new()
		line.width = 3.0
		line.default_color = Color(0.85, 0.7, 0.25, 0.35)
		var pts := PackedVector2Array()
		for wp in waypoints:
			if typeof(wp) != TYPE_DICTIONARY:
				continue
			pts.append(_grid_to_world(wp.get("grid", [0, 0])))
		if pts.size() >= 2:
			line.points = pts
			root.add_child(line)
