extends RefCounted
class_name DmbFrameCodec

## Length-prefixed UTF-8 JSON frames (4-byte big-endian size).

var _buffer: PackedByteArray = PackedByteArray()

const MAX_FRAME := 8 * 1024 * 1024


func encode(payload: Dictionary) -> PackedByteArray:
	var body := JSON.stringify(payload).to_utf8_buffer()
	if body.is_empty() or body.size() > MAX_FRAME:
		push_error("DmbFrameCodec: invalid frame size")
		return PackedByteArray()
	var out := PackedByteArray()
	out.resize(4)
	out.encode_u32(0, body.size())
	# encode_u32 is little-endian; rewrite as big-endian.
	var n := body.size()
	out[0] = (n >> 24) & 0xFF
	out[1] = (n >> 16) & 0xFF
	out[2] = (n >> 8) & 0xFF
	out[3] = n & 0xFF
	out.append_array(body)
	return out


func feed(data: PackedByteArray) -> Array:
	_buffer.append_array(data)
	var frames: Array = []
	while true:
		if _buffer.size() < 4:
			return frames
		var length := (_buffer[0] << 24) | (_buffer[1] << 16) | (_buffer[2] << 8) | _buffer[3]
		if length <= 0 or length > MAX_FRAME:
			push_error("DmbFrameCodec: malformed/oversize frame")
			_buffer.clear()
			return frames
		if _buffer.size() < 4 + length:
			return frames
		var body := _buffer.slice(4, 4 + length)
		_buffer = _buffer.slice(4 + length)
		var text := body.get_string_from_utf8()
		var parsed = JSON.parse_string(text)
		if typeof(parsed) == TYPE_DICTIONARY:
			frames.append(parsed)
	return frames
