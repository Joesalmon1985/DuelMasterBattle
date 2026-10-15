extends Node

## Autoload `LanSession`: what the menu decided and what the world needs for a LAN game, plus the local Python host.
## mode: "single" (the classic 127.0.0.1 simulator, desktop), "host" (this device runs the Python world and plays),
## "join" (this device plays on another device's world). On Android a single-player game is a private hosted session
## (the world runs inside this app through the PySim plugin).

const SimClient = preload("res://client/hybrid/sim_client.gd")

const PROTOCOL_VERSION := 1
const GAME_VERSION := "0.1.0"  # must match WizardRTSHybrid/wizard_rts/net/protocol.py
const DEFAULT_PORT := 8765
const DISCOVERY_PORT := 8767

var mode := "single"
var host_address := "127.0.0.1"
var port := DEFAULT_PORT
var join_code := ""
var player_name := ""
var host_secret := ""
var token := ""
var player_id := ""
var is_host := false
var session_name := ""
var seed := 507
var map_size := "small"
var last_error := ""
var sim = null  # the live HybridSimClient handed from the lobby to the world
var private_session := false  # single player on a phone: hosted on 127.0.0.1, no discovery

var _host_pid := -1
var _ready_file := ""
var _host_status: Dictionary = {}


func is_multiplayer() -> bool:
	return mode != "single"


func reset() -> void:
	mode = "single"
	host_address = "127.0.0.1"
	port = DEFAULT_PORT
	join_code = ""
	host_secret = ""
	token = ""
	player_id = ""
	is_host = false
	session_name = ""
	last_error = ""
	private_session = false
	if sim != null:
		sim.disconnect_from_host()
	sim = null


func default_player_name() -> String:
	if player_name != "":
		return player_name
	var n := OS.get_environment("USER")
	if n == "":
		n = OS.get_environment("USERNAME")
	if n == "":
		n = "Wizard"
	return n.substr(0, 1).to_upper() + n.substr(1, 15)


func random_code() -> String:
	return "%04d" % (randi() % 10000)


static func random_hex(n: int) -> String:
	var s := ""
	for _i in n:
		s += "0123456789abcdef"[randi() % 16]
	return s


## Can this device run the authoritative world itself? Desktop: python3 on PATH. Android: the PySim plugin in the APK.
func can_host_locally() -> bool:
	if Engine.has_singleton("DmbPySim"):
		return true
	if OS.has_feature("android") or OS.has_feature("ios") or OS.has_feature("web"):
		return false
	return true


func hosting_backend() -> String:
	if Engine.has_singleton("DmbPySim"):
		return "chaquopy"
	return "python_process"


## Start the Python host on this device. Returns at once; poll `host_status()` until state is "ready" or "failed".
func start_local_host(name: String, code: String, seed_: int, map_: String, private: bool = false) -> Dictionary:
	host_secret = random_hex(24)
	join_code = code
	session_name = name
	seed = seed_
	map_size = map_
	private_session = private
	_host_status = {"state": "starting"}
	var bind := "127.0.0.1" if private else "0.0.0.0"
	var args := {"port": DEFAULT_PORT, "bind": bind, "name": name, "code": code, "secret": host_secret, "seed": seed_, "map": map_,
		"profile": "campaign", "max_players": 1 if private else 2, "discovery_port": 0 if private else DISCOVERY_PORT}
	if Engine.has_singleton("DmbPySim"):
		var plugin = Engine.get_singleton("DmbPySim")
		var raw: String = str(plugin.start(JSON.stringify(args)))
		var r = JSON.parse_string(raw)
		if typeof(r) != TYPE_DICTIONARY or str(r.get("status", "")) != "ok":
			_host_status = {"state": "failed", "error": raw}
		return _host_status
	var py := OS.get_environment("DMB_PYTHON")
	if py == "":
		py = "python3"
	var hyb := _hybrid_dir()
	if hyb == "":
		_host_status = {"state": "failed", "error": "WizardRTSHybrid directory not found next to the project (desktop hosting needs the repository layout)"}
		return _host_status
	_ready_file = OS.get_user_data_dir().path_join("lan_host_ready_%d.json" % (Time.get_ticks_msec() % 100000))
	var argv: PackedStringArray = ["-u", hyb.path_join("wizard_rts/net/host.py"), "--bind", bind, "--port", str(DEFAULT_PORT), "--name", name, "--code", code,
		"--secret", host_secret, "--seed", str(seed_), "--map", map_, "--max-players", "1" if private else "2", "--ready-file", _ready_file]
	if private:
		argv.append("--no-discovery")
	_host_pid = OS.create_process(py, argv, false)
	if _host_pid <= 0:
		_host_status = {"state": "failed", "error": "could not start %s (set DMB_PYTHON to your Python 3 executable)" % py}
	return _host_status


func host_status() -> Dictionary:
	if Engine.has_singleton("DmbPySim"):
		var raw: String = str(Engine.get_singleton("DmbPySim").status())
		var r = JSON.parse_string(raw)
		if typeof(r) == TYPE_DICTIONARY:
			_host_status = r
			if str(r.get("state", "")) == "ready":
				port = int(r.get("port", DEFAULT_PORT))
		return _host_status
	if str(_host_status.get("state", "")) in ["ready", "failed"]:
		return _host_status
	if _ready_file != "" and FileAccess.file_exists(_ready_file):
		var text := FileAccess.get_file_as_string(_ready_file)
		var r = JSON.parse_string(text)
		if typeof(r) == TYPE_DICTIONARY:
			_host_status = r
			_host_status["state"] = "ready"
			port = int(r.get("port", DEFAULT_PORT))
			return _host_status
	if _host_pid > 0 and not OS.is_process_running(_host_pid):
		_host_status = {"state": "failed", "error": "the Python host exited (exit code %d)" % OS.get_process_exit_code(_host_pid)}
	return _host_status


func stop_local_host() -> void:
	if Engine.has_singleton("DmbPySim"):
		Engine.get_singleton("DmbPySim").stop()
	elif _host_pid > 0:
		OS.kill(_host_pid)
	_host_pid = -1
	_host_status = {"state": "idle"}
	if _ready_file != "" and FileAccess.file_exists(_ready_file):
		DirAccess.remove_absolute(_ready_file)
	_ready_file = ""


func _hybrid_dir() -> String:
	var candidates: PackedStringArray = []
	var env := OS.get_environment("DMB_HYBRID_DIR")
	if env != "":
		candidates.append(env)
	candidates.append(ProjectSettings.globalize_path("res://").path_join("../WizardRTSHybrid"))
	candidates.append(OS.get_executable_path().get_base_dir().path_join("WizardRTSHybrid"))
	for c in candidates:
		if DirAccess.dir_exists_absolute(c) and FileAccess.file_exists(c.path_join("wizard_rts/net/host.py")):
			return c
	return ""


## The local network addresses a joining phone could type.
func local_addresses() -> PackedStringArray:
	var out: PackedStringArray = []
	for a in IP.get_local_addresses():
		var s := str(a)
		if s.contains(":") or s.begins_with("127.") or s.begins_with("169.254."):
			continue
		out.append(s)
	return out


## Connect a sim client to the host and authenticate. Returns the hello reply; on success `sim` is kept for the world.
func connect_and_hello(address: String, port_: int, code: String, name: String, secret: String = "", reconnect_token: String = "") -> Dictionary:
	var c = SimClient.new()
	if not c.connect_to_host(address, port_, 4000):
		last_error = "no_host" if c.last_error == "refused" else c.last_error
		return {"status": "rejected", "reason": last_error}
	var msg := {"op": "hello", "protocol": PROTOCOL_VERSION, "game": GAME_VERSION, "name": name, "code": code}
	if secret != "":
		msg["secret"] = secret
	if reconnect_token != "":
		msg["token"] = reconnect_token
	var reply: Dictionary = c.op(msg, 8000)
	if str(reply.get("status", "")) != "ok":
		last_error = str(reply.get("reason", "rejected"))
		c.disconnect_from_host()
		return reply
	if sim != null and sim != c:
		sim.disconnect_from_host()
	sim = c
	host_address = address
	port = port_
	join_code = code
	player_name = name
	token = str(reply.get("token", ""))
	player_id = str(reply.get("player_id", ""))
	is_host = bool(reply.get("host", false))
	session_name = str(reply.get("session", {}).get("name", session_name))
	seed = int(reply.get("seed", seed))
	map_size = str(reply.get("map", map_size))
	return reply


static func describe_error(reason: String) -> String:
	match reason:
		"bad_code":
			return "Wrong join code."
		"protocol_mismatch", "version_mismatch":
			return "The host runs a different game version. Update both phones to the same version."
		"full":
			return "That game is full."
		"no_host", "refused":
			return "No game is answering at that address. Check the host is still on the Host screen and both phones are on the same Wi-Fi."
		"timeout":
			return "The host did not answer in time. Some Wi-Fi networks block phone-to-phone traffic (guest or 'client isolation' modes); try a hotspot."
		"no_spawn_tile":
			return "The host could not find a free tile next to its wizard."
		"disconnected":
			return "The connection to the host was lost."
	return "Could not join: %s" % reason


func _notification(what: int) -> void:
	if what == NOTIFICATION_WM_CLOSE_REQUEST or what == NOTIFICATION_PREDELETE:
		stop_local_host()  # a desktop python host must not outlive the window; on Android the plugin's thread ends with the app
