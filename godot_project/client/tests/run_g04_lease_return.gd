extends SceneTree

## G04 leased hazard duel Continueturn: Continue UI path tears board down once.

const HazardShell = preload("res://client/scenes/g04_hazard_shell.gd")


func _init() -> void:
	call_deferred("_go")


func _go() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-HAZARD")
	OS.set_environment("DMB_SEED", "408")
	OS.set_environment("DMB_SAVE_SLOT", "g04_hazard")
	DisplayServer.window_set_size(Vector2i(1280, 720))
	var hazard: Control = HazardShell.new()
	root.add_child(hazard)
	await create_timer(2.2).timeout
	if hazard._client == null:
		push_error("lease return: hazard shell failed")
		quit(1)
		return
	var deadline := Time.get_ticks_msec() + 5000
	while Time.get_ticks_msec() < deadline and hazard._hex_nodes.size() < 3:
		await create_timer(0.2).timeout
	if hazard._hex_nodes.size() < 3:
		push_error("lease return: expected 3 hazard cubes")
		quit(1)
		return

	var cube_id := str(hazard._hex_nodes.keys()[0])
	var clock_before: Dictionary = hazard._client.request_view("player", ["clock"]).get("clock", {})
	var paused_before := bool(clock_before.get("paused", false))

	hazard._on_duel_requested(cube_id)
	await create_timer(0.55).timeout
	if hazard._duel_id == "" or hazard._duel_adapter == null or not hazard._duel_adapter.is_active():
		push_error("lease return: duel did not start")
		quit(1)
		return
	var board = hazard._duel_adapter._board
	if board == null or not is_instance_valid(board):
		push_error("lease return: GameBoard missing")
		quit(1)
		return

	# Menu escape path must offer abandon, not Restart/Quit-to-menu.
	board._show_menu_overlay()
	await process_frame
	var menu_labels: Array = board.ui_overlay_button_labels()
	if not menu_labels.has("Abandon challenge"):
		push_error("lease return: menu missing Abandon challenge, got %s" % menu_labels)
		quit(1)
		return
	if menu_labels.has("Restart duel") or menu_labels.has("Quit to menu"):
		push_error("lease return: lease menu still offers standalone escape %s" % menu_labels)
		quit(1)
		return
	board.ui_dismiss_overlay()

	# Finish duel and press Continue (same path as the result overlay button).
	board.ui_debug_finish_duel("victory")
	# Result overlay appears after a short delay unless screenshot mode.
	var wait_result := Time.get_ticks_msec() + 2500
	while Time.get_ticks_msec() < wait_result and not board.ui_is_result_visible():
		await create_timer(0.1).timeout
	if not board.ui_is_result_visible():
		# Force visible for headless timing races.
		if board.get("_overlay") != null:
			board._overlay.visible = true
		await process_frame
	var result_labels: Array = board.ui_overlay_button_labels()
	if not result_labels.has("Continue"):
		push_error("lease return: result missing Continue, got %s" % result_labels)
		quit(1)
		return
	if result_labels.has("Play again"):
		push_error("lease return: lease result still offers Play again")
		quit(1)
		return

	var finished_before: int = hazard._duel_adapter.finished_emit_count
	var resolve_before: int = hazard._duel_adapter.resolve_submit_count
	var lease_duel_id := str(hazard._duel_id)
	if not board.ui_pointer_press_overlay_button("Continue"):
		push_error("lease return: Continue press failed")
		quit(1)
		return
	await create_timer(0.45).timeout

	if hazard._duel_adapter.finished_emit_count != finished_before + 1:
		push_error("lease return: finished callback count=%s expected %s" % [
			hazard._duel_adapter.finished_emit_count, finished_before + 1
		])
		quit(1)
		return
	if hazard._duel_adapter.resolve_submit_count != resolve_before + 1:
		push_error("lease return: ResolveHazardDuel count=%s expected %s" % [
			hazard._duel_adapter.resolve_submit_count, resolve_before + 1
		])
		quit(1)
		return
	# Idempotent second resolve must not mutate again / must not re-fire adapter.
	var dup: Dictionary = hazard._cmd("ResolveHazardDuel", {
		"duel_id": lease_duel_id,
		"success": true,
	})
	if hazard._duel_adapter.resolve_submit_count != resolve_before + 1:
		push_error("lease return: adapter re-submitted resolve after Continue")
		quit(1)
		return
	if hazard._duel_id != "":
		push_error("lease return: shell _duel_id not cleared")
		quit(1)
		return
	if hazard._duel_adapter.is_active():
		push_error("lease return: GameBoard still active after Continue")
		quit(1)
		return
	if hazard._duel_adapter._board != null and is_instance_valid(hazard._duel_adapter._board):
		push_error("lease return: GameBoard not torn down")
		quit(1)
		return
	if hazard._duel_host != null and hazard._duel_host.visible:
		push_error("lease return: DuelHost still visible")
		quit(1)
		return
	if hazard._area == null or not hazard._area.movement_enabled:
		push_error("lease return: movement not re-enabled")
		quit(1)
		return

	var view: Dictionary = hazard._client.request_view(
		"player", ["hazards", "fx_hazard", "player", "clock", "board", "leases"]
	)
	var cubes: Dictionary = view.get("hazards", {}).get("catastrophe", {}).get("cubes", {})
	if cubes.has(cube_id) and bool(cubes[cube_id].get("active", true)):
		push_error("lease return: victory must remove challenged cube %s" % cube_id)
		quit(1)
		return
	var still_active := 0
	for cid in cubes.keys():
		if bool(cubes[cid].get("active", true)):
			still_active += 1
	if still_active != 2:
		push_error("lease return: expected exactly 2 remaining cubes, got %s" % still_active)
		quit(1)
		return

	var clock_after: Dictionary = view.get("clock", {})
	if bool(clock_after.get("paused", false)) and not paused_before:
		var tokens = clock_after.get("pause_tokens", {})
		if typeof(tokens) == TYPE_DICTIONARY and bool(tokens.get("hazard_duel", false)):
			push_error("lease return: Game Time still held by hazard_duel pause")
			quit(1)
			return

	if hazard._duel_adapter.is_active() or hazard._duel_id != "":
		push_error("lease return: second duel started automatically")
		quit(1)
		return

	print("G04_LEASE_RETURN_OK cube=", cube_id, " dup_status=", dup.get("status", dup.get("payload", {})))
	print("G04_LEASE_RETURN_OK")
	if is_instance_valid(hazard):
		hazard.queue_free()
	quit(0)
