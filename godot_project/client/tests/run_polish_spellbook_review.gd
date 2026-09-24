extends SceneTree

## Smoke: g05 spellbook opens/closes in review mode (headless-friendly).
## godot --headless --path godot_project --script res://client/tests/run_polish_spellbook_review.gd

const Shell = preload("res://client/scenes/g05_shell.gd")
const Model = preload("res://client/ui/spellbook/spellbook_model.gd")
const ReviewBinder = preload("res://client/ui/spellbook/spellbook_review_binder.gd")


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	OS.set_environment("DMB_PLAYTEST_REVIEW", "1")
	OS.set_environment("DMB_FIXTURE", "FX-MVP")
	OS.set_environment("DMB_SEED", "507")
	OS.set_environment("DMB_SAVE_SLOT", "g05_visual_review")
	OS.set_environment("DMB_REDUCED_MOTION", "1")
	var shell: Control = Shell.new()
	root.add_child(shell)
	var deadline := Time.get_ticks_msec() + 15000
	while Time.get_ticks_msec() < deadline and not shell.is_booted():
		await process_frame
	if not shell.is_booted():
		push_error("polish spellbook review: shell boot timeout")
		print("POLISH_SPELLBOOK_REVIEW_FAIL boot")
		quit(1)
		return
	var model = shell.spellbook_model()
	var host = shell.spellbook_host()
	if model == null or host == null:
		push_error("polish spellbook review: host/model missing")
		print("POLISH_SPELLBOOK_REVIEW_FAIL host")
		quit(1)
		return
	if not ReviewBinder.review_enabled():
		push_error("polish spellbook review: review flag not active")
		print("POLISH_SPELLBOOK_REVIEW_FAIL flag")
		quit(1)
		return
	deadline = Time.get_ticks_msec() + 5000
	while Time.get_ticks_msec() < deadline and model.conn_state != Model.ConnState.READY:
		await process_frame
	var has_review := false
	for p in model.pages:
		if str(p.get("id", "")) == "review":
			has_review = true
			break
	if not has_review:
		push_error("polish spellbook review: missing Review page")
		print("POLISH_SPELLBOOK_REVIEW_FAIL pages")
		quit(1)
		return
	shell.invoke_spellbook_for_test()
	await create_timer(0.35).timeout
	if model.host_mode != Model.HostMode.OPEN:
		push_error("polish spellbook review: book did not open (mode=%s)" % model.host_mode)
		print("POLISH_SPELLBOOK_REVIEW_FAIL open")
		quit(1)
		return
	model.close_book()
	await create_timer(0.2).timeout
	if model.host_mode != Model.HostMode.COMPACT:
		push_error("polish spellbook review: book did not close")
		print("POLISH_SPELLBOOK_REVIEW_FAIL close")
		quit(1)
		return
	print("POLISH_SPELLBOOK_REVIEW_OK")
	quit(0)
