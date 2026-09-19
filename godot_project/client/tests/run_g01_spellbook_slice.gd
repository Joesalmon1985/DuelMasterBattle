extends SceneTree

## G01 spellbook slice: load shell, open book, Wait via binder, assert ack result.

const Migrated = preload("res://client/core/migrated_runtime.gd")
const Model = preload("res://client/ui/spellbook/spellbook_model.gd")


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	Migrated.enable()
	OS.set_environment("DMB_FIXTURE", "FX-CLOCK")
	OS.set_environment("DMB_SEED", "7")
	var err := change_scene_to_file("res://client/scenes/g01_shell.tscn")
	if err != OK:
		push_error("failed to load g01_shell: %s" % err)
		quit(1)
		return
	await create_timer(2.5).timeout
	var shell = root.get_child(root.get_child_count() - 1)
	if shell == null or not shell.has_method("_setup_spellbook"):
		# Scene root may be the shell Control itself.
		shell = root.get_children().back()
	if shell == null or shell.get("_spell_model") == null:
		push_error("spellbook model missing on shell")
		quit(1)
		return
	var model = shell._spell_model
	var binder = shell._spell_binder
	if model.conn_state != Model.ConnState.READY and model.conn_state != Model.ConnState.ERROR:
		# Allow ready; if still loading wait more
		await create_timer(2.0).timeout
	if model.conn_state != Model.ConnState.READY:
		push_error("spellbook not ready: %s %s" % [model.conn_state, model.error_reason])
		_shutdown(shell)
		quit(1)
		return
	model.open_book()
	if model.host_mode != Model.HostMode.OPEN:
		push_error("book failed to open")
		_shutdown(shell)
		quit(1)
		return
	var token_box: Array = []
	model.action_requested.connect(func(a, p, t): token_box.append([a, p, t]), CONNECT_ONE_SHOT)
	# Drive through binder the same way the UI does.
	model.request_action("wait", {})
	await create_timer(0.1).timeout
	if token_box.is_empty():
		push_error("wait did not emit action_requested")
		_shutdown(shell)
		quit(1)
		return
	binder.handle_action(token_box[0][0], token_box[0][1], token_box[0][2])
	await create_timer(0.5).timeout
	if model.result_kind != Model.ResultKind.SUCCESS and model.result_kind != Model.ResultKind.REJECTED:
		push_error("expected terminal result, got %s (%s)" % [model.result_kind, model.result_text])
		_shutdown(shell)
		quit(1)
		return
	if model.result_token != token_box[0][2]:
		push_error("result token mismatch")
		_shutdown(shell)
		quit(1)
		return
	model.close_book()
	if model.host_mode != Model.HostMode.COMPACT:
		push_error("book failed to close")
		_shutdown(shell)
		quit(1)
		return
	print("G01_SPELLBOOK_SLICE_OK result=", model.result_text)
	_shutdown(shell)
	quit(0)


func _shutdown(shell) -> void:
	if shell != null and shell.has_method("_exit_tree"):
		if shell.get("_launcher") != null:
			shell._launcher.stop()
	OS.delay_msec(150)
