extends Node
class_name DmbSidecarLauncher

## Starts the Python sidecar with a fresh token and reads the endpoint file.

signal launched(host: String, port: int, token: String)
signal failed(message: String)

var pid: int = -1
var token: String = ""
var endpoint_path: String = ""


func start(project_root: String) -> Dictionary:
	token = "%s-%s" % [Time.get_unix_time_from_system(), randi()]
	endpoint_path = project_root.path_join(".dmb_endpoint.json")
	var save_root := project_root.path_join(".dmb_saves")
	# Remove stale endpoint so we never connect to a previous sidecar port.
	if FileAccess.file_exists(endpoint_path):
		DirAccess.remove_absolute(endpoint_path)
	# Prefer an explicit interpreter from the Windows playtest launcher (or CI).
	var python := str(OS.get_environment("DMB_PYTHON")).strip_edges()
	if python == "":
		python = "python3"
		if OS.get_name() == "Windows":
			python = "python"
	var script := project_root.path_join("tools/run_sidecar.py")
	var args := PackedStringArray([
		script,
		"--token", token,
		"--save-root", save_root,
		"--endpoint-file", endpoint_path,
	])
	var fixture := str(OS.get_environment("DMB_FIXTURE"))
	var seed := str(OS.get_environment("DMB_SEED"))
	if fixture != "":
		args.append("--fixture")
		args.append(fixture)
	if seed != "":
		args.append("--seed")
		args.append(seed)
	pid = OS.create_process(python, args)
	if pid <= 0 and not str(OS.get_environment("DMB_PYTHON")).strip_edges().is_empty():
		# Absolute DMB_PYTHON failed; fall back to PATH names.
		pid = OS.create_process("python", args)
		if pid <= 0:
			pid = OS.create_process("python3", args)
	elif pid <= 0 and python == "python":
		pid = OS.create_process("python3", args)
	elif pid <= 0 and python == "python3":
		pid = OS.create_process("python", args)
	if pid <= 0:
		failed.emit("failed to start python sidecar")
		return {"ok": false, "error": "spawn_failed"}
	for _i in range(100):
		OS.delay_msec(50)
		if FileAccess.file_exists(endpoint_path):
			var raw := FileAccess.get_file_as_string(endpoint_path)
			if raw.strip_edges() == "":
				continue
			var data = JSON.parse_string(raw)
			if typeof(data) == TYPE_DICTIONARY and int(data.get("port", 0)) > 0:
				var ep_token := str(data.get("token", ""))
				if ep_token != "" and ep_token != token:
					continue
				launched.emit(str(data["host"]), int(data["port"]), ep_token if ep_token != "" else token)
				return {
					"ok": true,
					"host": data["host"],
					"port": int(data["port"]),
					"token": ep_token if ep_token != "" else token,
					"pid": pid,
				}
	failed.emit("sidecar endpoint timeout")
	return {"ok": false, "error": "timeout"}


func stop() -> void:
	if pid > 0:
		OS.kill(pid)
		pid = -1
	if endpoint_path != "" and FileAccess.file_exists(endpoint_path):
		DirAccess.remove_absolute(endpoint_path)
