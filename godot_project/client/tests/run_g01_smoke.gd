extends SceneTree

## Headless G01 sidecar smoke: launch, view, quit, no orphan process.

const Migrated = preload("res://client/core/migrated_runtime.gd")

func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	Migrated.enable()
	var launcher = load("res://client/bridge/sidecar_launcher.gd").new()
	root.add_child(launcher)
	var project_root := ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
	if project_root.ends_with("godot_project"):
		project_root = project_root.get_base_dir()
	var started: Dictionary = launcher.start(project_root)
	if not started.get("ok", false):
		push_error("sidecar start failed: %s" % started)
		quit(1)
		return
	var client = load("res://client/bridge/world_client.gd").new()
	root.add_child(client)
	OS.delay_msec(100)
	if not client.connect_sidecar(str(started["host"]), int(started["port"]), str(started["token"])):
		push_error("handshake failed")
		launcher.stop()
		quit(1)
		return
	var view: Dictionary = client.request_view("player")
	if str(view.get("world_id", "")) == "":
		push_error("empty view: %s" % view)
		launcher.stop()
		quit(1)
		return
	if not client.legacy_writers_blocked():
		push_error("legacy writers not blocked")
		launcher.stop()
		quit(1)
		return
	print("G01_SMOKE_OK world_id=", view.get("world_id"))
	launcher.stop()
	OS.delay_msec(100)
	quit(0)
