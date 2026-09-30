extends SceneTree

## Visual Sim QA kernel runner (Godot side).
## Env:
##   DMB_VISUAL_SIM_OUT   — output run directory (required)
##   DMB_FIXTURE / DMB_SEED / DMB_SAVE_SLOT
##   DMB_VISUAL_SIM_MODE — smoke|slice_a|slice_b (default smoke)

const Driver = preload("res://client/tests/auto_gate_driver.gd")
const Harvester = preload("res://client/tests/visual_sim_harvester.gd")

var _driver

func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var out_dir := OS.get_environment("DMB_VISUAL_SIM_OUT").strip_edges()
	if out_dir == "":
		push_error("DMB_VISUAL_SIM_OUT required")
		_finish(2)
		return
	DirAccess.make_dir_recursive_absolute(out_dir)
	DirAccess.make_dir_recursive_absolute(out_dir.path_join("shots"))
	DirAccess.make_dir_recursive_absolute(out_dir.path_join("render"))
	var fixture := OS.get_environment("DMB_FIXTURE")
	if fixture == "":
		fixture = "FX-MVP"
	var seed := int(OS.get_environment("DMB_SEED")) if OS.get_environment("DMB_SEED") != "" else 507
	var mode := OS.get_environment("DMB_VISUAL_SIM_MODE")
	if mode == "":
		mode = "smoke"
	_driver = Driver.new(self)
	var ok: bool = await _driver.launch_fixture("VISUAL_SIM", fixture, seed, "visual_sim_%s" % mode)
	if not ok:
		_write_json(out_dir.path_join("render/boot_failed.json"), {"error": "boot_failed", "errors": _driver.script_errors})
		print("VISUAL_SIM_KERNEL_FAIL boot")
		_finish(1)
		return
	var res := OS.get_environment("DMB_RESOLUTION")
	if res != "":
		var parts := res.split("x")
		if parts.size() == 2:
			await _driver.force_size(Vector2i(int(parts[0]), int(parts[1])))
	await _driver.wait_state(func(): return _driver.shell != null and _driver.shell.is_booted(), 30000, "booted")
	var waits := int(OS.get_environment("DMB_VISUAL_SIM_WAITS")) if OS.get_environment("DMB_VISUAL_SIM_WAITS") != "" else 0
	for i in range(waits):
		if _driver.shell.has_method("invoke_fx_era_wait_for_test"):
			_driver.shell.invoke_fx_era_wait_for_test()
		await process_frame
	var harvest: Dictionary = Harvester.harvest(_driver.shell)
	_write_json(out_dir.path_join("render/harvest.json"), harvest)
	await process_frame
	await process_frame
	var vp: Viewport = get_root().get_viewport()
	var tex: ViewportTexture = vp.get_texture()
	var img: Image = null
	if tex != null:
		img = tex.get_image()
	var shot_name := "SMOKE_BOOT.png"
	var shot_path := out_dir.path_join("shots").path_join(shot_name)
	var err := FAILED
	var w := 0
	var h := 0
	if img != null:
		w = img.get_width()
		h = img.get_height()
		shot_name = "SMOKE_BOOT_%dx%d.png" % [w, h]
		shot_path = out_dir.path_join("shots").path_join(shot_name)
		err = img.save_png(shot_path)
	var meta := {
		"capture_id": "SMOKE_BOOT",
		"path": shot_path,
		"width": w,
		"height": h,
		"save_error": err,
		"entity_count": harvest.get("entity_count", 0),
		"scenario_mode": mode,
	}
	_write_json(out_dir.path_join("shots/SMOKE_BOOT.json"), meta)
	# Tear down shell/sidecar before quit so the process can exit.
	_teardown()
	if err != OK or int(harvest.get("entity_count", 0)) < 1:
		print("VISUAL_SIM_KERNEL_FAIL capture_or_harvest err=%s entities=%s" % [err, harvest.get("entity_count")])
		_finish(1)
		return
	print("VISUAL_SIM_KERNEL_OK entities=%s shot=%s" % [harvest.get("entity_count"), shot_name])
	_finish(0)


func _teardown() -> void:
	if _driver == null:
		return
	var shell = _driver.shell
	if shell != null and is_instance_valid(shell):
		if shell.get("_launcher") != null and shell._launcher.has_method("stop"):
			shell._launcher.stop()
		shell.queue_free()
	_driver.shell = null


func _finish(code: int) -> void:
	await process_frame
	quit(code)


func _write_json(path: String, data: Dictionary) -> void:
	var f := FileAccess.open(path, FileAccess.WRITE)
	if f == null:
		push_error("cannot write %s" % path)
		return
	f.store_string(JSON.stringify(data, "\t"))
	f.close()
