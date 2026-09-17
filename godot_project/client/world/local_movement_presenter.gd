extends RefCounted
class_name DmbLocalMovementPresenter

## Sequence-driven Game-Time local mover for presentation-only journeys.
## Does not mutate cargo, credit stock, or advance World Turns.
## Pending transitions are only removed after Python accepts the sequence ACK.

const TILE := 64.0
const DEFAULT_SPEED_PX := 64.0
const MAX_QUEUE := 3
const DEPART_BEYOND := 1.6

signal journey_phase_changed(actor_id: String, phase: String)
signal journey_progress(actor_id: String, progress_ms: int, local_pos: Vector2)
signal needs_sync(actor_id: String, payload: Dictionary)

var _area  # DmbFxClockArea
var _client = null
var _paused := false
var _tracks: Dictionary = {}  # actor_id -> track dict
var _sync_acc_ms := 0.0
var _pending_sync: Dictionary = {}


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
	var drop: Array = []
	for actor_id in _tracks.keys():
		if not journeys.has(actor_id):
			drop.append(actor_id)
	for actor_id in drop:
		_tracks.erase(actor_id)
	if _area == null:
		return
	var here := str(_area.current_node)
	for actor_id in _tracks.keys():
		var track: Dictionary = _tracks[actor_id]
		var phase := str(track.get("phase", ""))
		var pending: Array = track.get("pending", [])
		if pending.is_empty():
			continue
		var nxt: Dictionary = pending[0]
		if str(nxt.get("to_node", "")) != here:
			continue
		# Follow-immediately: skip leftover depart and begin entrance once.
		if phase in ["to_exit", "waiting_exit", "departing", "hidden"]:
			_begin_entrance_ack(track, nxt)


func _ensure_track(actor_id: String, journey: Dictionary, pending) -> void:
	var jid := str(journey.get("journey_id", ""))
	var track: Dictionary = _tracks.get(actor_id, {})
	var pending_list: Array = []
	if typeof(pending) == TYPE_ARRAY:
		pending_list = pending.duplicate(true)
	var auth_last := int(journey.get("last_consumed_sequence", 0))
	if track.is_empty() or str(track.get("journey_id", "")) != jid:
		track = _track_from_journey(actor_id, journey, pending_list)
		_tracks[actor_id] = track
		return

	# Authority pending is source of truth (never locally pop before ACK).
	track["pending"] = pending_list
	track["authorized_cross"] = bool(journey.get("authorized_cross", track.get("authorized_cross", false)))
	track["last_consumed_sequence"] = maxi(int(track.get("last_consumed_sequence", 0)), auth_last)
	if journey.has("pending_arrival") and typeof(journey.get("pending_arrival")) == TYPE_DICTIONARY:
		# Keep as hint only; pending_list is authoritative.
		pass

	var auth_phase := str(journey.get("phase", ""))
	var local_phase := str(track.get("phase", ""))
	var local_last := int(track.get("last_consumed_sequence", 0))

	# Never adopt an older authority leg over a newer locally acknowledged phase.
	if auth_last < local_last:
		_tracks[actor_id] = track
		return
	if track.get("awaiting_ack", false):
		# Wait for matching ACK to land in authority before adopting.
		if auth_last >= int(track.get("awaiting_sequence", -1)):
			track["awaiting_ack"] = false
			track["awaiting_sequence"] = -1
		else:
			_tracks[actor_id] = track
			return

	if auth_phase == "blocked":
		track["phase"] = "blocked"
		track["presenting_node"] = str(journey.get("presenting_node", track.get("from_node")))
		track["local_to"] = _vec(journey.get("local_to"), track["local_to"])
		track["path"] = _build_path(track["local_pos"], track["local_to"])
		track["path_i"] = 0
		track["segment_t"] = 0.0
	elif auth_last > int(track.get("applied_auth_last", -1)) and auth_phase != local_phase:
		# Fresh authority acknowledgement — resume from persisted metadata without restarting
		# if we are already on the same phase/target.
		var same_leg := (
			local_phase == auth_phase
			and str(track.get("presenting_node")) == str(journey.get("presenting_node", ""))
			and _vec(journey.get("local_to"), track["local_to"]).distance_to(track["local_to"]) < 0.05
		)
		if not same_leg and not track.get("playing_pending", false):
			_adopt_leg(track, journey)
		elif same_leg:
			track["progress_ms"] = int(journey.get("progress_ms", track.get("progress_ms", 0)))
			track["local_pos"] = _vec(journey.get("local_pos"), track["local_pos"])
		track["applied_auth_last"] = auth_last
	elif auth_phase in ["entering", "to_waypoint", "to_delivery", "unloading", "hidden", "waiting_exit"]:
		if local_phase in ["to_exit", "waiting_exit", "departing"] and track.get("authorized_cross", false):
			pass  # finish depart locally
		elif local_phase == "hidden" and auth_phase == "entering":
			_adopt_leg(track, journey)
		elif local_phase != auth_phase and not track.get("playing_pending", false) and auth_last >= local_last:
			# Only adopt when authority is at least as new and we are not mid-segment.
			if auth_last > local_last or (auth_last == local_last and _phase_rank(auth_phase) >= _phase_rank(local_phase)):
				if _phase_rank(auth_phase) > _phase_rank(local_phase) or local_phase == "idle":
					_adopt_leg(track, journey)
	_tracks[actor_id] = track


func _phase_rank(phase: String) -> int:
	match phase:
		"to_exit":
			return 1
		"waiting_exit":
			return 2
		"departing":
			return 3
		"hidden":
			return 4
		"entering":
			return 5
		"to_waypoint":
			return 6
		"to_delivery":
			return 7
		"unloading":
			return 8
		"idle":
			return 9
		"blocked":
			return 2
		_:
			return 0


func _track_from_journey(actor_id: String, journey: Dictionary, pending_list: Array) -> Dictionary:
	var track := {
		"journey_id": str(journey.get("journey_id", "")),
		"actor_id": actor_id,
		"phase": str(journey.get("phase", "idle")),
		"presenting_node": str(journey.get("presenting_node", journey.get("from_node", ""))),
		"from_node": str(journey.get("from_node", "")),
		"to_node": str(journey.get("to_node", "")),
		"local_from": _vec(journey.get("local_from"), Vector2(6, 5)),
		"local_to": _vec(journey.get("local_to"), Vector2(12, 5)),
		"local_pos": _vec(journey.get("local_pos"), _vec(journey.get("local_from"), Vector2(6, 5))),
		"progress_ms": int(journey.get("progress_ms", 0)),
		"duration_ms": maxi(int(journey.get("duration_ms", 2500)), 400),
		"authorized_cross": bool(journey.get("authorized_cross", false)),
		"onward_phase": str(journey.get("onward_phase", "to_waypoint")),
		"last_consumed_sequence": int(journey.get("last_consumed_sequence", 0)),
		"applied_auth_last": int(journey.get("last_consumed_sequence", 0)),
		"path": [],
		"path_i": 0,
		"segment_t": 0.0,
		"pending": pending_list,
		"playing_pending": false,
		"awaiting_ack": false,
		"awaiting_sequence": -1,
	}
	if str(track["phase"]) == "hidden":
		track["presenting_node"] = ""
	track["path"] = _build_path(track["local_pos"], track["local_to"])
	return track


func _adopt_leg(track: Dictionary, journey: Dictionary) -> void:
	track["phase"] = str(journey.get("phase", track.get("phase")))
	track["presenting_node"] = str(journey.get("presenting_node", track.get("presenting_node")))
	track["from_node"] = str(journey.get("from_node", track.get("from_node")))
	track["to_node"] = str(journey.get("to_node", track.get("to_node")))
	track["local_from"] = _vec(journey.get("local_from"), track["local_pos"])
	track["local_to"] = _vec(journey.get("local_to"), track["local_to"])
	track["local_pos"] = _vec(journey.get("local_pos"), track["local_from"])
	track["progress_ms"] = int(journey.get("progress_ms", 0))
	track["duration_ms"] = maxi(int(journey.get("duration_ms", 2500)), 400)
	track["onward_phase"] = str(journey.get("onward_phase", track.get("onward_phase", "to_waypoint")))
	track["last_consumed_sequence"] = int(journey.get("last_consumed_sequence", track.get("last_consumed_sequence", 0)))
	track["path"] = _build_path(track["local_pos"], track["local_to"])
	track["path_i"] = 0
	track["segment_t"] = 0.0
	if str(track["phase"]) == "hidden":
		track["presenting_node"] = ""


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
	if phase in ["idle", "waiting_exit", "unloading", "hidden"]:
		if phase == "waiting_exit" and track.get("authorized_cross", false) and _has_pending_for_depart(track):
			_begin_depart(track)
		elif phase == "hidden":
			_try_start_entrance_if_here(track)
		elif phase == "unloading":
			track["progress_ms"] = int(track.get("progress_ms", 0)) + int(delta_sec * 1000.0)
			if int(track["progress_ms"]) >= int(track.get("duration_ms", 1400)):
				track["phase"] = "idle"
				track["playing_pending"] = false
				journey_phase_changed.emit(actor_id, "idle")
				_queue_sync(actor_id, track, false)
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
		if track.get("authorized_cross", false) and _has_pending_for_depart(track):
			_begin_depart(track)
		else:
			track["phase"] = "waiting_exit"
			track["presenting_node"] = str(track.get("from_node"))
			journey_phase_changed.emit(actor_id, "waiting_exit")
			_queue_sync(actor_id, track, false)
	elif phase == "departing":
		_finish_depart_hide(track)
	elif phase == "entering":
		var onward := str(track.get("onward_phase", "to_waypoint"))
		track["phase"] = onward
		track["local_from"] = track["local_pos"]
		track["path"] = _build_path(track["local_pos"], track["local_to"])
		track["path_i"] = 0
		track["segment_t"] = 0.0
		track["progress_ms"] = 0
		track["playing_pending"] = false
		journey_phase_changed.emit(actor_id, onward)
		_queue_sync(actor_id, track, false)
	elif phase == "to_waypoint":
		# Cross once to east exit; wait unless next edge already authorised.
		if track.get("authorized_cross", false) and _pending_leaves_here(track):
			_begin_depart(track)
		else:
			track["phase"] = "waiting_exit"
			track["presenting_node"] = str(track.get("from_node"))
			track["playing_pending"] = false
			journey_phase_changed.emit(actor_id, "waiting_exit")
			_queue_sync(actor_id, track, false)
	elif phase == "to_delivery":
		track["phase"] = "unloading"
		track["progress_ms"] = 0
		track["duration_ms"] = 1400
		track["playing_pending"] = false
		journey_phase_changed.emit(actor_id, "unloading")
		_queue_sync(actor_id, track, false)


func _has_pending_for_depart(track: Dictionary) -> bool:
	var pending: Array = track.get("pending", [])
	if pending.is_empty():
		return track.get("authorized_cross", false)
	# Depart when head pending leaves the current presenting/from node.
	var head: Dictionary = pending[0]
	return str(head.get("from_node", "")) == str(track.get("from_node")) or str(head.get("from_node", "")) == str(track.get("presenting_node"))


func _pending_leaves_here(track: Dictionary) -> bool:
	var pending: Array = track.get("pending", [])
	if pending.is_empty():
		return false
	var head: Dictionary = pending[0]
	var here := str(track.get("presenting_node", track.get("from_node")))
	return str(head.get("from_node", "")) == here and str(head.get("to_node", "")) != here


func _try_start_entrance_if_here(track: Dictionary) -> void:
	if _area == null:
		return
	var pending: Array = track.get("pending", [])
	if pending.is_empty():
		return
	var head: Dictionary = pending[0]
	if str(head.get("to_node", "")) == str(_area.current_node):
		_begin_entrance_ack(track, head)


func _begin_depart(track: Dictionary) -> void:
	track["phase"] = "departing"
	track["playing_pending"] = true
	var hold: Vector2 = track.get("local_to", track.get("local_pos", Vector2(12, 5)))
	var outward := hold
	if hold.x >= 8.0:
		outward = Vector2(hold.x + DEPART_BEYOND, hold.y)
	else:
		outward = Vector2(maxf(hold.x - DEPART_BEYOND, -0.5), hold.y)
	track["local_from"] = track["local_pos"]
	track["local_to"] = outward
	track["path"] = _build_path(track["local_pos"], outward)
	track["path_i"] = 0
	track["segment_t"] = 0.0
	track["progress_ms"] = 0
	track["duration_ms"] = 900
	track["presenting_node"] = str(track.get("from_node"))
	journey_phase_changed.emit(str(track.get("actor_id")), "departing")
	_queue_sync(str(track.get("actor_id")), track, false)


func _finish_depart_hide(track: Dictionary) -> void:
	track["phase"] = "hidden"
	track["presenting_node"] = ""
	track["playing_pending"] = false
	journey_phase_changed.emit(str(track.get("actor_id")), "hidden")
	_queue_sync(str(track.get("actor_id")), track, false)
	_apply_sprite(str(track.get("actor_id")), track)
	_try_start_entrance_if_here(track)


func _begin_entrance_ack(track: Dictionary, transition: Dictionary) -> void:
	# Do NOT pop pending locally — Python removes it only after sequence ACK.
	var seq := int(transition.get("sequence", -1))
	if int(track.get("last_consumed_sequence", 0)) >= seq and seq >= 0:
		return
	if track.get("awaiting_ack", false) and int(track.get("awaiting_sequence", -1)) == seq:
		return
	var arrival := _vec(transition.get("arrival_grid"), Vector2(1.5, 5))
	var local_to := _vec(transition.get("local_to"), arrival)
	var dest := str(transition.get("to_node", track.get("to_node")))
	track["from_node"] = dest
	track["to_node"] = dest
	track["phase"] = "entering"
	track["presenting_node"] = dest
	track["local_from"] = arrival
	track["local_to"] = local_to
	track["local_pos"] = arrival
	track["onward_phase"] = str(transition.get("onward_phase", "to_waypoint"))
	track["path"] = _build_path(arrival, local_to)
	track["path_i"] = 0
	track["segment_t"] = 0.0
	track["progress_ms"] = 0
	track["duration_ms"] = 4000
	track["consumed_sequence"] = seq
	track["awaiting_ack"] = true
	track["awaiting_sequence"] = seq
	track["playing_pending"] = true
	if transition.get("committed_edge") != null:
		track["committed_edge"] = transition.get("committed_edge")
	journey_phase_changed.emit(str(track.get("actor_id")), "entering")
	_queue_sync(str(track.get("actor_id")), track, true)


func _advance_along_path(track: Dictionary, delta_sec: float) -> bool:
	var path: Array = track.get("path", [])
	if path.is_empty():
		track["local_pos"] = track.get("local_to", track.get("local_pos"))
		track["progress_ms"] = int(track.get("duration_ms", 1))
		return true
	var speed := DEFAULT_SPEED_PX / TILE
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
	var phase := str(track.get("phase"))
	var presenting := str(track.get("presenting_node", ""))
	if phase == "hidden" or presenting == "":
		if _area._npc_nodes.has(actor_id):
			_area._npc_nodes[actor_id].visible = false
			if _area._label_nodes.has(actor_id):
				_area._label_nodes[actor_id].visible = false
		return
	if node_id != presenting:
		if _area._npc_nodes.has(actor_id):
			_area._npc_nodes[actor_id].visible = false
			if _area._label_nodes.has(actor_id):
				_area._label_nodes[actor_id].visible = false
		return
	# Past doorway threshold during depart: hide before finishing path.
	if phase == "departing":
		var pos_chk: Vector2 = track.get("local_pos", Vector2(6, 5))
		if pos_chk.x > 12.85 or pos_chk.x < 0.15:
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
		return [from_cell, Vector2(from_cell.x, 5), Vector2(to_cell.x, 5), to_cell]
	var cells: Array = []
	var cur := goal
	cells.push_front(Vector2(cur.x, cur.y))
	while came.has(cur) and came[cur] != cur:
		cur = came[cur]
		cells.push_front(Vector2(cur.x, cur.y))
		if cells.size() > 200:
			break
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
		if cell.y >= 4 and cell.y <= 5 and (cell.x == 0 or cell.x == 13):
			return true
		if cell.x < -1 or cell.y < 0 or cell.x > 14 or cell.y > 9:
			return false
	if _area != null and _area.has_method("is_cell_blocked"):
		if _area.is_cell_blocked(cell):
			if cell.y >= 4 and cell.y <= 5 and (cell.x <= 1 or cell.x >= 12):
				return true
			return false
	return true


func _clamp_cell(cell: Vector2i) -> Vector2i:
	return Vector2i(clampi(cell.x, -1, 14), clampi(cell.y, 0, 9))


func _vec(value, fallback: Vector2) -> Vector2:
	if typeof(value) == TYPE_ARRAY or typeof(value) == TYPE_PACKED_FLOAT32_ARRAY or typeof(value) == TYPE_PACKED_FLOAT64_ARRAY:
		if value.size() >= 2:
			return Vector2(float(value[0]), float(value[1]))
	if typeof(value) == TYPE_VECTOR2:
		return value
	return fallback


func _grid_payload(value) -> Array:
	if typeof(value) == TYPE_VECTOR2:
		return [value.x, value.y]
	if typeof(value) == TYPE_ARRAY and value.size() >= 2:
		return [float(value[0]), float(value[1])]
	return [0.0, 0.0]


func _queue_sync(actor_id: String, track: Dictionary, consume_pending: bool) -> void:
	var payload := {
		"actor_id": actor_id,
		"journey_id": track.get("journey_id"),
		"phase": track.get("phase"),
		"presenting_node": track.get("presenting_node", ""),
		"from_node": track.get("from_node"),
		"to_node": track.get("to_node"),
		"local_from": _grid_payload(track.get("local_from")),
		"local_to": _grid_payload(track.get("local_to")),
		"local_pos": _grid_payload(track.get("local_pos")),
		"onward_phase": track.get("onward_phase"),
		"progress_ms": track.get("progress_ms"),
		"duration_ms": track.get("duration_ms"),
		"authorized_cross": track.get("authorized_cross", false),
		"consume_pending": consume_pending,
		"last_consumed_sequence": track.get("last_consumed_sequence", 0),
	}
	if consume_pending:
		payload["consumed_sequence"] = track.get("consumed_sequence")
	if track.get("committed_edge") != null:
		payload["committed_edge"] = track.get("committed_edge")
	_pending_sync[actor_id] = payload


func _flush_syncs() -> void:
	if _client == null:
		_pending_sync.clear()
		return
	for actor_id in _pending_sync.keys():
		var payload: Dictionary = _pending_sync[actor_id]
		needs_sync.emit(str(actor_id), payload)
		var reply: Dictionary = _client.send_command(
			"pres-%s-%s" % [actor_id, Time.get_ticks_msec()],
			"SyncPresentation",
			payload
		)
		# Only treat pending as consumed after Python accepts the sequence ACK.
		if payload.get("consume_pending", false):
			var body: Dictionary = reply.get("payload", {})
			if str(body.get("status", "")) == "ok":
				var journey: Dictionary = body.get("journey", {})
				var track: Dictionary = _tracks.get(actor_id, {})
				if not track.is_empty():
					track["last_consumed_sequence"] = int(journey.get("last_consumed_sequence", track.get("last_consumed_sequence", 0)))
					track["awaiting_ack"] = false
					track["applied_auth_last"] = int(track["last_consumed_sequence"])
					_tracks[actor_id] = track
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
	if phase == "hidden":
		return false
	var presenting := str(track.get("presenting_node", ""))
	if presenting != "" and presenting == node_id:
		return true
	# Unplayed pending entrance for this room while camera is here.
	var pending: Array = track.get("pending", [])
	for item in pending:
		if str(item.get("to_node", "")) == node_id and phase in ["hidden", "departing", "to_exit", "waiting_exit"]:
			return true
	return false


func is_driving(actor_id: String) -> bool:
	if not _tracks.has(actor_id):
		return false
	var phase := str(_tracks[actor_id].get("phase", "idle"))
	return phase not in ["idle"]
