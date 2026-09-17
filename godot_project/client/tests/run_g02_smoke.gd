extends SceneTree

## G02 playable smoke: real g02_shell scene, pointer press/release through the
## viewport for movement + Wait, FX-CARGO block/resume/save via Interact commands.

const Migrated = preload("res://client/core/migrated_runtime.gd")
const G02Shell = preload("res://client/scenes/g02_shell.gd")


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	Migrated.enable()
	OS.set_environment("DMB_FIXTURE", "FX-CARGO")
	OS.set_environment("DMB_SEED", "202")
	DisplayServer.window_set_size(Vector2i(450, 800))

	var shell: Control = G02Shell.new()
	root.add_child(shell)
	# Allow sidecar handshake + scene build.
	for _i in range(90):
		await process_frame
		if shell._client != null and shell._area != null and shell._touch != null:
			var view: Dictionary = shell._client.request_view("economy")
			if int(view.get("fx_cargo", {}).get("seed", 0)) == 202:
				break
	if shell._client == null or shell._area == null:
		push_error("g02 shell failed to boot sidecar/area")
		_shutdown(shell, 1)
		return

	shell._force_playable_focus()
	await process_frame

	var economy: Dictionary = shell._client.request_view("economy")
	var fx: Dictionary = economy.get("fx_cargo", {})
	if int(fx.get("seed", 0)) != 202 or str(fx.get("cart_id", "")) == "":
		push_error("FX-CARGO economy view incomplete: %s" % fx)
		_shutdown(shell, 1)
		return
	if not economy.has("stocks") or not economy.has("carts"):
		push_error("economy view missing stocks/carts")
		_shutdown(shell, 1)
		return
	var people: Dictionary = shell._client.request_view("player").get("people", {})
	if not people.has("person:warehouse") or not people.has("person:cart"):
		push_error("warehouse/cart people missing from player view")
		_shutdown(shell, 1)
		return

	# Pointer movement via touch pad (real InputEventMouseButton press/release).
	var start_pos: Vector2 = shell._area.wizard_position()
	var pad: Control = shell._touch._pad
	if pad == null:
		push_error("touch pad missing")
		_shutdown(shell, 1)
		return
	var pad_rect := pad.get_global_rect()
	var right_zone := Rect2(
		pad_rect.position + Vector2(pad_rect.size.x * 0.72, pad_rect.size.y * 0.35),
		Vector2(pad_rect.size.x * 0.22, pad_rect.size.y * 0.3)
	)
	await _pointer_hold(right_zone, 0.55)
	var after_move: Vector2 = shell._area.wizard_position()
	if after_move.distance_to(start_pos) < 4.0:
		push_error("pointer pad did not move wizard (start=%s after=%s)" % [start_pos, after_move])
		_shutdown(shell, 1)
		return

	# Click Wait — exactly one World Turn.
	var turn0 := int(shell._client.request_view("player").get("clock", {}).get("turn", -1))
	var wait_btn := _find_button(shell, "Wait")
	if wait_btn == null:
		push_error("Wait button not found")
		_shutdown(shell, 1)
		return
	await _pointer_click(wait_btn.get_global_rect())
	for _j in range(20):
		await process_frame
	var turn1 := int(shell._client.request_view("player").get("clock", {}).get("turn", -1))
	if turn1 != turn0 + 1:
		push_error("Wait click expected turn %s→%s, got %s" % [turn0, turn0 + 1, turn1])
		_shutdown(shell, 1)
		return

	# Start delivery through Interact (same path as Economy Start button).
	var start_reply: Dictionary = shell._client.send_command(
		"g02-start", "Interact", {"action": "start_delivery"}
	)
	if str(start_reply.get("status", "")) != "ACCEPTED":
		push_error("start_delivery failed: %s" % start_reply)
		_shutdown(shell, 1)
		return
	var cart_id := str(fx.get("cart_id"))
	var cart: Dictionary = shell._client.request_view("economy").get("carts", {}).get(cart_id, {})
	if str(cart.get("status", "")) != "en_route":
		push_error("cart not en_route after start: %s" % cart)
		_shutdown(shell, 1)
		return
	var cargo_qty := _aboard_qty(cart)
	if cargo_qty < 4:
		push_error("expected cargo aboard after start, got %s" % cargo_qty)
		_shutdown(shell, 1)
		return

	# Block route, Wait until blocked.
	var block_reply: Dictionary = shell._client.send_command(
		"g02-block", "Interact", {"action": "place_route_block"}
	)
	if str(block_reply.get("status", "")) != "ACCEPTED":
		push_error("place_route_block failed: %s" % block_reply)
		_shutdown(shell, 1)
		return
	for i in range(3):
		shell._client.send_command(
			"g02-bw-%d" % i,
			"Wait",
			{"current_node": shell._client.request_view("player").get("player", {}).get("node_id", "node:1"), "press_id": "bw-%d" % i},
		)
	cart = shell._client.request_view("economy").get("carts", {}).get(cart_id, {})
	if str(cart.get("status", "")) != "blocked":
		push_error("expected blocked cart, got %s" % cart)
		_shutdown(shell, 1)
		return
	if _aboard_qty(cart) != cargo_qty:
		push_error("cargo teleported/changed while blocked")
		_shutdown(shell, 1)
		return
	var blocked_node := str(cart.get("current_node"))

	# Save while cargo aboard / blocked, reload, verify preservation.
	var save_reply: Dictionary = shell._client.send_command("g02-save", "Save", {"slot": "g02_smoke"})
	if str(save_reply.get("status", "")) != "ACCEPTED":
		push_error("save failed: %s" % save_reply)
		_shutdown(shell, 1)
		return
	var load_reply: Dictionary = shell._client.send_command("g02-load", "Load", {"slot": "g02_smoke"})
	if str(load_reply.get("status", "")) != "ACCEPTED":
		push_error("load failed: %s" % load_reply)
		_shutdown(shell, 1)
		return
	cart = shell._client.request_view("economy").get("carts", {}).get(cart_id, {})
	if str(cart.get("current_node")) != blocked_node or _aboard_qty(cart) != cargo_qty:
		push_error("save/load lost in-transit cargo: %s" % cart)
		_shutdown(shell, 1)
		return

	# Clear and resume delivery to staging.
	var clear_reply: Dictionary = shell._client.send_command(
		"g02-clear", "Interact", {"action": "clear_hazard"}
	)
	if str(clear_reply.get("status", "")) != "ACCEPTED":
		push_error("clear_hazard failed: %s" % clear_reply)
		_shutdown(shell, 1)
		return
	for i in range(4):
		shell._client.send_command(
			"g02-cw-%d" % i,
			"Wait",
			{"current_node": shell._client.request_view("player").get("player", {}).get("node_id", "node:1"), "press_id": "cw-%d" % i},
		)
	cart = shell._client.request_view("economy").get("carts", {}).get(cart_id, {})
	var fx_after: Dictionary = shell._client.request_view("economy").get("fx_cargo", {})
	if str(cart.get("current_node")) != str(fx_after.get("N2")) and str(cart.get("status")) != "arrived":
		# Allow arrived at N2.
		if str(cart.get("status")) != "arrived":
			push_error("cart did not resume to staging: %s fx=%s" % [cart, fx_after])
			_shutdown(shell, 1)
			return
	var staging := str(fx_after.get("staging_store"))
	var stocks: Dictionary = shell._client.request_view("economy").get("stocks", {})
	var staging_stock: Dictionary = stocks.get(staging, {}).get("catan", {}) if stocks.has(staging) else {}
	var timber_ok := int(staging_stock.get("timber", {}).get("available", 0)) >= 1
	if not timber_ok and str(fx_after.get("delivery_status")) != "delivered":
		push_error("staging missing delivered timber: stocks=%s fx=%s" % [staging_stock, fx_after])
		_shutdown(shell, 1)
		return

	print(
		"G02_SMOKE_OK seed=", fx.get("seed"),
		" cart=", cart_id,
		" store=", fx.get("store"),
		" moved=", after_move.distance_to(start_pos),
		" wait_turn=", turn0, "→", turn1,
		" delivery=", fx_after.get("delivery_status"),
		" construction=", fx_after.get("construction_status", "?")
	)
	_shutdown(shell, 0)


func _aboard_qty(cart: Dictionary) -> int:
	var total := 0
	for lot in cart.get("cargo_lots", []):
		if typeof(lot) != TYPE_DICTIONARY:
			continue
		if str(lot.get("status", "")) == "aboard":
			total += int(lot.get("quantity", 0))
	return total


func _find_button(node: Node, text: String) -> Button:
	if node is Button and str((node as Button).text) == text:
		return node as Button
	for child in node.get_children():
		var found := _find_button(child, text)
		if found != null:
			return found
	return null


func _pointer_click(rect: Rect2) -> void:
	var pos := _event_pos(rect.get_center())
	var motion := InputEventMouseMotion.new()
	motion.position = pos
	motion.global_position = pos
	root.push_input(motion)
	await process_frame
	var press := InputEventMouseButton.new()
	press.button_index = MOUSE_BUTTON_LEFT
	press.pressed = true
	press.position = pos
	press.global_position = pos
	press.button_mask = MOUSE_BUTTON_MASK_LEFT
	root.push_input(press)
	await process_frame
	var release := InputEventMouseButton.new()
	release.button_index = MOUSE_BUTTON_LEFT
	release.pressed = false
	release.position = pos
	release.global_position = pos
	root.push_input(release)
	await process_frame


func _pointer_hold(rect: Rect2, seconds: float) -> void:
	var pos := _event_pos(rect.get_center())
	var motion := InputEventMouseMotion.new()
	motion.position = pos
	motion.global_position = pos
	root.push_input(motion)
	await process_frame
	var press := InputEventMouseButton.new()
	press.button_index = MOUSE_BUTTON_LEFT
	press.pressed = true
	press.position = pos
	press.global_position = pos
	press.button_mask = MOUSE_BUTTON_MASK_LEFT
	root.push_input(press)
	var frames := int(ceil(seconds * 60.0))
	for _i in range(maxi(frames, 8)):
		await process_frame
	var release := InputEventMouseButton.new()
	release.button_index = MOUSE_BUTTON_LEFT
	release.pressed = false
	release.position = pos
	release.global_position = pos
	root.push_input(release)
	await process_frame


func _event_pos(canvas: Vector2) -> Vector2:
	return root.get_final_transform() * canvas


func _shutdown(shell: Node, code: int) -> void:
	if shell != null and shell.get("_launcher") != null and shell._launcher != null:
		shell._launcher.stop()
	OS.delay_msec(80)
	quit(code)
