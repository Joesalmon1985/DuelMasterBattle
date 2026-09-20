extends SceneTree

## G05 smoke — boot FX-VILLAGE shell with Python sidecar.
## godot --headless --path godot_project --script res://client/tests/run_g05_smoke.gd

const Shell = preload("res://client/scenes/g05_shell.gd")


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-VILLAGE")
	OS.set_environment("DMB_SEED", "507")
	var shell = Shell.new()
	root.add_child(shell)
	var deadline := Time.get_ticks_msec() + 12000
	while Time.get_ticks_msec() < deadline and not shell.is_booted():
		await process_frame
	if not shell.is_booted():
		push_error("G05 shell failed to boot")
		print("G05_SMOKE_FAIL")
		quit(1)
		return
	print("G05_SMOKE_OK")
	quit(0)
