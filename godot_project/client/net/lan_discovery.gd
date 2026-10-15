extends RefCounted
class_name LanDiscovery

## Finds hosts on the local network: a UDP probe to the broadcast addresses (and loopback), unicast replies collected by
## `poll()`. Hosts answer with their session info (name, port, state, players, version). Sending a broadcast works on
## Android without a multicast lock; the reply is unicast, so no fixed client port is needed.

const MAGIC := "DMB_DISCOVER"

var _udp := PacketPeerUDP.new()
var found: Dictionary = {}  # "host:port" -> info dictionary (with "host" and "port")
var probes := 0
var last_error := ""
var _port := 8767


func start(port: int = 8767) -> bool:
	_port = port
	var err := _udp.bind(0)
	if err != OK:
		last_error = "bind_%d" % err
		return false
	_udp.set_broadcast_enabled(true)
	return true


func stop() -> void:
	_udp.close()


func targets() -> PackedStringArray:
	var out: PackedStringArray = ["255.255.255.255", "127.0.0.1"]
	for a in IP.get_local_addresses():
		var s := str(a)
		if s.contains(":") or s.begins_with("127.") or s.begins_with("169.254."):
			continue
		var parts := s.split(".")
		if parts.size() == 4:
			out.append("%s.%s.%s.255" % [parts[0], parts[1], parts[2]])  # the subnet broadcast (some phones drop the limited broadcast)
	return out


func probe() -> void:
	var payload := ("%s?1" % MAGIC).to_utf8_buffer()
	for t in targets():
		_udp.set_dest_address(t, _port)
		_udp.put_packet(payload)
	probes += 1


func poll() -> void:
	while _udp.get_available_packet_count() > 0:
		var pkt := _udp.get_packet()
		var from := _udp.get_packet_ip()
		var parsed = JSON.parse_string(pkt.get_string_from_utf8())
		if typeof(parsed) != TYPE_DICTIONARY or int(parsed.get("dmb", 0)) != 1:
			continue
		var info: Dictionary = parsed
		info["host"] = from
		info["seen_ms"] = Time.get_ticks_msec()
		found["%s:%d" % [from, int(info.get("port", 0))]] = info


## Hosts seen in the last `max_age_ms`, newest first.
func hosts(max_age_ms: int = 4000) -> Array:
	var out: Array = []
	var now := Time.get_ticks_msec()
	for k in found:
		if now - int(found[k].get("seen_ms", 0)) <= max_age_ms:
			out.append(found[k])
	out.sort_custom(func(a, b): return int(a.get("seen_ms", 0)) > int(b.get("seen_ms", 0)))
	return out
