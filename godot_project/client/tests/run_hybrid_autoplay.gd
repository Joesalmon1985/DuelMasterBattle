extends SceneTree

## Headed P6 acceptance: the REAL game, a normal primitive six-faction world, watched in God Mode as a spectator at 16x. Nothing is
## staged: no fixture, no granted card, no era forcing, no spawned unit. Needs the sim with
##   HYBRID_PROFILE=developer HYBRID_START_SPEED=16 HYBRID_AI_POLICY=mixed HYBRID_SEED=507
## (scripts/run_headed_suite.sh autoplay). The script clicks the God Mode button, checks that spectating leaves every faction to its AI,
## then waits (by condition, with limits) for: the first draft, a card's building working, a new settlement, the first battle, the first
## catastrophe and the first NATURAL era change (by VP, not the stall guard). A timestamped screenshot is taken at each.

var _world: Node
var _god: Node
var _fails: Array[String] = []
var _dir := ""
var _t0 := 0


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, label: String) -> void:
	print("AUTOPLAY %s %s" % ["ok  " if ok else "FAIL", label])
	if not ok:
		_fails.append(label)


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _mmss(ms: int) -> String:
	var s := int(ms / 1000)
	return "%02d-%02d" % [s / 60, s % 60]


func _shot(name: String) -> void:
	await _frames(4)
	await RenderingServer.frame_post_draw
	var image: Image = get_root().get_viewport().get_texture().get_image()
	DirAccess.make_dir_recursive_absolute(_dir)
	var gms := int(_world._snapshot.get("game_ms", 0))
	var fname := "%s_game%s_wall%ds" % [name, _mmss(gms), int((Time.get_ticks_msec() - _t0) / 1000)]
	image.save_png(_dir.replace("\\", "/") + "/%s.png" % fname)
	print("AUTOPLAY_SHOT %s" % fname)


func _win(pos: Vector2) -> Vector2:
	return pos * (Vector2(DisplayServer.window_get_size()) / get_root().get_visible_rect().size)


func _click_control(c: Control) -> void:
	var pos := _win(c.get_global_rect().get_center())
	var mv := InputEventMouseMotion.new()
	mv.position = pos
	mv.global_position = pos
	Input.parse_input_event(mv)
	await _frames(1)
	var ev := InputEventMouseButton.new()
	ev.button_index = MOUSE_BUTTON_LEFT
	ev.position = pos
	ev.global_position = pos
	ev.pressed = true
	ev.button_mask = 1
	Input.parse_input_event(ev)
	await _frames(2)
	var up := ev.duplicate()
	up.pressed = false
	up.button_mask = 0
	Input.parse_input_event(up)
	await _frames(4)


func _feed_has(kind: String, extra: Callable = Callable()) -> bool:
	for e in _world._snapshot.get("feed", []):
		if str(e.get("kind", "")) == kind and (not extra.is_valid() or extra.call(e)):
			return true
	return false


func _card_building_working() -> bool:
	for e in _world._snapshot.get("entities", []):
		if str(e.get("class", "")) == "building" and str(e.get("kind", "")) in ["farm", "war_lodge", "tavern", "mine", "ironmine", "smelter"] \
				and not e.has("constructing") and not str(e.get("status_text", "")).begins_with("Under construction"):
			return true
	return false


func _run() -> void:
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
	if _dir == "":
		_dir = "res://../WizardRTSHybrid/docs/evidence/autoplay"
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(1366, 768))
	await _frames(40)
	_t0 = Time.get_ticks_msec()
	_god = _world.god
	var prof: Dictionary = _world._sim.op({"op": "profile"})
	_check(str(prof.get("profile", "")) == "developer" and bool(prof.get("gated", false)), "a gated primitive world (developer profile for God Mode)")
	_check(int(_world._snapshot.get("time_scale", 1)) == 16, "the clock starts at 16x (time_scale %s)" % str(_world._snapshot.get("time_scale", "")))
	if not _god.active:
		await _click_control(_god.mode_btn)
	_check(_god.active, "God Mode opened from its button")
	await _frames(20)
	_check(str(_world._snapshot.get("controlled_faction", "x")) == "", "spectating takes no faction away from its AI")
	_check(_god.spectator != null and _god.spectator.top.visible and _god.spectator.top.text.contains("Era"), "the spectator HUD shows the era")
	await _shot("01_primitive_start")
	var red0 := 0
	for e in _world._snapshot.get("entities", []):
		if str(e.get("faction_name", "")) == "Red" and str(e.get("class", "")) == "building":
			red0 += 1
	var steps := [
		["02_first_draft", func() -> bool: return _feed_has("card_drafted")],
		["03_card_building_working", func() -> bool: return _card_building_working()],
		["04_new_settlement", func() -> bool: return _feed_has("deployed")],
		["05_first_battle", func() -> bool: return _feed_has("ai_attack") or _feed_has("vp_conquest") or _feed_has("settlement_destroyed")],
		["06_first_catastrophe", func() -> bool: return _feed_has("outbreak_cube") or _feed_has("disrupted")],
		["07_natural_historic", func() -> bool: return str(_world._snapshot.get("era", {}).get("era", "")) != "prehistoric" and str(_world._snapshot.get("era", {}).get("last_reason", "")) == "vp_threshold"],
	]
	var done := {}
	var limit_game_ms := int(OS.get_environment("AUTOPLAY_LIMIT_MS")) if OS.get_environment("AUTOPLAY_LIMIT_MS") != "" else 75 * 60_000
	var wall_limit_ms := 20 * 60_000
	while done.size() < steps.size():
		await _frames(10)
		var gms := int(_world._snapshot.get("game_ms", 0))
		for st in steps:
			if not done.has(st[0]) and (st[1] as Callable).call():
				done[st[0]] = gms
				print("AUTOPLAY event %s at game %s, wall %d s" % [st[0], _mmss(gms), int((Time.get_ticks_msec() - _t0) / 1000)])
				if st[0] == "02_first_draft":
					_god.spectator.inspect("Green")  # show the draft panel of a faction the improved AI plays
					await _frames(10)
				await _shot(st[0])
		if gms >= limit_game_ms or Time.get_ticks_msec() - _t0 > wall_limit_ms:
			break
	for st in steps:
		_check(done.has(st[0]), "%s within %d game minutes" % [st[0], limit_game_ms / 60_000])
	var red1 := 0
	for e in _world._snapshot.get("entities", []):
		if str(e.get("faction_name", "")) == "Red" and str(e.get("class", "")) == "building":
			red1 += 1
	_check(red1 > red0, "the AI kept building while it was watched (Red %d -> %d buildings)" % [red0, red1])
	var gms_end := int(_world._snapshot.get("game_ms", 0))
	var wall := float(Time.get_ticks_msec() - _t0) / 1000.0
	print("AUTOPLAY pace: %.1f game minutes in %.0f s wall = %.1fx" % [gms_end / 60000.0, wall, gms_end / 1000.0 / maxf(wall, 1.0)])
	await _shot("99_end")
	if _fails.is_empty():
		print("HYBRID_AUTOPLAY_OK")
	else:
		print("HYBRID_AUTOPLAY_FAIL %s" % str(_fails))
	quit(0 if _fails.is_empty() else 1)
