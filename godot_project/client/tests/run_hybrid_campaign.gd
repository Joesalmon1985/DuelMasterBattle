extends SceneTree

## Headed campaign / developer profile test (M1). HYBRID_EXPECT=campaign (default): the God Mode button is hidden, the G key does
## nothing, a direct God command is rejected by the simulator, and the rendered opening is a primitive settlement. HYBRID_EXPECT=developer:
## God Mode opens, the tech panel shows a draft offer, and drafting through the real button unlocks a kind in the simulation.
## The sim must run with HYBRID_PROFILE set to the same value.

var _world: Node
var _fails: Array[String] = []
var _dir := ""


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, label: String) -> void:
	print("CAMPAIGN %s %s" % ["ok  " if ok else "FAIL", label])
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
	print("CAMPAIGN_SHOT %s" % name)


func _key(code: int) -> void:
	for pressed in [true, false]:
		var e := InputEventKey.new()
		e.keycode = code
		e.physical_keycode = code
		e.pressed = pressed
		Input.parse_input_event(e)
	await _frames(4)


func _kinds(faction: String) -> Dictionary:
	var out := {}
	for e in _world._snapshot.get("entities", []):
		if str(e.get("faction_name", "")) == faction and str(e.get("class", "")) == "building":
			out[str(e.get("kind", ""))] = true
	return out


func _run() -> void:
	var expect := OS.get_environment("HYBRID_EXPECT")
	if expect == "":
		expect = "campaign"
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
	if _dir == "":
		_dir = "res://../WizardRTSHybrid/docs/evidence/m1"
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	await _frames(40)
	var god: Node = _world.god
	var prof: Dictionary = _world._sim.op({"op": "profile"})
	_check(str(prof.get("profile", "")) == expect, "sim profile is %s (got %s)" % [expect, str(prof.get("profile", ""))])
	var snap_tech: Dictionary = _world._snapshot.get("tech", {})
	_check(snap_tech.has("factions") and snap_tech["factions"].size() == 6, "snapshot carries six factions' tech state")
	for f in ["Red", "Blue", "Green", "Yellow", "Purple", "Orange"]:
		var kinds := _kinds(f)
		_check(not kinds.has("mine") and not kinds.has("smithy") and not kinds.has("barracks") and not kinds.has("vehicle_factory"), "%s opens without mines, smithy, barracks or factory" % f)
		_check(kinds.has("warehouse") and kinds.has("producer") and kinds.has("quarry"), "%s has warehouse, woodcutter, quarry" % f)
	await _shot("%s_start" % expect)
	if expect == "campaign":
		_check(not god.god_enabled, "God Mode disabled in campaign")
		_check(not god.mode_btn.visible, "no God Mode button is drawn")
		await _key(KEY_G)
		_check(not god.active, "the G key does not enter God Mode")
		var rej: Dictionary = _world._sim.op({"op": "build", "faction": "Red", "kind": "quarry", "tx": 1, "ty": 1})
		_check(str(rej.get("reason", "")) == "god_mode_disabled", "a direct God command is rejected by the simulator")
		var tick: Dictionary = _world._sim.op({"op": "advance", "ms": 100, "sequence": 999999})
		_check(str(tick.get("status", "")) == "ok" or str(tick.get("reason", "")) != "god_mode_disabled", "the wizard's own clock ops still work")
	else:
		# Red is played by the AI until controlled, and the AI drafts at once: take the faction first, then wait for a round to open
		_world._sim.op({"op": "control", "faction": "Red"})
		var reply: Dictionary = _world._sim.op({"op": "tech"})
		var offers: Array = reply["tech"]["factions"]["Red"]["offers"]
		for _i in range(600):
			if offers.size() > 0:
				break
			await _frames(2)
			reply = _world._sim.op({"op": "tech"})
			offers = reply["tech"]["factions"]["Red"]["offers"]
		_check(god.god_enabled and god.mode_btn.visible, "God Mode button is shown in developer")
		await _key(KEY_G)
		_check(god.active, "G enters God Mode in developer")
		god.choose_faction("Red")
		await _frames(10)
		var tech: Dictionary = _world._snapshot.get("tech", {}).get("factions", {}).get("Red", {})
		# the first draft round opens at the first tick
		_check(offers.size() > 0, "Red has a draft offer after the first tick")
		if offers.is_empty():
			quit(1)
			return
		god._refresh_info()
		_world._apply_snapshot(_world._sim.op({"op": "snapshot"}).get("snapshot", {}))
		god._last_actions_key = ""
		god._refresh_info()
		await _frames(6)
		var btn: Button = null
		for c in god.actions.get_children():
			if c is Button and c.text == "Draft %s" % str(offers[0]).replace("dmb.card.", ""):
				btn = c
		_check(btn != null, "the panel shows a Draft button for %s" % str(offers[0]))
		await _shot("developer_offer")
		if btn != null:
			btn.pressed.emit()
			await _frames(4)
		var after: Dictionary = _world._sim.op({"op": "tech"})
		_check(after["tech"]["factions"]["Red"]["cards"].has(str(offers[0])), "drafting through the button adds the card in the simulation")
		var owned: Array = after["tech"]["factions"]["Red"]["cards"]
		var farm_btn: Button = god.build_grid.get_node_or_null("Build_farm")
		var mine_btn: Button = god.build_grid.get_node_or_null("Build_mine")
		_check(farm_btn != null and mine_btn != null, "the build menu lists Farm and Coal mine")
		var drafted := str(offers[0])
		var unlocks_farm := owned.has("dmb.card.farming")
		var unlocks_mine := owned.has("dmb.card.mining")  # the AI may have drafted for Red before it was taken over
		if farm_btn != null and mine_btn != null:
			_check(mine_btn.disabled == (not unlocks_mine), "Coal mine button is %s with cards %s" % ["enabled" if unlocks_mine else "locked", str(owned)])
			_check(farm_btn.disabled == (not unlocks_farm), "Farm button is %s with cards %s" % ["enabled" if unlocks_farm else "locked", str(owned)])
		var barracks: Button = god.build_grid.get_node_or_null("Build_barracks")
		_check(barracks == null or barracks.disabled, "Barracks stays locked")
		await _shot("developer_drafted")
	if _fails.is_empty():
		print("HYBRID_CAMPAIGN_OK %s" % expect)
		quit(0)
	else:
		print("HYBRID_CAMPAIGN_FAIL %s" % ", ".join(_fails))
		quit(1)
