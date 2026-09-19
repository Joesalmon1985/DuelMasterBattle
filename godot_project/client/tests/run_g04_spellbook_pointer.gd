extends SceneTree

## G04 real pointer-input spellbook regression (not model.open_book shortcuts).
## Portrait + landscape including 1280×720.

const BattleShell = preload("res://client/scenes/g04_battle_shell.gd")
const Model = preload("res://client/ui/spellbook/spellbook_model.gd")

var _sizes: Array = [
	Vector2i(450, 800),
	Vector2i(720, 1280),
	Vector2i(1280, 720),
]


func _init() -> void:
	call_deferred("_go")


func _go() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-BATTLE")
	OS.set_environment("DMB_SEED", "404")
	OS.set_environment("DMB_SAVE_SLOT", "g04_battle")
	OS.set_environment("DMB_REDUCED_MOTION", "1")
	for sz in _sizes:
		var ok: bool = await _run_at_size(sz)
		if not ok:
			quit(1)
			return
	print("G04_SPELLBOOK_POINTER_OK sizes=", _sizes.size())
	quit(0)


func _run_at_size(sz: Vector2i) -> bool:
	DisplayServer.window_set_size(sz)
	for _i in range(4):
		await process_frame
	var battle: Control = BattleShell.new()
	root.add_child(battle)
	await create_timer(2.4).timeout
	var deadline := Time.get_ticks_msec() + 6000
	while Time.get_ticks_msec() < deadline and (battle._client == null or not battle._lease_opened \
			or battle._spell_host == null or battle._spell_model == null):
		await create_timer(0.15).timeout
	if battle._client == null or not battle._lease_opened:
		push_error("spellbook pointer: battle lease not ready at %s" % sz)
		_shutdown(battle)
		return false
	var model = battle._spell_model
	var host = battle._spell_host
	if model == null or host == null:
		push_error("spellbook pointer: host/model missing at %s" % sz)
		_shutdown(battle)
		return false
	deadline = Time.get_ticks_msec() + 3000
	while Time.get_ticks_msec() < deadline and model.conn_state != Model.ConnState.READY:
		await create_timer(0.1).timeout

	var open_btn: Button = host.compact_open_button()
	if open_btn == null or not open_btn.is_visible_in_tree():
		push_error("spellbook pointer: Open Spellbook not visible at %s" % sz)
		_shutdown(battle)
		return false
	await _click(open_btn)
	await create_timer(0.3).timeout
	if model.host_mode != Model.HostMode.OPEN:
		push_error("spellbook pointer: book did not open via pointer at %s (mode=%s)" % [sz, model.host_mode])
		_shutdown(battle)
		return false
	host._layout_art_slots()
	await process_frame
	await process_frame

	var panel: Rect2 = host.open_panel_rect()
	var vp: Vector2 = battle.get_viewport_rect().size
	if panel.size.x <= 8.0 or panel.size.y <= 8.0:
		push_error("spellbook pointer: open panel has no size at %s" % sz)
		_shutdown(battle)
		return false
	var cover := (panel.size.x * panel.size.y) / maxf(1.0, vp.x * vp.y)
	if cover > 0.82:
		push_error("spellbook pointer: panel still too full-screen at %s cover=%.2f" % [sz, cover])
		_shutdown(battle)
		return false
	if battle._touch != null and battle._touch.visible:
		push_error("spellbook pointer: touch pad still visible over open book at %s" % sz)
		_shutdown(battle)
		return false

	if str(model.current_page().get("id", "")) != "spells":
		var tab := _find_button(host, "Spells")
		if tab != null:
			await _click(tab)
			await create_timer(0.2).timeout
			host._layout_art_slots()
			await process_frame

	var shield := _find_button(host, "Shield")
	if shield == null:
		push_error("spellbook pointer: Shield button missing at %s" % sz)
		_shutdown(battle)
		return false
	await _click(shield)
	await create_timer(0.3).timeout
	if model.host_mode != Model.HostMode.TARGETING:
		push_error("spellbook pointer: Shield did not enter TARGETING at %s (mode=%s hover=%s)" % [
			sz, model.host_mode, root.gui_get_hovered_control()
		])
		_shutdown(battle)
		return false
	if host.is_blocking_world() or (host._open_root != null and host._open_root.visible):
		push_error("spellbook pointer: book still obscuring world after Shield at %s" % sz)
		_shutdown(battle)
		return false

	var cancel := _find_button(host, "Cancel targeting")
	if cancel == null:
		push_error("spellbook pointer: Cancel targeting missing at %s" % sz)
		_shutdown(battle)
		return false
	await _click(cancel)
	await create_timer(0.25).timeout
	if model.host_mode != Model.HostMode.COMPACT:
		push_error("spellbook pointer: cancel did not restore COMPACT at %s" % sz)
		_shutdown(battle)
		return false

	open_btn = host.compact_open_button()
	if open_btn == null or not open_btn.visible:
		push_error("spellbook pointer: Open Spellbook missing after cancel at %s" % sz)
		_shutdown(battle)
		return false
	await _click(open_btn)
	await create_timer(0.3).timeout
	if model.host_mode != Model.HostMode.OPEN:
		push_error("spellbook pointer: reopen failed at %s" % sz)
		_shutdown(battle)
		return false

	var close_btn: Button = host.panel_close_button()
	if close_btn == null or not close_btn.visible:
		close_btn = _find_button(host, "Close book")
	if close_btn == null:
		push_error("spellbook pointer: Close book missing at %s" % sz)
		_shutdown(battle)
		return false
	await _click(close_btn)
	await create_timer(0.3).timeout
	if model.host_mode != Model.HostMode.COMPACT:
		push_error("spellbook pointer: Close did not restore COMPACT at %s" % sz)
		_shutdown(battle)
		return false
	if battle._touch != null and not battle._touch.visible:
		push_error("spellbook pointer: touch pad not restored after close at %s" % sz)
		_shutdown(battle)
		return false

	print("G04_SPELLBOOK_POINTER_SIZE_OK ", sz)
	_shutdown(battle)
	await create_timer(0.45).timeout
	return true


func _find_button(node: Node, text: String) -> Button:
	if node is Button and str((node as Button).text) == text and (node as Button).is_visible_in_tree():
		return node as Button
	for child in node.get_children():
		var found := _find_button(child, text)
		if found != null:
			return found
	return null


func _click(ctrl: Control) -> void:
	## Canvas-local press/release (in_local_coords) — headless window size is often 0.
	var pos := ctrl.get_global_rect().get_center()
	var motion := InputEventMouseMotion.new()
	motion.position = pos
	motion.global_position = pos
	root.push_input(motion, true)
	await process_frame
	var press := InputEventMouseButton.new()
	press.button_index = MOUSE_BUTTON_LEFT
	press.pressed = true
	press.position = pos
	press.global_position = pos
	press.button_mask = MOUSE_BUTTON_MASK_LEFT
	root.push_input(press, true)
	await process_frame
	var release := InputEventMouseButton.new()
	release.button_index = MOUSE_BUTTON_LEFT
	release.pressed = false
	release.position = pos
	release.global_position = pos
	root.push_input(release, true)
	await process_frame


func _shutdown(shell: Node) -> void:
	if shell != null and is_instance_valid(shell):
		shell.queue_free()
