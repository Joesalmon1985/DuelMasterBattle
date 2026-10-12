extends SceneTree

## Headed M2 test: the Modern industry slice rendered from the live simulation (HYBRID_PROFILE=developer HYBRID_FIXTURE=modern_industry
## HYBRID_ALLOW_SPAWN=1). Fast-forwards the one simulation, then asserts rendered pixels and entities: machines drawn in their role
## colours, belt items moving between two frames, a blocked state, a produced Mindustry unit drawn on screen, and a fight with an
## OpenRA rifleman. Screenshots go to HYBRID_SHOT_DIR.

var _world: Node
var _fails: Array[String] = []
var _dir := ""
var _seq := 0


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, label: String) -> void:
	print("INDUSTRY %s %s" % ["ok  " if ok else "FAIL", label])
	if not ok:
		_fails.append(label)


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _image() -> Image:
	await _frames(3)
	await RenderingServer.frame_post_draw
	return get_root().get_viewport().get_texture().get_image()


func _shot(name: String) -> Image:
	var image := await _image()
	DirAccess.make_dir_recursive_absolute(_dir)
	image.save_png(_dir.replace("\\", "/") + "/%s.png" % name)
	print("INDUSTRY_SHOT %s" % name)
	return image


func _sim_advance(seconds: int) -> void:
	_seq = int(_world._snapshot.get("clock_sequence", _seq))
	_seq += 1
	var reply: Dictionary = _world._sim.op({"op": "advance", "ms": seconds * 1000, "sequence": _seq, "tree_delta": true})
	if str(reply.get("status", "")) == "ok":
		_world._apply_snapshot(reply.get("snapshot", {}))


func _machines() -> Dictionary:
	var out := {}
	for e in _world._snapshot.get("entities", []):
		if str(e.get("definition", "")).begins_with("mindustry.") and e.has("mdy"):
			out[str(e["kind"])] = e
	return out


func _to_screen(tile: Vector2) -> Vector2:
	var wp: Vector2 = (tile + Vector2(0.5, 0.5)) * float(_world.TPX)
	var sp: Vector2 = _world.get_canvas_transform() * wp
	return sp * (Vector2(get_root().get_visible_rect().size) / Vector2(get_root().get_visible_rect().size))


func _pixel(image: Image, tile: Vector2) -> Color:
	var sp := _to_screen(tile)
	var scale := Vector2(image.get_size()) / get_root().get_visible_rect().size
	return image.get_pixelv(Vector2i(sp * scale))


func _belt_items() -> Array:
	var out: Array = []
	for belt in _world._snapshot.get("industry", {}).get("belts", []):
		for it in belt[3]:
			out.append([int(belt[0]), int(belt[1]), int(it[1])])
	return out


func _focus_on_machines() -> void:
	var lo := Vector2(1e9, 1e9)
	var hi := Vector2(-1e9, -1e9)
	for e in _world._snapshot.get("entities", []):
		if str(e.get("definition", "")).begins_with("mindustry."):
			lo.x = min(lo.x, float(e["tx"]))
			lo.y = min(lo.y, float(e["ty"]))
			hi.x = max(hi.x, float(e["tx"]))
			hi.y = max(hi.y, float(e["ty"]))
	var c := (lo + hi) * 0.5 + Vector2(0.5, 0.5)
	_world.camera_focus = c * float(_world.TPX)
	var span: float = max(hi.x - lo.x, hi.y - lo.y) + 8.0
	var z: float = clampf(18.0 / span, 0.25, 0.9)
	_world._camera.zoom = Vector2(z, z)


func _cd(a: Color, b: Color) -> float:
	return sqrt(pow(a.r - b.r, 2) + pow(a.g - b.g, 2) + pow(a.b - b.b, 2))


func _diff(a: Image, b: Image) -> float:
	var n := 0
	var changed := 0
	var w := a.get_width()
	var h := a.get_height()
	for y in range(0, h, 3):
		for x in range(0, w, 3):
			n += 1
			if _cd(a.get_pixel(x, y), b.get_pixel(x, y)) > 0.08:
				changed += 1
	return float(changed) / float(max(n, 1))


func _run() -> void:
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
	if _dir == "":
		_dir = "res://../WizardRTSHybrid/docs/evidence/m2"
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	await _frames(40)
	_world.wizard_labels.enabled = false  # the wizard's label popups would cover the pictures this test samples
	var prof: Dictionary = _world._sim.op({"op": "profile"})
	_check(str(prof.get("profile", "")) == "developer", "developer profile with the fixture")
	var defs := 0
	for e in _world._snapshot.get("entities", []):
		if str(e.get("definition", "")).begins_with("mindustry."):
			defs += 1
	_check(defs >= 10, "the snapshot carries the Mindustry machines and belt sites (%d entities)" % defs)
	_focus_on_machines()
	await _frames(10)
	var start_img := await _shot("start_sites_under_construction")
	var sites := 0
	for e in _world._snapshot.get("entities", []):
		if str(e.get("definition", "")).begins_with("mindustry.") and e.has("constructing"):
			sites += 1
	_check(sites >= 6, "start: %d machine/belt sites are under construction" % sites)
	# fast-forward the one simulation until the belts carry items and the factory is built
	var t := 0
	while t < 75 * 60:
		_sim_advance(30)
		t += 30
		var live := 0
		for e in _world._snapshot.get("entities", []):
			if str(e.get("kind", "")) == "mdy:conveyor" and bool(e.get("line_live", false)):
				live += 1
		if live >= 4 and _belt_items().size() > 20 and _machines().has("mdy:ground_factory") and not _world._snapshot.get("entities", []).is_empty():
			var f: Dictionary = _machines()["mdy:ground_factory"]
			if not f.has("constructing") and str(f["mdy"]["state"]) in ["building", "waiting for inputs", "no power"]:
				break
	_focus_on_machines()
	await _frames(10)
	var m := _machines()
	_check(m.has("mdy:ground_factory") and not m["mdy:ground_factory"].has("constructing"), "the ground factory is built")
	# frame A and B 0.4 s of real time apart: belt chevrons and items move
	var a := await _shot("working_a")
	var items_a := _belt_items().size()
	await create_timer(0.4).timeout
	var b := await _shot("working_b")
	_check(items_a > 10, "belts carry items in the snapshot (%d)" % items_a)
	_check(_diff(a, b) > 0.0005, "two rendered frames differ (moving belts), changed share %.4f" % _diff(a, b))
	# role colours drawn at machine centres
	for kind in ["mdy:silicon_smelter", "mdy:ground_factory", "mdy:solar_panel_large"]:
		if m.has(kind):
			var e: Dictionary = m[kind]
			var fp: Array = e.get("ground_footprint", [])
			var cx := 0.0
			var cy := 0.0
			for p in fp:
				cx += float(p[0])
				cy += float(p[1])
			var c := Vector2(cx / fp.size(), cy / fp.size())
			var px := _pixel(b, c)
			var base: Color = _world._art.industry.ROLE_COLOR[str(e["mdy"]["role"])]
			_check(_cd(px, base) < 0.55 or _cd(px, base.darkened(0.45)) < 0.55 or _cd(px, base.lightened(0.3)) < 0.55, "%s is drawn in its role colour (pixel %s)" % [kind, str(px)])
	# a blocked or no-power state is visible as text and darker colour
	var states := {}
	for k in m:
		states[k] = str(m[k]["mdy"]["state"])
	print("INDUSTRY states ", states)
	_check(states.size() >= 5, "every machine kind reports a state (%d kinds)" % states.size())
	# run until the unit exists
	t = 0
	var unit := {}
	while t < 60 * 60 and unit.is_empty():
		_sim_advance(20)
		t += 20
		for e in _world._snapshot.get("entities", []):
			if str(e.get("definition", "")) == "mindustry.dagger":
				unit = e
	_check(not unit.is_empty(), "a Mindustry dagger exists in the shared entity list")
	if not unit.is_empty():
		_focus_on_machines()
		_world.camera_focus = (Vector2(float(unit["tx"]), float(unit["ty"])) + Vector2(0.5, 0.5)) * float(_world.TPX)
		_world._camera.zoom = Vector2(0.7, 0.7)
		await _frames(10)
		var u_img := await _shot("unit_leaves_factory")
		var found := 0
		var sp := _to_screen(Vector2(float(unit["tx"]), float(unit["ty"])))
		var sc := Vector2(u_img.get_size()) / get_root().get_visible_rect().size
		for dy in range(-14, 15, 2):
			for dx in range(-14, 15, 2):
				var q := Vector2i((sp + Vector2(dx, dy)) * sc)
				if q.x >= 0 and q.y >= 0 and q.x < u_img.get_width() and q.y < u_img.get_height() and _cd(u_img.get_pixelv(q), Color(0.88, 0.9, 0.95)) < 0.12:
					found += 1
		_check(found >= 6, "the dagger's light triangle is drawn on its tile (%d matching pixels)" % found)
		# fight: an OpenRA rifleman of Blue walks into range
		var foe: Dictionary = _world._sim.op({"op": "spawn", "faction": "Blue", "definition": "openra.e1", "tx": int(unit["tx"]) + 3, "ty": int(unit["ty"])})
		_check(str(foe.get("status", "")) == "ok", "spawned an OpenRA rifleman (needs HYBRID_ALLOW_SPAWN=1): %s" % str(foe.get("reason", "ok")))
		if str(foe.get("status", "")) == "ok":
			_world._sim.op({"op": "order", "unit": str(unit["id"]), "target": str(foe["id"])})
			_world._sim.op({"op": "order", "unit": str(foe["id"]), "target": str(unit["id"])})
			var fought := false
			for i in 30:
				_sim_advance(1)
				await _frames(2)
				if i == 2:
					await _shot("fight")
				var foe_alive := false
				for e in _world._snapshot.get("entities", []):
					if str(e.get("id", "")) == str(foe["id"]):
						foe_alive = true
				if not foe_alive:
					fought = true
					break
			_check(fought, "the OpenRA rifleman is destroyed by the Mindustry unit")
			await _shot("fight_won")
	if _fails.is_empty():
		print("HYBRID_INDUSTRY_OK")
		quit(0)
	else:
		print("HYBRID_INDUSTRY_FAIL %s" % ", ".join(_fails))
		quit(1)
