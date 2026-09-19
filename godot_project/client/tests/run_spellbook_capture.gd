extends SceneTree

## Headless environments cannot sample viewport textures (dummy renderer).
## Prefer docs/spellbook_captures offline composites; this script verifies the
## book opens at multiple window sizes under project stretch without crashing.

const Migrated = preload("res://client/core/migrated_runtime.gd")
const Model = preload("res://client/ui/spellbook/spellbook_model.gd")


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	Migrated.enable()
	OS.set_environment("DMB_FIXTURE", "FX-CLOCK")
	OS.set_environment("DMB_SEED", "7")
	ProjectSettings.set_setting("dmb/spellbook/text_scale", 1.25)
	var err := change_scene_to_file("res://client/scenes/g01_shell.tscn")
	if err != OK:
		push_error("load failed")
		quit(1)
		return
	await create_timer(2.5).timeout
	var shell = root.get_children().back()
	if shell == null or shell.get("_spell_model") == null:
		push_error("no spellbook")
		quit(1)
		return
	var model = shell._spell_model
	model.open_book()
	model.goto_page(1)  # Actions
	await create_timer(0.4).timeout
	var sizes := [
		Vector2i(360, 800),
		Vector2i(390, 844),
		Vector2i(720, 1280),
		Vector2i(1280, 720),
	]
	for sz in sizes:
		DisplayServer.window_set_size(sz)
		await create_timer(0.25).timeout
		if model.host_mode != Model.HostMode.OPEN:
			push_error("book closed unexpectedly at %s" % sz)
			quit(1)
			return
		print("layout_ok window=", sz, " viewport=", get_root().get_viewport().get_visible_rect().size)
	# Long-text stress (no GPU capture — dummy renderer cannot sample textures).
	model.set_live(
		"Long status line for readability checks across mobile widths and scaled fonts.",
		"World Turn: 12 | Game Time: 123456 ms (123.5s) | Node: node:warehouse_north | paused=false",
		"Prompt with an extended explanation of the last Travel acknowledgement including facing and coordinates.",
		false
	)
	model.append_log("detail log line " + "x".repeat(60))
	model.goto_page(3)
	await create_timer(0.2).timeout
	print("SPELLBOOK_CAPTURE_OK logical_stretch_verified")
	if shell.get("_launcher") != null:
		shell._launcher.stop()
	OS.delay_msec(100)
	quit(0)
