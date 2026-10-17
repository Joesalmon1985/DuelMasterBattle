extends SceneTree

## Character system: library, stable appearances, the animation state machine, the presentation bus, drawing.
##
## godot --headless --path godot_project --script res://client/tests/run_characters.gd

const Lib = preload("res://client/characters/character_library.gd")
const Look = preload("res://client/characters/character_look.gd")
const Anim = preload("res://client/characters/character_anim.gd")
const Appearance = preload("res://client/characters/character_appearance.gd")
const Bus = preload("res://client/characters/character_bus.gd")
const Render = preload("res://client/characters/character_renderer.gd")

var fails := 0


func check(cond: bool, what: String) -> void:
	if not cond:
		fails += 1
		print("FAIL: ", what)


func _init() -> void:
	run()


func run() -> void:
	test_library()
	test_roster()
	test_stability()
	test_anim()
	test_bus()
	await test_draw()
	if fails == 0:
		print("CHARACTERS: ALL PASSED")
		quit(0)
	else:
		print("CHARACTERS: %d FAILED" % fails)
		quit(1)


func test_library() -> void:
	check(Lib.available(), "characters.json loads through ResourceLoader")
	var d := Lib.data()
	var n := 0
	for id in d["outfits"]:
		n += 1
		check(Lib.texture("outfits/%s.png" % id) != null, "outfit sheet " + id)
		check(Lib.texture("outfits/%s_p.png" % id) != null, "portrait sheet " + id)
	check(n >= 60, "at least 60 outfits (%d)" % n)
	for body in d["hair_styles"]:
		for st in d["hair_styles"][body]:
			check(Lib.texture("hair/hair_%s_%s.png" % [body, st]) != null, "hair %s %s" % [body, st])
			check(Lib.texture("hair/hair_%s_%s_p.png" % [body, st]) != null, "hair portrait %s %s" % [body, st])
	for st in d["beard_styles"]:
		check(Lib.texture("hair/beard_adult_%s.png" % st) != null, "beard " + st)
	var tex: Texture2D = Lib.texture("outfits/farmer.png")
	var cs := Lib.cell()
	var cols := 0
	for c in d["clip_sets"]["civil"]:
		cols += Lib.clip_frames(c)
	check(tex.get_width() == cols * cs.x, "sheet width = frames x cell (%d vs %d)" % [tex.get_width(), cols * cs.x])
	check(tex.get_height() == cs.y * 3 * Lib.BANDS.size(), "sheet height = 3 views x bands")


func test_roster() -> void:
	var d := Lib.data()
	for def in ["widelands.carrier", "widelands.lumberjack_worker", "widelands.ranger_worker", "widelands.stonemason_worker", "widelands.farmer_worker", "widelands.hunter_worker",
			"widelands.barbarians_blacksmith_worker", "widelands.empire_baker_worker", "widelands.atlanteans_miner_worker", "widelands.frisians_brewer_worker",
			"widelands.soldier", "widelands.barbarians_soldier_worker", "openra.e1", "openra.e6", "openra.medi", "openra.spy", "dmb.settlers", "dmb.caravan", "dmb.clubman"]:
		check(Appearance.outfit_for_definition(def, "empire") != "", "definition maps to a person: " + def)
	check(Appearance.outfit_for_definition("widelands.bunny", "") == "", "animals are not people")
	check(Appearance.is_animal_definition("widelands.deer"), "deer is an animal")
	for name in d["named"]:
		var look = Appearance.named(name)
		check(look != null and Lib.has_outfit(look.outfit), "named character has an outfit: " + name)


func test_stability() -> void:
	var e := {"id": "worker:42", "definition": "widelands.lumberjack_worker", "faction_name": "Red", "class": "worker"}
	Appearance.faction_tribes["Red"] = "barbarians"
	var a = Appearance.for_entity(e).describe()
	Look._cache.clear()
	var b = Appearance.for_entity(e).describe()
	check(a == b, "the same entity id gives the same look after the cache is dropped")
	var seen := {}
	for i in 200:
		var l = Appearance.for_entity({"id": "worker:%d" % i, "definition": "widelands.carrier", "faction_name": "Red", "class": "carrier"})
		seen["%s|%s|%s|%s" % [l.hair_style, l.beard_style, l.tint_skin.to_html(), l.tint_a.to_html()]] = true
	check(seen.size() >= 60, "200 carriers show at least 60 distinct looks (%d)" % seen.size())
	check(Lib.stable_hash("worker:42") == Lib.stable_hash("worker:42") and Lib.stable_hash("a") != Lib.stable_hash("b"), "stable hash")
	check(Lib.stable_hash("hello") == 1335831723, "FNV-1a value is platform independent (%d)" % Lib.stable_hash("hello"))
	var j1 = Appearance.named("john").describe()
	var j2 = Appearance.for_sprite("john", "John").describe()
	check(j1 == j2, "a named character looks the same however it is asked for")
	var p1 = Appearance.for_player("p2", "Mira", "#3a6ad6").describe()
	Look._cache.clear()
	var p2 = Appearance.for_player("p2", "Mira", "#3a6ad6").describe()
	check(p1 == p2, "a LAN player's wizard is stable")
	var q = Appearance.for_player("p3", "Ode", "#d63a3a")
	check(q.outfit != Appearance.for_player("p2", "Mira", "#3a6ad6").outfit, "different players get different wizard cuts")


func _anim(clips := "civil") -> Anim:
	var look = Look.make("test", "wizard" if clips == "full" else "farmer", 12345, {"tribe": "empire"})
	return Anim.new(look, "t1")


func test_anim() -> void:
	Bus.reset()
	var a := _anim()
	for i in 10:
		a.update(0.1, false)
	check(a.state == Anim.S.IDLE, "starts idle")
	a.update(0.05, true)
	check(a.state == Anim.S.WALK, "movement interrupts idle")
	var frames := {}
	for i in 24:
		a.update(0.05, true)
		frames[a.frame] = true
	check(frames.size() == 6, "a walk cycle shows all 6 frames (%d)" % frames.size())
	for i in 10:
		a.update(0.05, false)
	check(a.state == Anim.S.IDLE, "stopping returns to idle")
	Bus.speak("t1", 5.0)
	a.update(0.05, false)
	check(a.state == Anim.S.TALK, "speaking while still talks")
	a.update(0.05, true)
	check(a.state == Anim.S.WALK, "walking wins over talking")
	for i in 5:
		a.update(0.05, false)
	check(a.state == Anim.S.TALK, "back to talking when the walk stops")
	Bus.stop_speaking("t1")
	a.update(0.05, false)
	check(a.state == Anim.S.IDLE, "stop speaking returns to idle")
	# facing and flipping
	a.set_facing("left")
	check(a.flipped() and a.cell().y == 1, "left uses the side row, mirrored")
	a.set_facing("up")
	check(not a.flipped() and a.cell().y == 2, "up uses the back row")
	# one-shot reactions and priority
	Bus.react("t1", "hurt")
	a.update(0.05, false)
	check(a.state == Anim.S.HURT, "hurt reaction")
	Bus.speak("t1", 5.0)
	a.update(0.05, false)
	check(a.state == Anim.S.HURT, "talking does not interrupt a hurt")
	for i in 20:
		a.update(0.05, false)
	check(a.state == Anim.S.TALK, "after the hurt the character returns to what it was doing")
	Bus.stop_speaking("t1")
	# death outranks everything and persists
	a.dead = true
	a.update(0.05, false)
	check(a.state == Anim.S.DYING, "death starts")
	Bus.speak("t1", 5.0)
	a.update(0.05, true)
	check(a.state == Anim.S.DYING, "a dying character does not talk or walk")
	for i in 40:
		a.update(0.05, true)
	check(a.state == Anim.S.DEAD and a.frame == Lib.clip_frames("die") - 1, "dead holds the last frame")
	Bus.react("t1", "hurt")
	a.update(0.05, false)
	check(a.state == Anim.S.DEAD, "nothing but a revival leaves death")
	a.dead = false
	a.update(0.05, false)
	check(a.state == Anim.S.REVIVING, "revival plays the fall backwards")
	for i in 30:
		a.update(0.05, false)
	check(a.state == Anim.S.TALK or a.state == Anim.S.IDLE, "revived character is alive again")
	# wizard-only clips fall back for ordinary people
	var civ := _anim()
	Bus.react("t1", "cast")
	civ.update(0.05, false)
	check(civ.clip != "cast", "a villager has no cast clip and does not draw a missing one")
	var wiz := _anim("full")
	Bus.react("t1", "cast")
	wiz.update(0.05, false)
	check(wiz.state == Anim.S.CAST and wiz.clip == "cast", "a wizard casts")
	Bus.reset()


func test_bus() -> void:
	Bus.reset()
	Bus.set_time(10.0)
	Bus.speak_text("x", "Hello there, wizard.")
	check(Bus.is_speaking("x"), "speaking after speak_text")
	Bus.set_time(10.5)
	check(Bus.is_speaking("x"), "still speaking half a second later")
	Bus.set_time(12.0)
	check(not Bus.is_speaking("x"), "stops after the line is over")
	Bus.speak("y")
	Bus.set_time(500.0)
	check(Bus.is_speaking("y"), "an open-ended line lasts until stopped")
	Bus.stop_speaking("y")
	check(not Bus.is_speaking("y"), "stopped")
	check(Bus.line_seconds("") >= 1.2 and Bus.line_seconds("x".repeat(220)) >= 9.9, "line length scales with text")
	Bus.reset()
	Bus.set_time(-1.0)


func test_draw() -> void:
	var host := Sprite2D.new()
	root.add_child(host)
	var view = preload("res://client/characters/character_view.gd").new()
	host.add_child(view)
	view.setup(Look.make("draw", "farmer", 7, {"tribe": "frisians"}), "draw")
	var before := Render.draws
	await process_frame
	await process_frame
	check(Render.draws > before, "a character view draws its cell")
	# the view reads the parent's motion: moving the parent starts the walk without anyone calling the animation
	for i in 6:
		host.position += Vector2(3, 0)
		await process_frame
	check(view.anim.state == Anim.S.WALK and view.anim.facing == "right", "moving the parent walks to the right (%s %s)" % [view.anim.state_name(), view.anim.facing])
	for i in 20:
		await process_frame
	check(view.anim.state == Anim.S.IDLE, "and standing still idles again")
	host.queue_free()
