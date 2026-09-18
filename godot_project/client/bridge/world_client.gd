extends Node
class_name DmbWorldClient

## Thin client over the loopback Python sidecar. Owns no durable world state.
## Hot path is nonblocking: enqueue → frame-polled send/recv (one in flight).

signal result(payload: Dictionary)
signal projection_updated(view: Dictionary)
signal bridge_failed(reason: String)
signal request_finished(request_id: String, reply: Dictionary)
signal bridge_stats(stats: Dictionary)

const FrameCodec = preload("res://client/bridge/frame_codec.gd")

const MAX_IN_FLIGHT := 1
const MAX_QUEUE := 48
const REQUEST_TIMEOUT_MS := 2500
const CONNECT_TIMEOUT_MS := 2500

var _peer := StreamPeerTCP.new()
var _codec := FrameCodec.new()
var _host := "127.0.0.1"
var _port := 0
var _token := ""
var _session_id := "godot-local"
var _world_id := ""
var _world_version := 0
var _connected := false
var _paused := false
var _legacy_tick_blocked := true
var _legacy_save_blocked := true

var _queue: Array = []
var _in_flight = null
var _inflight_sent_ms := 0
var _next_request_id := 1
var _player_cache: Dictionary = {}
var _completed: Dictionary = {}
var _waiting: Dictionary = {}

var _stats := {
	"requests_sent": 0,
	"requests_completed": 0,
	"bytes_in": 0,
	"bytes_out": 0,
	"latency_sum_ms": 0.0,
	"latency_count": 0,
	"timeouts": 0,
	"queue_high_water": 0,
	"dropped_coalesced": 0,
	"frames_received": 0,
}


func _process(_delta: float) -> void:
	if _connected:
		_poll()


func connect_sidecar(host: String, port: int, token: String) -> bool:
	_host = host
	_port = port
	_token = token
	_peer = StreamPeerTCP.new()
	_codec = FrameCodec.new()
	_queue.clear()
	_in_flight = null
	_completed.clear()
	var err := _peer.connect_to_host(host, port)
	if err != OK:
		bridge_failed.emit("connect_failed")
		return false
	var deadline := Time.get_ticks_msec() + CONNECT_TIMEOUT_MS
	while Time.get_ticks_msec() < deadline:
		_peer.poll()
		var status := _peer.get_status()
		if status == StreamPeerTCP.STATUS_CONNECTED:
			_connected = true
			break
		if status == StreamPeerTCP.STATUS_ERROR:
			bridge_failed.emit("connect_error")
			return false
		OS.delay_msec(5)
	if not _connected:
		bridge_failed.emit("connect_timeout")
		return false
	var reply := _blocking_roundtrip({
		"kind": "Handshake",
		"protocol_version": 1,
		"session_id": _session_id,
		"token": _token,
		"role": "local_client",
		"game_build_id": "g01",
	})
	if str(reply.get("status", "")) != "ACCEPTED":
		bridge_failed.emit("handshake_rejected:%s" % str(reply))
		_paused = true
		return false
	var new_world := str(reply.get("world_id", ""))
	if new_world != "" and new_world != _world_id and _world_id != "":
		clear_player_cache("world_change")
	_world_id = new_world
	_world_version = int(reply.get("world_version", 0))
	return true


func is_busy() -> bool:
	return _in_flight != null or not _queue.is_empty()


func in_flight_kind() -> String:
	if _in_flight == null:
		return ""
	return str(_in_flight.get("label", ""))


func cached_player_view() -> Dictionary:
	return _player_cache.duplicate(true)


func has_player_cache() -> bool:
	return not _player_cache.is_empty()


func clear_player_cache(reason: String = "") -> void:
	## Call on world change / Load of a different slot so omitted fields cannot revive stale entities.
	_player_cache.clear()
	if reason != "":
		projection_updated.emit({})


func player_cache_has_field(field: String) -> bool:
	return _player_cache.has(field)


static func merge_player_view(cache: Dictionary, incoming: Dictionary, requested_fields: Array = []) -> Dictionary:
	## Omitted keys mean no update. Explicitly present keys (including empty collections) replace.
	## When requested_fields is non-empty, only those economy keys plus always-present base keys are authoritative.
	var out: Dictionary = cache.duplicate(true)
	var base_keys := {
		"world_id": true,
		"world_version": true,
		"clock": true,
		"player": true,
		"board": true,
		"people": true,
		"presentation": true,
		"scope": true,
	}
	for key in incoming.keys():
		var apply := true
		if requested_fields.size() > 0 and not base_keys.has(key):
			apply = requested_fields.has(key)
		if apply:
			out[key] = incoming[key]
	return out


func bridge_metrics() -> Dictionary:
	var out := _stats.duplicate(true)
	out["queue_depth"] = _queue.size()
	out["in_flight"] = _in_flight != null
	out["world_version"] = _world_version
	var lat_n := int(out.get("latency_count", 0))
	out["latency_avg_ms"] = (float(out.get("latency_sum_ms", 0.0)) / float(lat_n)) if lat_n > 0 else 0.0
	return out


func request_view_blocking(scope: String = "player", fields: Array = []) -> Dictionary:
	var rid := enqueue_view(scope, fields, {"replaceable": false, "coalesce_key": ""})
	var reply: Dictionary = _wait_reply_spin(rid)
	if str(reply.get("status", "")) == "ACCEPTED":
		var view: Dictionary = reply.get("view", {})
		return view
	return {}


func request_view(scope: String = "player", fields: Array = []) -> Dictionary:
	## Synchronous helper for tests / infrequent UI. Play hot path uses enqueue_view.
	return request_view_blocking(scope, fields)


func request_view_async(scope: String = "player", fields: Array = []) -> Dictionary:
	var rid := enqueue_view(scope, fields, {"replaceable": false, "coalesce_key": ""})
	var reply: Dictionary = await wait_reply(rid)
	if str(reply.get("status", "")) == "ACCEPTED":
		return reply.get("view", {})
	return {}


func enqueue_view(scope: String = "player", fields: Array = [], opts: Dictionary = {}) -> String:
	var item := {
		"id": _alloc_id(),
		"type": "view",
		"label": "RequestView:%s" % scope,
		"scope": scope,
		"fields": fields.duplicate(),
		"coalesce_key": str(opts.get("coalesce_key", "view:%s" % scope)),
		"replaceable": bool(opts.get("replaceable", true)),
		"queued_ms": Time.get_ticks_msec(),
	}
	_enqueue(item)
	return str(item["id"])


func send_command_blocking(command_id: String, kind: String, payload: Dictionary, opts: Dictionary = {}) -> Dictionary:
	## Bootstrap / controlled failure helpers — do not use on the clock hot path.
	var rid := enqueue_command(command_id, kind, payload, opts)
	return _wait_reply_spin(rid)


func send_command(command_id: String, kind: String, payload: Dictionary, opts: Dictionary = {}) -> Dictionary:
	## Synchronous helper for tests / infrequent UI. Play hot path uses enqueue_command.
	return send_command_blocking(command_id, kind, payload, opts)


func send_command_async(command_id: String, kind: String, payload: Dictionary, opts: Dictionary = {}) -> Dictionary:
	var rid := enqueue_command(command_id, kind, payload, opts)
	return await wait_reply(rid)


func _wait_reply_spin(request_id: String) -> Dictionary:
	if _completed.has(request_id):
		var done: Dictionary = _completed[request_id]
		_completed.erase(request_id)
		return done
	var deadline := Time.get_ticks_msec() + REQUEST_TIMEOUT_MS
	while Time.get_ticks_msec() < deadline:
		_poll(false)
		if _completed.has(request_id):
			var reply: Dictionary = _completed[request_id]
			_completed.erase(request_id)
			return reply
		OS.delay_msec(1)
	_stats["timeouts"] = int(_stats.get("timeouts", 0)) + 1
	# Do not emit bridge_failed here — callers decide; avoids recovery re-entry loops.
	if _in_flight != null and str(_in_flight.get("id", "")) == request_id:
		_in_flight = null
	return {"status": "REJECTED", "code": "TIMEOUT", "request_id": request_id}


func wait_reply(request_id: String) -> Dictionary:
	if _completed.has(request_id):
		var done: Dictionary = _completed[request_id]
		_completed.erase(request_id)
		return done
	_waiting[request_id] = true
	var deadline := Time.get_ticks_msec() + REQUEST_TIMEOUT_MS
	while Time.get_ticks_msec() < deadline:
		_poll(false)
		if _completed.has(request_id):
			var reply: Dictionary = _completed[request_id]
			_completed.erase(request_id)
			_waiting.erase(request_id)
			return reply
		await get_tree().process_frame
	_waiting.erase(request_id)
	_stats["timeouts"] = int(_stats.get("timeouts", 0)) + 1
	if _in_flight != null and str(_in_flight.get("id", "")) == request_id:
		_in_flight = null
	return {"status": "REJECTED", "code": "TIMEOUT", "request_id": request_id}


func enqueue_command(command_id: String, kind: String, payload: Dictionary, opts: Dictionary = {}) -> String:
	if not _connected:
		bridge_failed.emit("not_connected")
		_paused = true
		var fail := {"status": "REJECTED", "code": "BRIDGE_DOWN"}
		var rid := _alloc_id()
		_completed[rid] = fail
		request_finished.emit(rid, fail)
		result.emit(fail)
		return rid
	var replaceable := bool(opts.get("replaceable", false))
	var coalesce_key := str(opts.get("coalesce_key", ""))
	if coalesce_key == "" and replaceable:
		coalesce_key = "cmd:%s" % kind
	var item := {
		"id": _alloc_id(),
		"type": "command",
		"label": kind,
		"command_id": command_id,
		"command_kind": kind,
		"payload": payload.duplicate(true),
		"coalesce_key": coalesce_key,
		"replaceable": replaceable,
		"queued_ms": Time.get_ticks_msec(),
	}
	_enqueue(item)
	return str(item["id"])


func pause(reason: String) -> Dictionary:
	return send_command("pause-%s" % reason, "Pause", {"reason": reason})


func resume(token: String) -> Dictionary:
	return send_command("resume-%s" % token, "Resume", {"token": token})


func recover_checkpoint() -> Dictionary:
	return send_command("recover-%s" % Time.get_ticks_msec(), "RecoverCheckpoint", {})


func legacy_writers_blocked() -> bool:
	return _legacy_tick_blocked and _legacy_save_blocked


func _alloc_id() -> String:
	var rid := "r%d" % _next_request_id
	_next_request_id += 1
	return rid


func _enqueue(item: Dictionary) -> void:
	if bool(item.get("replaceable", false)) and str(item.get("coalesce_key", "")) != "":
		var key := str(item["coalesce_key"])
		for i in range(_queue.size() - 1, -1, -1):
			var existing: Dictionary = _queue[i]
			if str(existing.get("coalesce_key", "")) == key and bool(existing.get("replaceable", false)):
				_queue[i] = item
				_stats["dropped_coalesced"] = int(_stats.get("dropped_coalesced", 0)) + 1
				_try_send_next()
				return
	if _queue.size() >= MAX_QUEUE:
		# Drop oldest replaceable item; never drop non-replaceable commands.
		var dropped := false
		for i in range(_queue.size()):
			if bool(_queue[i].get("replaceable", false)):
				_queue.remove_at(i)
				_stats["dropped_coalesced"] = int(_stats.get("dropped_coalesced", 0)) + 1
				dropped = true
				break
		if not dropped:
			bridge_failed.emit("queue_overflow")
			_paused = true
			return
	_queue.append(item)
	_stats["queue_high_water"] = maxi(int(_stats.get("queue_high_water", 0)), _queue.size())
	_try_send_next()


func _poll(emit_failures: bool = true) -> void:
	if not _connected:
		return
	_peer.poll()
	var status := _peer.get_status()
	if status != StreamPeerTCP.STATUS_CONNECTED:
		if status == StreamPeerTCP.STATUS_ERROR or status == StreamPeerTCP.STATUS_NONE:
			_connected = false
			_paused = true
			if emit_failures:
				bridge_failed.emit("disconnected")
		return
	_recv_available(emit_failures)
	_check_timeout(emit_failures)
	_try_send_next()


func _recv_available(emit_failures: bool = true) -> void:
	var available := _peer.get_available_bytes()
	if available <= 0:
		return
	var got := _peer.get_data(available)
	if int(got[0]) != OK:
		_paused = true
		if emit_failures:
			bridge_failed.emit("recv_failed")
		return
	var chunk: PackedByteArray = got[1]
	_stats["bytes_in"] = int(_stats.get("bytes_in", 0)) + chunk.size()
	var frames: Array = _codec.feed(chunk)
	# Process every received frame — never drop replies.
	for frame in frames:
		_stats["frames_received"] = int(_stats.get("frames_received", 0)) + 1
		_complete_in_flight(frame)


func _check_timeout(emit_failures: bool = true) -> void:
	if _in_flight == null:
		return
	if Time.get_ticks_msec() - _inflight_sent_ms < REQUEST_TIMEOUT_MS:
		return
	_stats["timeouts"] = int(_stats.get("timeouts", 0)) + 1
	var timeout := {"status": "REJECTED", "code": "TIMEOUT"}
	_finish_request(_in_flight, timeout)
	_in_flight = null
	_paused = true
	if emit_failures:
		bridge_failed.emit("reply_timeout")


func _try_send_next() -> void:
	if not _connected or _in_flight != null:
		return
	if _queue.is_empty():
		return
	var item: Dictionary = _queue.pop_front()
	# Assign expected_world_version at send time, not queue time.
	if str(item.get("type", "")) == "command":
		item["expected_world_version"] = _world_version
	if not _send_raw(_encode_item(item)):
		return
	_in_flight = item
	_inflight_sent_ms = Time.get_ticks_msec()
	_stats["requests_sent"] = int(_stats.get("requests_sent", 0)) + 1


func _encode_item(item: Dictionary) -> Dictionary:
	if str(item.get("type", "")) == "view":
		var frame := {"kind": "RequestView", "scope": str(item.get("scope", "player"))}
		var fields: Array = item.get("fields", [])
		if typeof(fields) == TYPE_ARRAY and fields.size() > 0:
			frame["fields"] = fields
		return frame
	return {
		"kind": "Command",
		"protocol_version": 1,
		"session_id": _session_id,
		"world_id": _world_id,
		"command_id": str(item.get("command_id", "")),
		"expected_world_version": int(item.get("expected_world_version", _world_version)),
		"command_kind": str(item.get("command_kind", "")),
		"payload": item.get("payload", {}),
	}


func _send_raw(payload: Dictionary) -> bool:
	var bytes := _codec.encode(payload)
	if bytes.is_empty():
		bridge_failed.emit("encode_failed")
		_paused = true
		return false
	_peer.poll()
	if _peer.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		bridge_failed.emit("not_connected_status")
		_paused = true
		_connected = false
		return false
	var err := _peer.put_data(bytes)
	if err != OK:
		bridge_failed.emit("send_failed")
		_paused = true
		return false
	_stats["bytes_out"] = int(_stats.get("bytes_out", 0)) + bytes.size()
	return true


func _complete_in_flight(reply: Dictionary) -> void:
	if _in_flight == null:
		# Orphan / late frame after timeout — still surface it; do not drop.
		result.emit(reply)
		return
	var item: Dictionary = _in_flight
	_in_flight = null
	_finish_request(item, reply)
	_try_send_next()


func _finish_request(item: Dictionary, reply: Dictionary) -> void:
	var rid := str(item.get("id", ""))
	var latency := float(Time.get_ticks_msec() - int(item.get("queued_ms", _inflight_sent_ms)))
	_stats["latency_sum_ms"] = float(_stats.get("latency_sum_ms", 0.0)) + latency
	_stats["latency_count"] = int(_stats.get("latency_count", 0)) + 1
	_stats["requests_completed"] = int(_stats.get("requests_completed", 0)) + 1
	if str(reply.get("status", "")) == "ACCEPTED" and not _accept_reply_identity(item, reply):
		reply = {
			"status": "REJECTED",
			"code": "STALE_REPLY",
			"request_id": rid,
			"detail": "world_id/version mismatch",
		}
	if reply.has("world_version") and str(reply.get("status", "")) == "ACCEPTED":
		_world_version = int(reply["world_version"])
	if str(item.get("type", "")) == "view" and str(reply.get("status", "")) == "ACCEPTED":
		var view: Dictionary = reply.get("view", {})
		if str(item.get("scope", "player")) == "player":
			var fields: Array = item.get("fields", [])
			_player_cache = merge_player_view(_player_cache, view, fields)
			projection_updated.emit(_player_cache.duplicate(true))
		else:
			projection_updated.emit(view)
	elif str(item.get("type", "")) == "command" and str(reply.get("status", "")) == "ACCEPTED":
		var kind := str(item.get("command_kind", ""))
		if kind == "Load":
			clear_player_cache("load")
			var loaded_world := str(reply.get("world_id", ""))
			if loaded_world == "" and reply.has("view") and typeof(reply.get("view")) == TYPE_DICTIONARY:
				loaded_world = str(reply.get("view").get("world_id", ""))
			if loaded_world != "":
				_world_id = loaded_world
		# Commands may include projection hints; merge when present (omit ≠ delete).
		if reply.has("view") and typeof(reply.get("view")) == TYPE_DICTIONARY:
			_player_cache = merge_player_view(_player_cache, reply.get("view"), [])
			projection_updated.emit(_player_cache.duplicate(true))
	_completed[rid] = reply
	request_finished.emit(rid, reply)
	result.emit(reply)
	bridge_stats.emit(bridge_metrics())
	# Bound completed map so waiters that abandoned do not leak.
	if _completed.size() > 64:
		var keys: Array = _completed.keys()
		for i in range(mini(16, keys.size())):
			var k := str(keys[i])
			if not _waiting.has(k):
				_completed.erase(k)


func _accept_reply_identity(item: Dictionary, reply: Dictionary) -> bool:
	## Reject views/commands that belong to a different world than the active session.
	## Load intentionally switches worlds and is exempt.
	if str(item.get("command_kind", "")) == "Load":
		return true
	var view: Variant = reply.get("view", null)
	var wid := ""
	if typeof(view) == TYPE_DICTIONARY:
		wid = str(view.get("world_id", ""))
	if wid == "":
		wid = str(reply.get("world_id", ""))
	if wid == "" or _world_id == "":
		return true
	return wid == _world_id


func _blocking_roundtrip(payload: Dictionary) -> Dictionary:
	## Startup/handshake only — must not be used on the play hot path.
	if not _send_raw(payload):
		return {"status": "REJECTED", "code": "SEND"}
	var deadline := Time.get_ticks_msec() + REQUEST_TIMEOUT_MS
	while Time.get_ticks_msec() < deadline:
		_peer.poll()
		if _peer.get_status() != StreamPeerTCP.STATUS_CONNECTED:
			bridge_failed.emit("disconnected")
			_paused = true
			return {"status": "REJECTED", "code": "DISCONNECTED"}
		var available := _peer.get_available_bytes()
		if available > 0:
			var got := _peer.get_data(available)
			if int(got[0]) != OK:
				bridge_failed.emit("recv_failed")
				_paused = true
				return {"status": "REJECTED", "code": "RECV"}
			var chunk: PackedByteArray = got[1]
			_stats["bytes_in"] = int(_stats.get("bytes_in", 0)) + chunk.size()
			var frames: Array = _codec.feed(chunk)
			if not frames.is_empty():
				# Handshake should be a single reply; still consume all frames.
				var first: Dictionary = frames[0]
				for i in range(1, frames.size()):
					result.emit(frames[i])
				return first
		OS.delay_msec(2)
	bridge_failed.emit("reply_timeout")
	_paused = true
	return {"status": "REJECTED", "code": "TIMEOUT"}
