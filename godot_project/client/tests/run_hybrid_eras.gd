extends SceneTree

## Headed M4 test: the historic -> modern transition and the full-cycle reset, watched through the real HUD. Needs the sim with
## HYBRID_PROFILE=developer HYBRID_ERA_MS=20000 HYBRID_ERA_VP=99 (a short stall guard so every era ends in 20 game seconds; the VP bar is
## out of reach, so the transition is the stall guard's). The clock runs at 6x. The same land must come back after the reset.

var _world: Node
var _fails: Array[String] = []
var _dir := ""


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, label: String) -> void:
	print("ERAS %s %s" % ["ok  " if ok else "FAIL", label])
	if not ok:
		_fails.append(label)


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _shot(name: String) -> void:
	await _frames(4)
	await RenderingServer.frame_post_draw
	var image: Image = get_root().get_viewport().get_texture().get_image()
	DirAccess.make_dir_recursive_absolute(_dir)
	image.save_png(_dir.replace("\\", "/") + "/%s.png" % name)
	print("ERAS_SHOT %s" % name)


func _red_kinds() -> Dictionary:
	var out := {}
	for e in _world._snapshot.get("entities", []):
		if str(e.get("faction_name", "")) == "Red" and str(e.get("class", "")) == "building":
			out[str(e.get("kind", ""))] = int(out.get(str(e.get("kind", "")), 0)) + 1
	return out


func _run() -> void:
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
	if _dir == "":
		_dir = "res://../WizardRTSHybrid/docs/evidence/m4"
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	await _frames(40)
	var prof: Dictionary = _world._sim.op({"op": "profile"})
	_check(str(prof.get("profile", "")) == "developer", "sim profile is developer")
	_check(_world.era_hud != null and _world.era_hud.text.contains("prehistoric"), "the HUD names the first era: '%s'" % _world.era_hud.text)
	var map_hash := str(_world._snapshot.get("map", {}).get("static_hash", ""))
	var seed0 := int(_world._snapshot.get("seed", 0))
	_check(map_hash != "", "the map carries a static hash")
	await _shot("era_prehistoric")
	_world._sim.op({"op": "speed", "scale": 6})
	var seen: Array[String] = []
	var shots := {}
	var reset_seen := false
	var last_cycle := 0
	for _i in range(3000):
		await _frames(3)
		var era := str(_world._snapshot.get("era", {}).get("era", ""))
		if era != "" and (seen.is_empty() or seen[-1] != era):
			seen.append(era)
			print("ERAS era -> %s at %d ms" % [era, int(_world._snapshot.get("game_ms", 0))])
			if not shots.has(era):
				shots[era] = true
				await _shot("era_%s" % era)
		last_cycle = int(_world._snapshot.get("history", {}).get("cycle", 0))
		if last_cycle >= 1:
			reset_seen = true
			break
	_check(seen.size() >= 4 and seen.slice(0, 4) == ["prehistoric", "historic", "modern", "dystopian"], "the HUD walked the four eras in order: %s" % str(seen))
	_check(reset_seen, "the cycle ended and a new one began")
	if reset_seen:
		await _frames(30)
		_world._sim.op({"op": "speed", "scale": 1})
		await _frames(10)
		var after_era := str(_world._snapshot.get("era", {}).get("era", ""))
		_check(after_era == "prehistoric", "the new cycle opens in the first era (got %s)" % after_era)
		_check(str(_world._snapshot.get("map", {}).get("static_hash", "")) == map_hash, "the land is the same land after the reset")
		_check(int(_world._snapshot.get("seed", 0)) != seed0, "the run's randomness moved on")
		_check(_world.era_hud.text.begins_with("Cycle 1"), "the HUD shows cycle 1: '%s'" % _world.era_hud.text)
		var kinds := _red_kinds()
		_check(kinds.has("warehouse") and not kinds.has("mine") and not kinds.has("smithy") and not kinds.has("barracks"), "Red starts again from the primitive opening: %s" % str(kinds))
		var tech: Dictionary = _world._sim.op({"op": "tech"})
		_check(tech["tech"]["factions"]["Red"]["cards"].size() <= 1, "no card survived the reset")
		await _shot("cycle_1_start")
	if _fails.is_empty():
		print("HYBRID_ERAS_OK")
	else:
		print("HYBRID_ERAS_FAIL %s" % str(_fails))
	quit(0 if _fails.is_empty() else 1)
