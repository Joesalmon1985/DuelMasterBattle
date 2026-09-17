extends RefCounted
class_name DmbLocalMovementPresenter

## Reusable Game-Time local mover for presentation-only journeys.
## Does not mutate cargo, credit stock, or advance World Turns.
## Paths use area walkability; strategic crossings remain Python-authoritative.

const TILE := 64.0
const DEFAULT_SPEED_PX := 96.0
const MAX_QUEUE := 3

signal journey_phase_changed(actor_id: String, phase: String)
signal journey_progress(actor_id: String, progress_ms: int, local_pos: Vector2)
signal needs_sync(actor_id: String, payload: Dictionary)

var _area  # DmbFxClockArea
var _client = null
var _paused := false
var _tracks: Dictionary = {}  # actor_id -> track dict
var _sync_acc_ms := 0.0


func bind(area, world_client) -> void:
	_area = area
	_client = world_client


func set_paused(on: bool) -> void:
	_paused = on


func clear() -> void:
	_tracks.clear()


func ingest_view(view: Dictionary) -> void:
	var presentation: Dictionary = view.get("presentation", {})
	var journeys: Dictionary = presentation.get("journeys", {})
	var pending_all: Dictionary = presentation.get("pending_transitions", {})
	for actor_id in journeys.keys():
		var journey: Dictionary = journeys[actor_id]
		_ensure_track(str(actor_id), journey, pending_all.get(actor_id, []))
	# Drop tracks for actors no longer present.
	var drop: Array = []
	for actor_id in _tracks.keys():
		if not journeys.has(actor_id):
			drop.append(actor_id)
	for actor_id in drop:
		_tracks.erase(actor_id)
	# If the local camera is already on an arrival node with a pending edge,
	# skip leftover departure and play the entrance here (follow-immediately).
	if _area != null:
		var here := str(_area.current_node)
		for actor_id in _tracks.keys():
			var track: Dictionary = _tracks[actor_id]
			var phase := str(track.get("phase", ""))
			var pending: Array = track.get("pending", [])
			if pending.is_empty() and track.has("pending_arrival"):
				pending = [track["pending_arrival"]]
				track["pending"] = pending
				track.erase("pending_arrival")
			if pending.is_empty():
				continue
			var nxt: Dictionary = pending[0]
			if str(nxt.get("to_node", "")) != here:
				continue
			if phase in ["to_exit", "waiting_exit", "departing"]:
				_start_entrance_from_pending(track)


func _ensure_track(actor_id: String, journey: Dictionary, pending) -> void:
	var jid := str(journey.get("journey_id", ""))
	var track: Dictionary = _tracks.get(actor_id, {})
	var pending_list: Array = []
	if typeof(pending) == TYPE_ARRAY:
		pending_list = pending.duplicate(true)
	if track.is_empty() or str(track.get("journey_id", "")) != jid:
		track = {
			"journey_id": jid,
			"actor_id": actor_id,
			"phase": str(journey.get("phase", "idle")),
			"from_node": str(journey.get("from_node", "")),
			"to_node": str(journey.get("to_node", "")),
			"local_from": _vec(journey.get("local_from"), Vector2(6, 5)),
			"local_to": _vec(journey.get("local_to"), Vector2(12, 5)),
			"local_pos": _vec(journey.get("local_pos"), _vec(journey.get("local_from"), Vector2(6, 5))),
			"progress_ms": int(journey.get("progress_ms", 0)),
			"duration_ms": maxi(int(journey.get("duration_ms", 2500)), 400),
			"authorized_cross": bool(journey.get("authorized_cross", false)),
			"path": [],
			"path_i": 0,
			"segment_t": 0.0,
			"pending": pending_list,
			"playing_pending": false,
		}
		# Resume mid-leg: reconstruct path from local_pos → local_to.
		track["path"] = _build_path(track["local_pos"], track["local_to"])
		_tracks[actor_id] = track
		return
	# Same journey: absorb authorization / pending without resetting motion.
	track["authorized_cross"] = bool(journey.get("authorized_cross", track.get("authorized_cross", false)))
	if journey.has("pending_arrival") and typeof(journey.get("pending_arrival")) == TYPE_DICTIONARY:
		track["pending_arrival"] = journey["pending_arrival"]
	if pending_list.size() > 0:
		track["pending"] = _merge_pending(track.get("pending", []), pending_list)
	# Adopt phase upgrades from authority when not mid-segment conflict.
	var auth_phase := str(journey.get("phase", ""))
	if auth_phase == "blocked":
		track["phase"] = "blocked"
		track["local_to"] = _vec(journey.get("local_to"), track["local_to"])
		track["path"] = _build_path(track["local_pos"], track["local_to"])
		track["path_i"] = 0
		track["segment_t"] = 0.0
	elif auth_phase in ["entering", "to_waypoint", "to_delivery", "unloading"] and not track.get("playing_pending", false):
		if str(track.get("phase")) in ["to_exit", "waiting_exit", "departing"] and track.get("authorized_cross", false):
			# Finish departure visually then apply pending entrance (unless camera already moved).
			pass
		elif str(track.get("phase")) != auth_phase:
			_adopt_leg(track, journey)
	_tracks[actor_id] = track


func _merge_pending(existing: Array, incoming: Array) -> Array:
	var out: Array = existing.duplicate(true)
	var seen: Dictionary = {}
	for item in out:
		seen[_edge_key(item)] = true
	for item in incoming:
		var key := _edge_key(item)
		if seen.has(key):
			continue
		seen[key] = true
		out.append(item)
	while out.size() > MAX_QUEUE:
		out.pop_front()
	return out


func _edge_key(item: Dictionary) -> String:
	return "%s|%s|%s" % [str(item.get("kind")), str(item.get("committed_edge")), str(item.get("sequence"))]


func _adopt_leg(track: Dictionary, journey: Dictionary) -> void:
	track["phase"] = str(journey.get("phase", track.get("phase")))
	track["from_node"] = str(journey.get("from_node", track.get("from_node")))
	track["to_node"] = str(journey.get("to_node", track.get("to_node")))
	track["local_from"] = _vec(journey.get("local_from"), track["local_pos"])
	track["local_to"] = _vec(journey.get("local_to"), track["local_to"])
	track["local_pos"] = _vec(journey.get("local_pos"), track["local_from"])
	track["progress_ms"] = int(journey.get("progress_ms", 0))
	track["duration_ms"] = maxi(int(journey.get("duration_ms", 2500)), 400)
	track["path"] = _build_path(track["local_pos"], track["local_to"])
	track["path_i"] = 0
	track["segment_t"] = 0.0


func tick(delta_sec: float) -> void:
	if _paused or _area == null or delta_sec <= 0.0:
		return
	_sync_acc_ms += delta_sec * 1000.0
	for actor_id in _tracks.keys():
		_tick_actor(str(actor_id), delta_sec)
	if _sync_acc_ms >= 200.0:
		_sync_acc_ms = 0.0
		_flush_syncs()


func _tick_actor(actor_id: String, delta_sec: float) -> void:
	var track: Dictionary = _tracks[actor_id]
	var phase := str(track.get("phase", "idle"))
	if phase in ["idle", "waiting_exit", "unloading"]:
		if phase == "waiting_exit" and track.get("authorized_cross", false):
			_begin_depart_then_enter(track)
		elif phase == "unloading":
			track["progress_ms"] = int(track.get("progress_ms", 0)) + int(delta_sec * 1000.0)
			if int(track["progress_ms"]) >= int(track.get("duration_ms", 1200)):
				track["phase"] = "idle"
				journey_phase_changed.emit(actor_id, "idle")
		_apply_sprite(actor_id, track)
		return
	if phase == "blocked":
		_advance_along_path(track, delta_sec)
		_apply_sprite(actor_id, track)
		return

	var finished := _advance_along_path(track, delta_sec)
	_apply_sprite(actor_id, track)
	if not finished:
		return

	if phase == "to_exit":
		if track.get("authorized_cross", false):
			_begin_depart_then_enter(track)
		else:
			track["phase"] = "waiting_exit"
			journey_phase_changed.emit(actor_id, "waiting_exit")
			_queue_sync(actor_id, track, false)
	elif phase == "departing":
		var pend: Array = track.get("pending", [])
		if pend.size() > 0 and _area != null and str(pend[0].get("to_node", "")) == str(_area.current_node):
			_start_entrance_from_pending(track)
		elif pend.size() > 0:
			# Left this room; destination camera will drain the pending entrance.
			track["phase"] = "idle"
			track["playing_pending"] = false
			journey_phase_changed.emit(actor_id, "idle")
			_apply_sprite(actor_id, track)
		else:
			_start_entrance_from_pending(track)
	elif phase in ["entering", "to_waypoint", "to_delivery"]:
		if phase == "entering":
			var onward := str(track.get("onward_phase", "to_waypoint"))
			track["phase"] = onward
			track["local_from"] = track["local_pos"]
			# local_to already set from pending
			track["path"] = _build_path(track["local_pos"], track["local_to"])
			track["path_i"] = 0
			track["segment_t"] = 0.0
			track["progress_ms"] = 0
			journey_phase_changed.emit(actor_id, onward)
		else:
			var pending_next: Array = track.get("pending", [])
			if pending_next.size() > 0 and _area != null:
				var nxt_to := str(pending_next[0].get("to_node", ""))
				if nxt_to == str(_area.current_node):
					_start_entrance_from_pending(track)
				elif nxt_to != "" and str(track.get("from_node")) == str(_area.current_node):
					# Next edge leaves this room — brief depart, leave pending for destination.
					_begin_depart_then_enter(track)
				else:
					track["phase"] = "idle"
					track["playing_pending"] = false
					_queue_sync(actor_id, track, false)
			else:
				track["phase"] = "idle" if phase != "to_delivery" else "unloading"
				if track["phase"] == "unloading":
					track["progress_ms"] = 0
					track["duration_ms"] = 1200
				journey_phase_changed.emit(actor_id, str(track["phase"]))
				track["playing_pending"] = false
				_queue_sync(actor_id, track, true)


func _begin_depart_then_enter(track: Dictionary) -> void:
	track["phase"] = "departing"
	# Brief outward step into doorway band.
	var hold: Vector2 = track.get("local_to", Vector2(12, 5))
	var outward := hold
	if str(track.get("from_node")) == "node:1" or hold.x >= 10.0:
		outward = Vector2(hold.x + 0.6, hold.y)
	else:
		outward = Vector2(maxf(hold.x - 0.6, 0.3), hold.y)
	track["local_from"] = track["local_pos"]
	track["local_to"] = outward
	track["path"] = _build_path(track["local_pos"], outward)
	track["path_i"] = 0
	track["segment_t"] = 0.0
	track["progress_ms"] = 0
	track["duration_ms"] = 500
	track["playing_pending"] = true
	journey_phase_changed.emit(str(track.get("actor_id")), "departing")


func _start_entrance_from_pending(track: Dictionary) -> void:
	var pending: Array = track.get("pending", [])
	var transition: Dictionary = {}
	if pending.size() > 0:
		transition = pending.pop_front()
		track["pending"] = pending
	elif track.has("pending_arrival"):
		transition = track["pending_arrival"]
		track.erase("pending_arrival")
	var arrival := _vec(transition.get("arrival_grid"), Vector2(1.5, 5))
	var local_to := _vec(transition.get("local_to"), arrival)
	track["from_node"] = str(transition.get("to_node", track.get("to_node")))
	track["to_node"] = str(transition.get("to_node", track.get("to_node")))
	track["phase"] = "entering"
	track["local_from"] = arrival
	track["local_to"] = local_to
	track["local_pos"] = arrival
	track["onward_phase"] = str(transition.get("onward_phase", "to_waypoint"))
	track["path"] = _build_path(arrival, local_to)
	track["path_i"] = 0
	track["segment_t"] = 0.0
	track["progress_ms"] = 0
	track["duration_ms"] = 2800
	track["consumed_sequence"] = transition.get("sequence")
	journey_phase_changed.emit(str(track.get("actor_id")), "entering")
	_queue_sync(str(track.get("actor_id")), track, true)


func _advance_along_path(track: Dictionary, delta_sec: float) -> bool:
	var path: Array = track.get("path", [])
	if path.is_empty():
		track["local_pos"] = track.get("local_to", track.get("local_pos"))
		track["progress_ms"] = int(track.get("duration_ms", 1))
		return true
	var speed := DEFAULT_SPEED_PX / TILE  # cells per second
	var remaining := delta_sec * speed
	while remaining > 0.0 and int(track.get("path_i", 0)) < path.size() - 1:
		var i := int(track["path_i"])
		var a: Vector2 = path[i]
		var b: Vector2 = path[i + 1]
		var seg_len := a.distance_to(b)
		if seg_len < 0.001:
			track["path_i"] = i + 1
			track["segment_t"] = 0.0
			continue
		var t := float(track.get("segment_t", 0.0))
		var dist_left := (1.0 - t) * seg_len
		if remaining >= dist_left:
			remaining -= dist_left
			track["path_i"] = i + 1
			track["segment_t"] = 0.0
			track["local_pos"] = b
		else:
			var step := remaining / seg_len
			t += step
			track["segment_t"] = t
			track["local_pos"] = a.lerp(b, t)
			remaining = 0.0
	var dur := float(track.get("duration_ms", 2500))
	var total_cells := 0.0
	for j in range(maxi(path.size() - 1, 0)):
		total_cells += path[j].distance_to(path[j + 1])
	var done_cells := 0.0
	var pi := int(track.get("path_i", 0))
	for j in range(mini(pi, path.size() - 1)):
		done_cells += path[j].distance_to(path[j + 1])
	if pi < path.size() - 1:
		done_cells += float(track.get("segment_t", 0.0)) * path[pi].distance_to(path[pi + 1])
	var frac := 1.0 if total_cells < 0.001 else clampf(done_cells / total_cells, 0.0, 1.0)
	track["progress_ms"] = int(frac * dur)
	return pi >= path.size() - 1


func _apply_sprite(actor_id: String, track: Dictionary) -> void:
	if _area == null:
		return
	var node_id := str(_area.current_node)
	var presenting := str(track.get("from_node"))
	var phase := str(track.get("phase"))
	if phase in ["entering", "to_waypoint", "to_delivery", "unloading", "idle"]:
		presenting = str(track.get("to_node", presenting))
	# After authorized cross during departing, sprite may vanish until entrance on new node.
	if phase == "departing" and track.get("authorized_cross", false):
		presenting = str(track.get("from_node"))
	if node_id != presenting:
		# Hide sprite on this area if actor is elsewhere.
		if _area._npc_nodes.has(actor_id):
			_area._npc_nodes[actor_id].visible = false
			if _area._label_nodes.has(actor_id):
				_area._label_nodes[actor_id].visible = false
		return
	if not _area._npc_nodes.has(actor_id):
		return
	var spr: Node2D = _area._npc_nodes[actor_id]
	spr.visible = true
	var pos: Vector2 = track.get("local_pos", Vector2(6, 5))
	spr.position = Vector2(pos.x * TILE + TILE * 0.5, pos.y * TILE + TILE * 0.5)
	if _area._label_nodes.has(actor_id):
		var lbl: Label = _area._label_nodes[actor_id]
		lbl.visible = true
		lbl.position = spr.position + Vector2(-30, -48)
	journey_progress.emit(actor_id, int(track.get("progress_ms", 0)), pos)


func _build_path(from_cell: Vector2, to_cell: Vector2) -> Array:
	if _area == null:
		return [from_cell, to_cell]
	var start := Vector2i(int(round(from_cell.x)), int(round(from_cell.y)))
	var goal := Vector2i(int(round(to_cell.x)), int(round(to_cell.y)))
	start = _clamp_cell(start)
	goal = _clamp_cell(goal)
	if start == goal:
		return [from_cell, to_cell]
	var came := _bfs(start, goal)
	if came.is_empty():
		# Fallback corridor along row 5 (exit band) then to goal.
		return [from_cell, Vector2(from_cell.x, 5), Vector2(to_cell.x, 5), to_cell]
	var cells: Array = []
	var cur := goal
	cells.push_front(Vector2(cur.x, cur.y))
	while came.has(cur) and came[cur] != cur:
		cur = came[cur]
		cells.push_front(Vector2(cur.x, cur.y))
		if cells.size() > 200:
			break
	# Replace ends with precise fractional endpoints.
	if cells.size() >= 1:
		cells[0] = from_cell
		cells[cells.size() - 1] = to_cell
	return cells


func _bfs(start: Vector2i, goal: Vector2i) -> Dictionary:
	var came: Dictionary = {}
	var q: Array = [start]
	came[start] = start
	var dirs := [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]
	while not q.is_empty():
		var c: Vector2i = q.pop_front()
		if c == goal:
			return came
		for d in dirs:
			var n: Vector2i = c + d
			if came.has(n):
				continue
			if not _walkable(n):
				continue
			came[n] = c
			q.append(n)
	return {}


func _walkable(cell: Vector2i) -> bool:
	if cell.x < 1 or cell.y < 1 or cell.x > 12 or cell.y > 8:
		# Allow doorway edge cells used as holds.
		if cell.y >= 4 and cell.y <= 5 and (cell.x == 0 or cell.x == 13):
			return true
		if cell.x < 0 or cell.y < 0 or cell.x > 13 or cell.y > 9:
			return false
	if _area != null and _area.has_method("is_cell_blocked"):
		if _area.is_cell_blocked(cell):
			# Doorway gaps are walkable even if wall tile exists beside them.
			if cell.y >= 4 and cell.y <= 5 and (cell.x <= 1 or cell.x >= 12):
				return true
			return false
	return true


func _clamp_cell(cell: Vector2i) -> Vector2i:
	return Vector2i(clampi(cell.x, 0, 13), clampi(cell.y, 0, 9))


func _vec(value, fallback: Vector2) -> Vector2:
	if typeof(value) == TYPE_ARRAY or typeof(value) == TYPE_PACKED_FLOAT32_ARRAY or typeof(value) == TYPE_PACKED_FLOAT64_ARRAY:
		if value.size() >= 2:
			return Vector2(float(value[0]), float(value[1]))
	if typeof(value) == TYPE_VECTOR2:
		return value
	return fallback


var _pending_sync: Dictionary = {}


func _queue_sync(actor_id: String, track: Dictionary, consume_pending: bool) -> void:
	_pending_sync[actor_id] = {
		"actor_id": actor_id,
		"journey_id": track.get("journey_id"),
		"phase": track.get("phase"),
		"progress_ms": track.get("progress_ms"),
		"local_pos": [track.get("local_pos").x, track.get("local_pos").y] if typeof(track.get("local_pos")) == TYPE_VECTOR2 else track.get("local_pos"),
		"consume_pending": consume_pending,
		"consumed_sequence": track.get("consumed_sequence"),
	}


func _flush_syncs() -> void:
	if _client == null:
		_pending_sync.clear()
		return
	for actor_id in _pending_sync.keys():
		var payload: Dictionary = _pending_sync[actor_id]
		needs_sync.emit(str(actor_id), payload)
		_client.send_command(
			"pres-%s-%s" % [actor_id, Time.get_ticks_msec()],
			"SyncPresentation",
			payload
		)
	_pending_sync.clear()


func world_position_for(actor_id: String) -> Vector2:
	var track: Dictionary = _tracks.get(actor_id, {})
	if track.is_empty():
		return Vector2.ZERO
	var pos: Vector2 = track.get("local_pos", Vector2.ZERO)
	return Vector2(pos.x * TILE + TILE * 0.5, pos.y * TILE + TILE * 0.5)


func presenting_on_node(actor_id: String, node_id: String) -> bool:
	if not _tracks.has(actor_id):
		return false
	var track: Dictionary = _tracks[actor_id]
	var phase := str(track.get("phase", "idle"))
	if phase in ["to_exit", "waiting_exit", "departing", "blocked"]:
		if str(track.get("from_node")) == node_id:
			return true
	elif phase in ["entering", "to_waypoint", "to_delivery", "unloading"]:
		if str(track.get("to_node")) == node_id or str(track.get("from_node")) == node_id:
			return true
	# Unplayed pending entrances for this room (rapid Wait / follow-after-Travel).
	var pending: Array = track.get("pending", [])
	for item in pending:
		if str(item.get("to_node", "")) == node_id:
			return true
	if track.has("pending_arrival") and str(track["pending_arrival"].get("to_node", "")) == node_id:
		return true
	return false


func is_driving(actor_id: String) -> bool:
	if not _tracks.has(actor_id):
		return false
	var phase := str(_tracks[actor_id].get("phase", "idle"))
	return phase not in ["idle"]
