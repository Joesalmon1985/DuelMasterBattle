extends SceneTree

## Headed conversation-interruption test: a person the wizard talks to STOPS (and stands, not walking on the spot) while everyone else in the settlement
## carries on, and goes back to their activity when the conversation ends. The world is NOT paused: the scene polls the simulation in real time, so
## "stops" means the picture really stops while other workers and carriers keep moving. Subjects: a moving lumberjack, a forester, a carrier and a soldier
## on a move order. Also: the conversation closes by itself when the person is killed, and the same person (same name) is met again afterwards.
## Needs HYBRID_PROFILE=developer (the soldier's order is a God command) and HYBRID_ALLOW_SPAWN is not needed.

var _world: Node
var _ui: Node
var _fails: Array[String] = []
var _dir := ""


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, label: String) -> void:
	print("CONV %s %s" % ["ok  " if ok else "FAIL", label])
	if not ok:
		_fails.append(label)


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _secs(seconds: float) -> void:
	await create_timer(seconds).timeout


func _settle() -> void:
	await _frames(3)
	await RenderingServer.frame_post_draw


func _shot(name: String) -> void:
	await _settle()
	var image: Image = get_root().get_viewport().get_texture().get_image()
	DirAccess.make_dir_recursive_absolute(_dir)
	image.save_png(_dir.replace("\\", "/") + "/%s.png" % name)
	print("CONV_SHOT %s" % name)


func _by_id(id: String) -> Dictionary:
	for e in _world._snapshot.get("entities", []):
		if str(e.get("id", "")) == id:
			return e
	return {}


func _tile(id: String) -> Vector2i:
	var e := _by_id(id)
	return Vector2i(int(e.get("tx", -1)), int(e.get("ty", -1)))


func _others() -> Dictionary:
	var out := {}
	for e in _world._snapshot.get("entities", []):
		if str(e.get("class", "")) in ["worker", "carrier"]:
			out[str(e["id"])] = Vector2i(int(e["tx"]), int(e["ty"]))
	return out


func _wait_until(cond: Callable, seconds := 20.0) -> bool:
	var t0 := Time.get_ticks_msec()
	while not cond.call():
		await _frames(3)
		if (Time.get_ticks_msec() - t0) / 1000.0 > seconds:
			return false
	return true


var _seen: Dictionary = {}


## Is this body going somewhere right now? (its anim or status says so, or it has changed tile since the last time we looked)
func _walking(id: String) -> bool:
	var e := _by_id(id)
	if e.is_empty():
		return false
	var here := Vector2i(int(e["tx"]), int(e["ty"]))
	var moved: bool = _seen.has(id) and _seen[id] != here
	_seen[id] = here
	return moved or str(e.get("anim", "")) in ["walk", "walkload"] or str(e.get("status", "")) == "moving"


func _key(code: int) -> void:
	for pressed in [true, false]:
		var ev := InputEventKey.new()
		ev.keycode = code
		ev.physical_keycode = code
		ev.pressed = pressed
		Input.parse_input_event(ev)
		await _frames(1)
	await _frames(3)


## Stand beside the person and start the conversation the way the inspect card's Talk button does (story_ui.talk_to).
func _talk(id: String) -> bool:
	var e := _by_id(id)
	for d in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
		var t: Vector2i = Vector2i(int(e["tx"]), int(e["ty"])) + (d as Vector2i)
		if _world.is_walkable(t):
			_world.set_john_pos(t)
			_world._arrived()
			break
	_ui.talk_to(id)
	await _frames(4)
	return _ui.dialog.visible


func _journal() -> Dictionary:
	return _world._sim.op({"op": "journal"}).get("journal", {})


## The whole experiment for one person: it moves, the wizard talks to it, it stands still for a few real seconds while others move, the conversation
## closes, and it moves again.
func _subject(label: String, id: String, keep_moving_check: bool) -> void:
	_check(await _wait_until(func(): return _walking(id), 120.0), "%s: moving before we talk (%s)" % [label, str(_tile(id))])
	var others0 := _others()
	var ms0 := int(_world._snapshot.get("game_ms", 0))
	_check(await _talk(id), "%s: the conversation opens" % label)
	var name_before: String = _ui.dialog_title.text
	var held_at := _tile(id)
	await _secs(1.0)
	held_at = _tile(id)
	await _shot("conv_%s_talking" % label)
	await _secs(4.0)
	_check(_tile(id) == held_at, "%s: stays exactly where they stopped for 4 more seconds (%s -> %s)" % [label, str(held_at), str(_tile(id))])
	_check(str(_by_id(id).get("anim", "idle")) == "idle" or str(_by_id(id).get("status", "")) == "idle", "%s: stands instead of walking on the spot (anim %s, status %s)" % [label, str(_by_id(id).get("anim", "")), str(_by_id(id).get("status", ""))])
	var others1 := _others()
	var moved := 0
	for k in others1:
		if k != id and others0.has(k) and others0[k] != others1[k]:
			moved += 1
	_check(int(_world._snapshot.get("game_ms", 0)) - ms0 >= 3000, "%s: the world kept running (%d game ms passed)" % [label, int(_world._snapshot.get("game_ms", 0)) - ms0])
	_check(moved >= 1, "%s: other workers and carriers kept moving (%d of them moved)" % [label, moved])
	_check((_journal().get("talking", []) as Array).has(id), "%s: the server says they are in conversation" % label)
	_check(_ui.dialog_title.text == name_before and name_before != "" and _ui.person_name(id) == name_before, "%s: they are still %s" % [label, name_before])
	await _key(KEY_ESCAPE)
	_check(not _ui.dialog.visible and not (_journal().get("talking", []) as Array).has(id), "%s: Escape closes it and releases them" % label)
	if keep_moving_check:
		_check(await _wait_until(func(): return _tile(id) != held_at, 25.0), "%s: they go back to what they were doing (%s -> %s)" % [label, str(held_at), str(_tile(id))])


## The first Red carrier that actually walks (a carrier on a quiet road stays put): watch them all for a while.
func _find_moving_carrier() -> String:
	var start := {}
	for e in _world._snapshot.get("entities", []):
		if str(e.get("class", "")) == "carrier" and str(e.get("faction_name", "")) == "Red":
			start[str(e["id"])] = Vector2i(int(e["tx"]), int(e["ty"]))
	var t0 := Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < 60000:
		await _frames(10)
		for id in start:
			if _tile(str(id)) != start[id]:
				return str(id)
	return ""


## The first Red worker of this role that actually walks (a hut can stand idle for a while): watch them all.
func _find_moving_worker(role: String, fallback: String) -> String:
	var start := {}
	for e in _world._snapshot.get("entities", []):
		if str(e.get("class", "")) == "worker" and str(e.get("faction_name", "")) == "Red" and str(e.get("role", "")) == role:
			start[str(e["id"])] = Vector2i(int(e["tx"]), int(e["ty"]))
	var t0 := Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < 90000:
		await _frames(10)
		for id in start:
			if _tile(str(id)) != start[id]:
				return str(id)
	return fallback


func _run() -> void:
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
	if _dir == "":
		_dir = "res://../WizardRTSHybrid/docs/evidence/narrative/polish"
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	await _frames(40)
	_ui = _world.story_ui
	_ui.finish_opening()
	_world._camera.zoom = Vector2(1.0, 1.0)
	var prof: Dictionary = _world._sim.op({"op": "profile"})
	_check(str(prof.get("profile", "")) == "developer", "developer profile (%s)" % str(prof.get("profile", "")))
	_world._sim.op({"op": "ai", "enabled": false})  # the settlement's own work is what we watch; nobody else marches
	await _secs(20.0)  # let the settlement get going: workers out and about, carriers on the roads

	var jack := ""
	var ranger := ""
	var carrier := ""
	for e in _world._snapshot.get("entities", []):
		var cls := str(e.get("class", ""))
		if cls == "worker" and str(e.get("faction_name", "")) == "Red" and str(e.get("role", "")) == "lumberjack" and jack == "":
			jack = str(e["id"])
		if cls == "worker" and str(e.get("faction_name", "")) == "Red" and str(e.get("role", "")) == "ranger" and ranger == "":
			ranger = str(e["id"])
		if cls == "carrier" and str(e.get("faction_name", "")) == "Red" and carrier == "":
			carrier = str(e["id"])
	_check(jack != "" and ranger != "" and carrier != "", "Red lumberjack %s, forester %s and carrier %s exist" % [jack, ranger, carrier])

	jack = await _find_moving_worker("lumberjack", jack)
	await _subject("lumberjack", jack, true)
	ranger = await _find_moving_worker("ranger", ranger)
	await _subject("forester", ranger, true)
	# a carrier is only 'moving' while it carries or walks its road; wait for a moment when it does
	var mover := await _find_moving_carrier()
	if mover != "":
		carrier = mover
	await _subject("carrier", carrier, false)

	# ---- a soldier on a move order
	var soldier := ""
	for e in _world._snapshot.get("entities", []):
		if str(e.get("class", "")) == "unit" and str(e.get("faction_name", "")) == "Red" and str(e.get("kind", "")) == "soldier":
			soldier = str(e["id"])
			break
	_check(soldier != "", "a Red soldier exists (%s)" % soldier)
	if soldier != "":
		var st := _tile(soldier)
		_world._sim.op({"op": "control", "faction": "Red"})
		var mv: Dictionary = {}
		for off in [Vector2i(18, 0), Vector2i(-18, 0), Vector2i(0, 18), Vector2i(0, -18), Vector2i(10, 10), Vector2i(-10, -10)]:
			mv = _world._sim.op({"op": "move", "units": [soldier], "tx": st.x + off.x, "ty": st.y + off.y, "attack_move": false})
			if str(mv.get("status", "")) != "rejected":
				break
		_check(str(mv.get("status", "")) != "rejected", "the soldier is sent on a long walk (%s)" % str(mv))
		_check(await _wait_until(func(): return _tile(soldier) != st, 15.0), "the soldier is walking")
		_check(await _talk(soldier), "the soldier agrees to talk")
		var held := _tile(soldier)
		await _secs(1.0)
		held = _tile(soldier)
		await _secs(4.0)
		_check(_tile(soldier) == held, "the soldier stands still while we talk (%s -> %s)" % [str(held), str(_tile(soldier))])
		await _shot("conv_soldier_talking")
		await _key(KEY_ESCAPE)
		_check(await _wait_until(func(): return _tile(soldier) != held, 20.0), "released, he carries on to where he was going (%s -> %s)" % [str(held), str(_tile(soldier))])

	# ---- the person is killed during the conversation: the conversation ends by itself
	if jack != "":
		_check(await _talk(jack), "talk to the lumberjack again")
		var fire: Dictionary = _world._sim.op({"op": "fire", "target": jack})
		_check(str(fire.get("status", "")) == "ok", "he is struck down while we talk (%s)" % str(fire.get("status", fire.get("reason", ""))))
		_check(await _wait_until(func(): return not _ui.dialog.visible, 12.0), "the conversation closes by itself")
		_check(not (_journal().get("talking", []) as Array).has(jack) and _by_id(jack).is_empty(), "nothing is left held and he is gone from the world")
		await _secs(2.0)
		_check(not _world._input_locked, "control has returned to the wizard")

	if _fails.is_empty():
		print("HYBRID_CONVERSATION_OK")
		quit(0)
	else:
		print("HYBRID_CONVERSATION_FAIL ", ", ".join(_fails))
		quit(1)
