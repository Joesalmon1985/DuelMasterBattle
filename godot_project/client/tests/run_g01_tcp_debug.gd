extends SceneTree

const Migrated = preload("res://client/core/migrated_runtime.gd")
const Codec = preload("res://client/bridge/frame_codec.gd")

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	Migrated.enable()
	var launcher = load("res://client/bridge/sidecar_launcher.gd").new()
	root.add_child(launcher)
	var project_root := ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
	if project_root.ends_with("godot_project"):
		project_root = project_root.get_base_dir()
	print("PROJECT_ROOT=", project_root)
	var started: Dictionary = launcher.start(project_root)
	print("STARTED=", started)
	if not started.get("ok", false):
		quit(1)
		return
	var peer := StreamPeerTCP.new()
	var err := peer.connect_to_host(str(started["host"]), int(started["port"]))
	print("CONNECT_ERR=", err)
	for i in range(50):
		peer.poll()
		print("STATUS=", peer.get_status())
		if peer.get_status() == StreamPeerTCP.STATUS_CONNECTED:
			break
		OS.delay_msec(50)
	var codec := Codec.new()
	var hs := {
		"kind": "Handshake",
		"protocol_version": 1,
		"session_id": "dbg",
		"token": str(started["token"]),
		"role": "local_client",
	}
	var frame: PackedByteArray = codec.encode(hs)
	print("FRAME_LEN=", frame.size(), " HEAD=", frame[0], frame[1], frame[2], frame[3])
	peer.poll()
	var put_err := peer.put_data(frame)
	print("PUT=", put_err)
	for i in range(50):
		peer.poll()
		var avail := peer.get_available_bytes()
		print("AVAIL=", avail, " STATUS=", peer.get_status())
		if avail > 0:
			var got := peer.get_data(avail)
			print("GET_ERR=", got[0], " BYTES=", got[1].size())
			var frames: Array = codec.feed(got[1])
			print("FRAMES=", frames)
			break
		OS.delay_msec(50)
	launcher.stop()
	quit(0)
