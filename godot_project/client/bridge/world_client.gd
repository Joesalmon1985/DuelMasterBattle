extends Node
class_name DmbWorldClient

## Thin client over the loopback Python sidecar. Owns no durable world state.

signal result(payload: Dictionary)
signal projection_updated(view: Dictionary)
signal bridge_failed(reason: String)

const FrameCodec = preload("res://client/bridge/frame_codec.gd")

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


func connect_sidecar(host: String, port: int, token: String) -> bool:
	_host = host
	_port = port
	_token = token
	_peer = StreamPeerTCP.new()
	var err := _peer.connect_to_host(host, port)
	if err != OK:
		bridge_failed.emit("connect_failed")
		return false
	for _i in range(100):
		_peer.poll()
		var status := _peer.get_status()
		if status == StreamPeerTCP.STATUS_CONNECTED:
			_connected = true
			break
		if status == StreamPeerTCP.STATUS_ERROR:
			bridge_failed.emit("connect_error")
			return false
		OS.delay_msec(20)
	if not _connected:
		bridge_failed.emit("connect_timeout")
		return false
	var reply := _roundtrip({
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
	_world_id = str(reply.get("world_id", ""))
	_world_version = int(reply.get("world_version", 0))
	return true


func request_view(scope: String = "player") -> Dictionary:
	var reply := _roundtrip({"kind": "RequestView", "scope": scope})
	if str(reply.get("status", "")) == "ACCEPTED":
		var view: Dictionary = reply.get("view", {})
		projection_updated.emit(view)
		return view
	return {}


func send_command(command_id: String, kind: String, payload: Dictionary) -> Dictionary:
	if not _connected:
		bridge_failed.emit("not_connected")
		_paused = true
		return {"status": "REJECTED", "code": "BRIDGE_DOWN"}
	var reply := _roundtrip({
		"kind": "Command",
		"protocol_version": 1,
		"session_id": _session_id,
		"world_id": _world_id,
		"command_id": command_id,
		"expected_world_version": _world_version,
		"command_kind": kind,
		"payload": payload,
	})
	if reply.has("world_version"):
		_world_version = int(reply["world_version"])
	result.emit(reply)
	return reply


func pause(reason: String) -> Dictionary:
	return send_command("pause-%s" % reason, "Pause", {"reason": reason})


func resume(token: String) -> Dictionary:
	return send_command("resume-%s" % token, "Resume", {"token": token})


func legacy_writers_blocked() -> bool:
	return _legacy_tick_blocked and _legacy_save_blocked


func _roundtrip(payload: Dictionary) -> Dictionary:
	var bytes := _codec.encode(payload)
	if bytes.is_empty():
		bridge_failed.emit("encode_failed")
		_paused = true
		return {"status": "REJECTED", "code": "ENCODE"}
	_peer.poll()
	if _peer.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		bridge_failed.emit("not_connected_status")
		_paused = true
		return {"status": "REJECTED", "code": "NOT_CONNECTED"}
	var err := _peer.put_data(bytes)
	if err != OK:
		bridge_failed.emit("send_failed")
		_paused = true
		return {"status": "REJECTED", "code": "SEND"}
	for _i in range(200):
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
			var frames: Array = _codec.feed(got[1])
			if not frames.is_empty():
				return frames[0]
		OS.delay_msec(10)
	bridge_failed.emit("reply_timeout")
	_paused = true
	return {"status": "REJECTED", "code": "TIMEOUT"}
