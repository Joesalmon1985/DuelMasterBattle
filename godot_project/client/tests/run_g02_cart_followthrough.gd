extends SceneTree

## Follow FX-CARGO cart presentation through node:1 → node:2 → node:3.
## Pauses shell auto-clock and drives AdvanceGame + tick_presentation explicitly.

const Migrated = preload("res://client/core/migrated_runtime.gd")
const G02Shell = preload("res://client/scenes/g02_shell.gd")

var _clock_seq := 0


func _init() -> void:
	call_deferred("_go")


func _go() -> void:
	Migrated.enable()
	OS.set_environment("DMB_FIXTURE", "FX-CARGO")
	OS.set_environment("DMB_SEED", "202")
	DisplayServer.window_set_size(Vector2i(450, 800))

	var shell: Control = G02Shell.new()
	root.add_child(shell)
	for _i in range(90):
		await process_frame
		if shell._client != null and shell._area != null:
			break
	if shell._client == null or shell._area == null:
		push_error("boot failed")
		_shutdown(shell, 1)
		return
	shell._force_playable_focus()
	for _j in range(8):
		await process_frame
	# Stop competing auto AdvanceGame from the shell clock.
	shell._paused = true
	_clock_seq = int(shell._client.request_view("player").get("clock", {}).get("clock_sequence", 0))

	var start: Dictionary = shell._client.send_command("ft-start", "Interact", {"action": "start_delivery"})
	if str(start.get("status", "")) != "ACCEPTED":
		push_error("start failed %s" % start)
		_shutdown(shell, 1)
		return
	print("FT_START_OK")

	var turn0 := _turn(shell)
	await _drive(shell, 50)  # ~5s Game Time at 100ms/tick
	if _turn(shell) != turn0:
		push_error("Game Time walk changed World Turn")
		_shutdown(shell, 1)
		return
	var j := _journey(shell)
	print("FT_APPROACH phase=", j.get("phase"), " presenting=", j.get("presenting_node"))
	if str(j.get("phase", "")) not in ["to_exit", "waiting_exit", "departing"]:
		push_error("expected approach phase, got %s" % j.get("phase"))
		_shutdown(shell, 1)
		return

	var node := str(shell._client.request_view("player").get("player", {}).get("node_id", "node:1"))
	shell._client.send_command("ft-w1", "Wait", {"current_node": node, "press_id": "ft-w1"})
	shell._refresh_counters(false)
	await _drive(shell, 25)
	j = _journey(shell)
	print("FT_AFTER_WAIT phase=", j.get("phase"), " presenting=", j.get("presenting_node"))
	if str(j.get("phase", "")) not in ["departing", "hidden", "entering", "to_waypoint", "waiting_exit"]:
		# Still finishing to_exit toward authorized exit is OK briefly.
		if str(j.get("phase")) == "to_exit" and bool(j.get("authorized_cross", false)):
			await _drive(shell, 20)
			j = _journey(shell)
			print("FT_AFTER_WAIT2 phase=", j.get("phase"), " presenting=", j.get("presenting_node"))
		if str(j.get("phase", "")) not in ["departing", "hidden", "entering", "to_waypoint", "waiting_exit"]:
			push_error("unexpected post-Wait phase %s" % j.get("phase"))
			_shutdown(shell, 1)
			return

	var trav: Dictionary = shell._client.send_command("ft-t2", "Travel", {"from_node": node, "to_node": "node:2"})
	if str(trav.get("status", "")) != "ACCEPTED":
		push_error("travel node:2 failed %s" % trav)
		_shutdown(shell, 1)
		return
	_clock_seq = int(shell._client.request_view("player").get("clock", {}).get("clock_sequence", _clock_seq))
	shell._refresh_counters(true)
	await process_frame
	await _drive(shell, 45)
	j = _journey(shell)
	print(
		"FT_NODE2 phase=", j.get("phase"),
		" presenting=", j.get("presenting_node"),
		" last=", int(j.get("last_consumed_sequence", 0))
	)
	if str(j.get("presenting_node")) == "node:2":
		var lf: Array = j.get("local_from", [0, 0])
		var lt: Array = j.get("local_to", [12, 5])
		if float(lf[0]) > float(lt[0]) + 0.5:
			push_error("node:2 restarted westbound leg from=%s to=%s" % [lf, lt])
			_shutdown(shell, 1)
			return
	var seq2 := int(j.get("last_consumed_sequence", 0))
	var phase2 := str(j.get("phase", ""))
	for _r in range(50):
		var jj := _journey(shell)
		if int(jj.get("last_consumed_sequence", 0)) < seq2:
			push_error("sequence rewound on refresh")
			_shutdown(shell, 1)
			return
		if phase2 in ["to_waypoint", "waiting_exit", "to_delivery", "unloading", "idle"]:
			if str(jj.get("phase")) == "entering" and float(jj.get("local_pos", [9, 5])[0]) < 2.5:
				if float(j.get("local_pos", [9, 5])[0]) > 8.0:
					push_error("entrance restarted after refresh")
					_shutdown(shell, 1)
					return
		await process_frame
	print("FT_REFRESH_OK")

	var here := str(shell._client.request_view("player").get("player", {}).get("node_id", "node:2"))
	shell._client.send_command("ft-w2", "Wait", {"current_node": here, "press_id": "ft-w2"})
	_clock_seq = int(shell._client.request_view("player").get("clock", {}).get("clock_sequence", _clock_seq))
	await _drive(shell, 20)

	here = str(shell._client.request_view("player").get("player", {}).get("node_id", "node:2"))
	if here == "node:2":
		var trav3: Dictionary = shell._client.send_command(
			"ft-t3", "Travel", {"from_node": "node:2", "to_node": "node:3"}
		)
		if str(trav3.get("status", "")) == "ACCEPTED":
			_clock_seq = int(shell._client.request_view("player").get("clock", {}).get("clock_sequence", _clock_seq))
			shell._refresh_counters(true)
	await _drive(shell, 50)

	j = _journey(shell)
	var phase3 := str(j.get("phase", ""))
	var present3 := str(j.get("presenting_node", ""))
	var pending: Array = shell._client.request_view("player").get("presentation", {}).get(
		"pending_transitions", {}
	).get("person:cart", [])
	print(
		"G02_CART_FOLLOWTHROUGH_OK phases_end=%s presenting=%s last_seq=%s pending=%s"
		% [phase3, present3, int(j.get("last_consumed_sequence", 0)), pending.size()]
	)
	_shutdown(shell, 0)


func _drive(shell: Control, ticks: int) -> void:
	for i in range(ticks):
		_clock_seq += 1
		shell._client.send_command(
			"ft-adv-%d" % _clock_seq,
			"AdvanceGame",
			{"delta_ms": 100, "clock_sequence": _clock_seq},
		)
		if shell._area:
			shell._area.tick_presentation(0.1)
		if i % 5 == 0:
			shell._refresh_counters(false)
		await process_frame


func _journey(shell: Control) -> Dictionary:
	var view: Dictionary = shell._client.request_view("player")
	return view.get("presentation", {}).get("journeys", {}).get("person:cart", {})


func _turn(shell: Control) -> int:
	return int(shell._client.request_view("player").get("clock", {}).get("turn", 0))


func _shutdown(shell: Node, code: int) -> void:
	if shell != null and shell.get("_launcher") != null and shell._launcher != null:
		shell._launcher.stop()
	OS.delay_msec(50)
	quit(code)
