extends RefCounted
class_name HybridSimClient

## One newline-JSON connection to the authoritative Python world: the single-player simulator on 127.0.0.1 or a LAN host.
## `op()` is the blocking request every existing caller uses; `request()` is the asynchronous form the multiplayer world
## uses for its state polls, so a slow Wi-Fi reply never stalls a frame. Replies arrive in send order on the one stream,
## so one queue of callbacks (null for a blocking op) serves both.

var _peer := StreamPeerTCP.new()
var _bytes := PackedByteArray()
var _pending: Array = []  # Callable per request, or null for a blocking op, in send order
var _sync_reply: Dictionary = {}
var _sync_ready := false
var host := "127.0.0.1"
var port := 0
var bytes_in := 0
var bytes_out := 0
var requests := 0
var replies := 0
var last_error := ""
var last_round_trip_ms := 0
var _sent_at: Array = []  # ticks when each pending request was sent (round-trip measurement)


func connect_to(port_: int) -> bool:
	return connect_to_host("127.0.0.1", port_)


func connect_to_host(host_: String, port_: int, timeout_ms: int = 3000) -> bool:
	host = host_
	port = port_
	_bytes = PackedByteArray()
	_pending.clear()
	_sent_at.clear()
	last_error = ""
	var err := _peer.connect_to_host(host_, port_)
	if err != OK:
		last_error = "connect_error_%d" % err
		return false
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		_peer.poll()
		var st := _peer.get_status()
		if st == StreamPeerTCP.STATUS_CONNECTED:
			_peer.set_no_delay(true)
			return true
		if st == StreamPeerTCP.STATUS_ERROR:
			last_error = "refused"
			return false
		OS.delay_msec(10)
	last_error = "timeout"
	_peer.disconnect_from_host()
	return false


func connected() -> bool:
	return _peer.get_status() == StreamPeerTCP.STATUS_CONNECTED


func disconnect_from_host() -> void:
	_peer.disconnect_from_host()
	_fail_pending("disconnected")


func pending_count() -> int:
	return _pending.size()


func _send(message: Dictionary) -> bool:
	if _peer.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		return false
	var buf := (JSON.stringify(message) + "\n").to_utf8_buffer()
	var err := _peer.put_data(buf)
	if err != OK:
		last_error = "send_error_%d" % err
		return false
	bytes_out += buf.size()
	requests += 1
	_sent_at.append(Time.get_ticks_msec())
	return true


## Send and return at once; `callback(reply: Dictionary)` runs from a later `poll()` (or `op()`).
func request(message: Dictionary, callback: Callable) -> bool:
	if not _send(message):
		callback.call({"status": "rejected", "reason": "not_connected"})
		return false
	_pending.append(callback)
	return true


## Read what has arrived and hand complete replies to their callbacks. The multiplayer world calls this every frame.
func poll() -> void:
	_peer.poll()
	if _peer.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		if not _pending.is_empty():
			_fail_pending("disconnected")
		return
	var available := _peer.get_available_bytes()
	if available > 0:
		var got: Array = _peer.get_data(available)
		if int(got[0]) == OK:
			var chunk: PackedByteArray = got[1]
			bytes_in += chunk.size()
			_bytes.append_array(chunk)
	_dispatch_lines()


func _dispatch_lines() -> void:
	while true:
		var nl := _bytes.find(10)
		if nl < 0:
			return
		var text := _bytes.slice(0, nl).get_string_from_utf8()
		_bytes = _bytes.slice(nl + 1)
		if text.strip_edges() == "":
			continue
		var parsed = JSON.parse_string(text)
		var reply: Dictionary = parsed if typeof(parsed) == TYPE_DICTIONARY else {"status": "rejected", "reason": "bad_reply"}
		replies += 1
		if not _sent_at.is_empty():
			last_round_trip_ms = Time.get_ticks_msec() - int(_sent_at.pop_front())
		if _pending.is_empty():
			continue  # a reply nobody waits for (after a timeout)
		var cb = _pending.pop_front()
		if cb == null:
			_sync_reply = reply
			_sync_ready = true
		elif cb is Callable and cb.is_valid():
			cb.call(reply)


func _fail_pending(reason: String) -> void:
	var cbs := _pending.duplicate()
	_pending.clear()
	_sent_at.clear()
	for cb in cbs:
		if cb is Callable and cb.is_valid():
			cb.call({"status": "rejected", "reason": reason})


## Blocking request: waits for this message's reply, delivering any earlier asynchronous replies on the way.
func op(message: Dictionary, timeout_ms: int = 4000) -> Dictionary:
	if not _send(message):
		return {"status": "rejected", "reason": "not_connected"}
	_pending.append(null)
	_sync_ready = false
	var deadline := Time.get_ticks_msec() + timeout_ms
	while Time.get_ticks_msec() < deadline:
		poll()
		if _sync_ready:
			_sync_ready = false
			return _sync_reply
		if _peer.get_status() != StreamPeerTCP.STATUS_CONNECTED:
			return {"status": "rejected", "reason": "disconnected"}
		OS.delay_msec(1)
	# the reply, if it ever comes, is dropped by _dispatch_lines (its marker is removed here)
	var idx := _pending.rfind(null)
	if idx >= 0:
		_pending.remove_at(idx)
	last_error = "timeout"
	return {"status": "rejected", "reason": "timeout"}
