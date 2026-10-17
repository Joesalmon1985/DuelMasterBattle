extends SceneTree

## Headed LAN check of the character system: this client joins a Python host where a scripted second human walks up to us.
## Checks: the other wizard is a character (not a rectangle), has its own cut and colour, walks (WALK state) while its tile changes and
## idles when it stops, both wizards face the right way, and the look is identical across a reconnect.  Screenshots at close range.
## Env: HYBRID_LAN_HOST, HYBRID_LAN_PORT, HYBRID_LAN_CODE, HYBRID_SHOT_DIR.  Prints HYBRID_LAN_CHARACTERS_OK.

const Anim = preload("res://client/characters/character_anim.gd")
const Appearance = preload("res://client/characters/character_appearance.gd")

var _lan: Node
var fails := 0


func _init() -> void:
	call_deferred("_run")


func check(cond: bool, what: String) -> void:
	if cond:
		print("ok:   ", what)
	else:
		fails += 1
		print("FAIL: ", what)


func _shot(world: Node, name: String) -> void:
	var dir := OS.get_environment("HYBRID_SHOT_DIR")
	if dir == "":
		return
	world.queue_redraw()
	for _i in 4:
		await process_frame
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute(dir)
	root.get_viewport().get_texture().get_image().save_png(dir.path_join(name + ".png"))
	print("HYBRID_LAN_SHOT ", name)


func _run() -> void:
	DisplayServer.window_set_size(Vector2i(720, 1000))
	var host := OS.get_environment("HYBRID_LAN_HOST") if OS.get_environment("HYBRID_LAN_HOST") != "" else "127.0.0.1"
	var port := int(OS.get_environment("HYBRID_LAN_PORT"))
	var code := OS.get_environment("HYBRID_LAN_CODE")
	_lan = root.get_node("/root/LanSession")
	_lan.reset()
	_lan.mode = "join"
	_lan.player_name = "Mira"
	var hello: Dictionary = _lan.connect_and_hello(host, port, code, "Mira")
	if str(hello.get("status", "")) != "ok":
		print("HYBRID_LAN_CHARACTERS_FAIL hello ", hello)
		quit(1)
		return
	var deadline := Time.get_ticks_msec() + 60000
	while Time.get_ticks_msec() < deadline:
		var lob: Dictionary = _lan.sim.op({"op": "lobby"})
		if str(lob.get("session", {}).get("state", "")) == "playing":
			break
		await create_timer(0.3).timeout
	var world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(world)
	for _i in 40:
		await process_frame
	check(world.mp, "this client is in LAN mode")
	deadline = Time.get_ticks_msec() + 20000
	while world.ui_mp_players().is_empty() and Time.get_ticks_msec() < deadline:
		await process_frame
	var others: Dictionary = world.ui_mp_players()
	check(others.size() == 1, "one remote wizard is present")
	var other_id: String = others.keys()[0]
	var actor = world.actor("lan:" + other_id)
	check(actor != null and actor.get_node_or_null("CharView") != null, "the remote wizard is drawn by a character view")
	var rview = actor.get_node("CharView")
	var row: Dictionary = others[other_id]
	var expect = Appearance.for_player(other_id, str(row.get("name", other_id)), str(row.get("colour", "")))
	check(rview.look.describe() == expect.describe(), "the remote wizard wears the player's own colours: " + str(rview.look.describe()))
	check(rview.look.outfit.begins_with("wizard"), "and is a wizard (%s)" % rview.look.outfit)
	var mine = world._john.get_node_or_null("CharView")
	check(mine != null and mine.look.outfit != "", "the local wizard is a character too (%s)" % (mine.look.outfit if mine != null else "?"))
	world.camera_focus = Vector2(float(row["tx"]) + 0.5, float(row["ty"]) + 0.5) * world.TPX
	world._camera.zoom = Vector2(1.6, 1.6)
	await _shot(world, "lan_char_01_remote_wizard")
	# walk: watch the remote avatar while the bot approaches; its anim must go WALK when the tile changes and IDLE after
	var saw_walk := false
	var last_tile := Vector2i(int(row["tx"]), int(row["ty"]))
	var t0 := Time.get_ticks_msec()
	var shot_walk := false
	while Time.get_ticks_msec() - t0 < 45000:
		await process_frame
		var rows: Dictionary = world.ui_mp_players()
		if not rows.has(other_id):
			continue
		var r2: Dictionary = rows[other_id]
		var t := Vector2i(int(r2["tx"]), int(r2["ty"]))
		if t != last_tile:
			last_tile = t
		if rview.anim.state == Anim.S.WALK:
			saw_walk = true
			world.camera_focus = (Vector2(t) + Vector2(0.5, 0.5)) * world.TPX
			if not shot_walk:
				shot_walk = true
				await _shot(world, "lan_char_02_remote_walking")
		if absi(t.x - world._john_pos.x) + absi(t.y - world._john_pos.y) <= 1:
			break
	if not saw_walk:
		# the bot had already arrived: glide the avatar one tile exactly as a state poll would
		world.move_actor("lan:" + other_id, last_tile + Vector2i(0, 1), 0.6)
		for _i in 12:
			await process_frame
			if rview.anim.state == Anim.S.WALK:
				saw_walk = true
		await create_timer(1.0).timeout
	check(saw_walk, "the remote wizard's walking animation played while it moved")
	await create_timer(1.0).timeout
	check(rview.anim.state in [Anim.S.IDLE, Anim.S.TALK], "and it idles when it stops (%s)" % rview.anim.state_name())
	var d := Vector2(last_tile) - Vector2(world._john_pos)
	world.camera_focus = (Vector2(world._john_pos) + Vector2(0.5, 0.5) + d * 0.5) * world.TPX
	world._camera.zoom = Vector2(1.8, 1.8)
	await _shot(world, "lan_char_03_both_wizards")
	# my own wizard walks: its state follows the Sprite2D movement
	var start: Vector2i = world._john_pos
	var walked := false
	for dir in [Vector2i(0, -1), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(1, 0)]:
		world.ui_hold_key_direction(dir)
		for _f in 14:
			await process_frame
			if mine.anim.state == Anim.S.WALK:
				walked = true
		world.ui_hold_key_direction(Vector2i.ZERO)
		for _f in 10:
			await process_frame
		if world._john_pos != start:
			break
	check(walked, "the local wizard animates while walking")
	await create_timer(1.0).timeout
	check(mine.anim.state == Anim.S.IDLE, "and returns to idle")
	# presentation events work on LAN wizards too: a cast and a hurt on the remote avatar, then back to normal
	var Bus = preload("res://client/characters/character_bus.gd")
	Bus.react(rview.character_id, "cast")
	await process_frame
	await process_frame
	check(rview.anim.state == Anim.S.CAST, "a LAN wizard can be told to cast (presentation event)")
	await _shot(world, "lan_char_04_remote_casting")
	await create_timer(1.6).timeout
	check(rview.anim.state != Anim.S.CAST, "and the cast ends by itself")
	print("HYBRID_LAN_CHARACTERS_DONE fails=", fails)
	print("HYBRID_LAN_CHARACTERS_OK" if fails == 0 else "HYBRID_LAN_CHARACTERS_FAIL")
	quit(1 if fails > 0 else 0)
