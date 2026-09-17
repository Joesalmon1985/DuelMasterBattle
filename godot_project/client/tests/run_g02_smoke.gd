extends SceneTree

## Headless G02 FX-CARGO smoke: sidecar with fixture, economy view fields, quit.

const Migrated = preload("res://client/core/migrated_runtime.gd")


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	Migrated.enable()
	OS.set_environment("DMB_FIXTURE", "FX-CARGO")
	OS.set_environment("DMB_SEED", "202")
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
	var view: Dictionary = client.request_view("economy")
	var fx: Dictionary = view.get("fx_cargo", {})
	if int(fx.get("seed", 0)) != 202:
		push_error("expected FX-CARGO seed 202, got %s" % fx)
		launcher.stop()
		quit(1)
		return
	if str(fx.get("cart_id", "")) == "":
		push_error("missing cart_id in fx_cargo")
		launcher.stop()
		quit(1)
		return
	if not view.has("stocks") or not view.has("carts"):
		push_error("economy view missing stocks/carts")
		launcher.stop()
		quit(1)
		return
	print("G02_SMOKE_OK seed=", fx.get("seed"), " cart=", fx.get("cart_id"), " store=", fx.get("store"))
	launcher.stop()
	OS.delay_msec(100)
	quit(0)
