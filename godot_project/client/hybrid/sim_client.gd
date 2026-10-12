extends RefCounted
class_name HybridSimClient

var _peer := StreamPeerTCP.new()
var _buffer := ""


func connect_to(port: int) -> bool:
	var err := _peer.connect_to_host("127.0.0.1", port)
	if err != OK:
		return false
	var deadline := Time.get_ticks_msec() + 3000
	while Time.get_ticks_msec() < deadline:
		_peer.poll()
		if _peer.get_status() == StreamPeerTCP.STATUS_CONNECTED:
			return true
		if _peer.get_status() == StreamPeerTCP.STATUS_ERROR:
			return false
		OS.delay_msec(10)
	return false


func op(message: Dictionary) -> Dictionary:
	if _peer.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		return {"status": "rejected", "reason": "not_connected"}
	var line := JSON.stringify(message) + "\n"
	_peer.put_data(line.to_utf8_buffer())
	var deadline := Time.get_ticks_msec() + 4000
	while Time.get_ticks_msec() < deadline:
		_peer.poll()
		var available := _peer.get_available_bytes()
		if available > 0:
			_buffer += _peer.get_utf8_string(available)
			var nl := _buffer.find("\n")
			if nl >= 0:
				var text := _buffer.substr(0, nl)
				_buffer = _buffer.substr(nl + 1)
				var parsed = JSON.parse_string(text)
				if typeof(parsed) == TYPE_DICTIONARY:
					return parsed
				return {"status": "rejected", "reason": "bad_reply"}
		OS.delay_msec(1)
	return {"status": "rejected", "reason": "timeout"}
