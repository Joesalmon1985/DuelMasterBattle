extends SceneTree

## Automated G02 cart journey demo: Start → Game Time walk → Wait crossing → frames.

const Migrated = preload("res://client/core/migrated_runtime.gd")
const G02Shell = preload("res://client/scenes/g02_shell.gd")


func _init() -> void:
	call_deferred("_go")


func _go() -> void:
	Migrated.enable()
	OS.set_environment("DMB_FIXTURE", "FX-CARGO")
	OS.set_environment("DMB_SEED", "202")
	DisplayServer.window_set_size(Vector2i(450, 800))
	var project_root := ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
	if project_root.ends_with("godot_project"):
		project_root = project_root.get_base_dir()
	var out_dir := project_root.path_join("Pack/DuelMasterBattle_Build_Pack/tracking/gates/G02/recordings")
	DirAccess.make_dir_recursive_absolute(out_dir)

	var shell: Control = G02Shell.new()
	root.add_child(shell)
	for _i in range(90):
		await process_frame
		if shell._client != null and shell._area != null:
			break
	if shell._client == null:
		push_error("boot failed")
		quit(1)
		return
	shell._force_playable_focus()
	await create_timer(0.4).timeout

	var start: Dictionary = shell._client.send_command("demo-start", "Interact", {"action": "start_delivery"})
	if str(start.get("status", "")) != "ACCEPTED":
		push_error("start failed %s" % start)
		quit(1)
		return
	shell._refresh_counters(false)

	# Advance Game Time so the cart walks toward the exit (World Turn unchanged).
	var turn0 := int(shell._client.request_view("player").get("clock", {}).get("turn", 0))
	for i in range(40):
		shell._client.send_command("demo-adv-%d" % i, "AdvanceGame", {"delta_ms": 100, "clock_sequence": i + 1})
		if shell._area:
			shell._area.tick_presentation(0.1)
		shell._refresh_counters(false)
		if i % 8 == 0:
			_save_frame(out_dir, "depart_%02d.png" % (i / 8))
		await process_frame
	var turn1 := int(shell._client.request_view("player").get("clock", {}).get("turn", 0))
	if turn1 != turn0:
		push_error("Game Time walk changed World Turn")
		quit(1)
		return

	# Authorised crossing — capture while cart is still departing the yard.
	var node := str(shell._client.request_view("player").get("player", {}).get("node_id", "node:1"))
	shell._client.send_command("demo-wait", "Wait", {"current_node": node, "press_id": "demo-wait"})
	shell._refresh_counters(false)
	if shell._area:
		shell._area.tick_presentation(0.05)
	shell._client.send_command("demo-dep-0", "AdvanceGame", {"delta_ms": 50, "clock_sequence": 50})
	if shell._area:
		shell._area.tick_presentation(0.05)
	shell._refresh_counters(false)
	await process_frame
	_save_frame(out_dir, "crossing.png")
	# Finish departure animation on the yard before following.
	for i in range(5):
		shell._client.send_command("demo-dep-%d" % (i + 1), "AdvanceGame", {"delta_ms": 80, "clock_sequence": 51 + i})
		if shell._area:
			shell._area.tick_presentation(0.08)
		shell._refresh_counters(false)
		await process_frame

	# Follow into next area. Travel spends another seat; pending still plays node:2 entrance.
	var trav: Dictionary = shell._client.send_command(
		"demo-trav", "Travel", {"from_node": node, "to_node": "node:2"}
	)
	if str(trav.get("status", "")) != "ACCEPTED":
		push_error("travel failed %s" % trav)
		quit(1)
		return
	shell._refresh_counters(true)
	await process_frame
	for i in range(40):
		shell._client.send_command("demo-adv2-%d" % i, "AdvanceGame", {"delta_ms": 100, "clock_sequence": 100 + i})
		if shell._area:
			shell._area.tick_presentation(0.1)
		shell._refresh_counters(false)
		if i % 10 == 0:
			_save_frame(out_dir, "arrive_%02d.png" % (i / 10))
		await process_frame

	_save_frame(out_dir, "final.png")
	var cart_shown := false
	if shell._area != null and shell._area._npc_nodes.has("person:cart"):
		cart_shown = bool(shell._area._npc_nodes["person:cart"].visible)
	print("G02_JOURNEY_DEMO_OK frames=", out_dir, " cart_visible=", cart_shown)
	if shell._launcher and shell._launcher.has_method("stop"):
		shell._launcher.stop()
	call_deferred("quit", 0)


func _save_frame(dir: String, name: String) -> void:
	var img: Image = get_root().get_viewport().get_texture().get_image()
	img.save_png(dir.path_join(name))
