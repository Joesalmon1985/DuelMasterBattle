extends Node2D

## Character showcase: every character category, every animation, the dialogue portrait.
##
##   godot --path godot_project res://client/scenes/character_showcase.tscn                  (interactive)
##   godot --path godot_project --resolution 720x1280 res://client/scenes/character_showcase.tscn -- --shots=/some/dir
##
## Interactive: left/right = page, 1-9 = play a clip on the selected group, space = talk/stop, Esc = quit.
## `--shots=DIR` walks through every page, writes a PNG per page (and a filmstrip of frames for the animated ones) and quits.

const Lib = preload("res://client/characters/character_library.gd")
const Look = preload("res://client/characters/character_look.gd")
const Anim = preload("res://client/characters/character_anim.gd")
const Appearance = preload("res://client/characters/character_appearance.gd")
const Bus = preload("res://client/characters/character_bus.gd")
const Render = preload("res://client/characters/character_renderer.gd")
const Portrait = preload("res://client/characters/dialogue_portrait.gd")

const PAGES := ["wizards", "named", "labour", "military", "walk", "clips", "frames_wizard_front", "frames_wizard_side", "frames_wizard_back", "frames_villager_front", "frames_villager_side", "dialogue", "crowd"]
const S := 3.0  # pixel scale

var page := 0
var entries: Array = []      # {look, anim, pos, label, moving, dir, home}
var portraits: Array = []
var _t := 0.0
var _shots_dir := ""
var _shot_i := 0
var _title := Label.new()
var _hint := Label.new()
var _ui: CanvasLayer
var _crowd_seed := 0


func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--shots="):
			_shots_dir = a.substr(8)
	_ui = CanvasLayer.new()
	add_child(_ui)
	_title.position = Vector2(14, 8)
	_title.add_theme_font_size_override("font_size", 26)
	_title.add_theme_color_override("font_outline_color", Color(0, 0, 0, 1))
	_title.add_theme_constant_override("outline_size", 6)
	_ui.add_child(_title)
	_hint.position = Vector2(14, 1236)
	_hint.add_theme_font_size_override("font_size", 15)
	_hint.text = "<- ->  page    1-9  play clip    space  talk    S  screenshot"
	_ui.add_child(_hint)
	_build(PAGES[0])
	if _shots_dir != "":
		_run_shots()


func _unhandled_input(ev: InputEvent) -> void:
	if not (ev is InputEventKey and ev.pressed and not ev.echo):
		return
	match ev.keycode:
		KEY_RIGHT:
			page = (page + 1) % PAGES.size()
			_build(PAGES[page])
		KEY_LEFT:
			page = (page + PAGES.size() - 1) % PAGES.size()
			_build(PAGES[page])
		KEY_SPACE:
			for e in entries:
				if Bus.is_speaking(e.id):
					Bus.stop_speaking(e.id)
				else:
					Bus.speak(e.id)
		KEY_ESCAPE:
			get_tree().quit()
		KEY_S:
			_save("%s/showcase_%s.png" % [OS.get_user_data_dir(), PAGES[page]])
		_:
			if ev.keycode >= KEY_1 and ev.keycode <= KEY_9:
				_play_clip(ev.keycode - KEY_1)


const CLIP_KEYS := ["idle", "walk", "talk", "hurt", "die", "surprise", "work", "cast", "celebrate"]


func _play_clip(i: int) -> void:
	var c: String = CLIP_KEYS[i]
	for e in entries:
		match c:
			"idle":
				e.moving = false
				Bus.stop_speaking(e.id)
				e.anim.dead = false
			"walk":
				e.moving = true
			"talk":
				e.moving = false
				Bus.speak(e.id)
			"hurt":
				Bus.react(e.id, "hurt")
			"die":
				e.anim.dead = true
			"surprise":
				Bus.react(e.id, "surprise")
			"work":
				e.working = true
			"cast":
				Bus.react(e.id, "cast")
			"celebrate":
				Bus.react(e.id, "celebrate")


func _add(look, pos: Vector2, label: String, id: String = "") -> Dictionary:
	var eid := id if id != "" else "show%d" % entries.size()
	var e := {"look": look, "anim": Anim.new(look, eid), "pos": pos, "label": label, "moving": false, "working": false, "dir": Vector2.ZERO, "home": pos, "id": eid}
	entries.append(e)
	return e


func _clear() -> void:
	labels.clear()
	entries.clear()
	for p in portraits:
		p.queue_free()
	portraits.clear()
	Bus.reset()


func _grid(looks: Array, labels: Array, cols: int, origin: Vector2, cell: Vector2) -> void:
	for i in looks.size():
		var p := origin + Vector2((i % cols) * cell.x, (i / cols) * cell.y)
		_add(looks[i], p, labels[i] if i < labels.size() else "")


func _build(name: String) -> void:
	_clear()
	_title.text = "Characters - " + name
	match name:
		"wizards":
			var looks := []
			var labels := []
			var cols := [Color("#d63a3a"), Color("#3a6ad6"), Color("#3fae49"), Color("#e0c63a"), Color("#8e4ad0"), Color("#e8892e")]
			for i in 6:
				var pid := "p%d" % (i + 1)
				looks.append(Appearance.for_player(pid, "Player %d" % (i + 1), cols[i].to_html(false)))
				labels.append("wizard cut %d" % (i + 1))
			for n in ["john_staff", "archmage", "mirror_mage", "thorn_adept", "eightfold_warden", "blue_apprentice"]:
				looks.append(Appearance.named(n))
				labels.append(n)
			_grid(looks, labels, 3, Vector2(30, 80), Vector2(235, 300))
		"named":
			var names := ["john", "halvard", "red_mage", "hedge_mage", "reaper", "assassin", "knight", "dwarf", "elf", "elder", "igbut", "ivy", "official", "matron", "throm", "child", "shepherd", "villager_b"]
			var looks2 := []
			for n in names:
				looks2.append(Appearance.named(n))
			_grid(looks2, names, 3, Vector2(30, 70), Vector2(235, 200))
		"labour":
			var jobs := ["carrier", "farmer", "baker", "woodcutter", "forester", "miner", "smith", "builder", "mason", "fisher", "hunter", "cook", "brewer", "miller", "carpenter", "weaver", "digger", "herder", "gardener", "scout", "geologist", "charcoal", "shipwright", "merchant"]
			var looks3 := []
			for j in jobs:
				looks3.append(Look.store(Look.make("show:" + j, j, Lib.stable_hash("show:" + j), {"tribe": Appearance.TRIBES[jobs.find(j) % 5]})))
			_grid(looks3, jobs, 4, Vector2(10, 60), Vector2(178, 150))
		"military":
			var m := ["soldier_barbarian", "soldier_empire", "soldier_atlantean", "soldier_frisian", "soldier_amazon", "clubman", "spearman", "slinger", "e1", "e2", "e3", "e4", "e6", "e7", "spy", "thief", "medic", "mechanic", "shock", "zombie", "trainer", "recruit", "settler", "healer"]
			var looks4 := []
			for j in m:
				looks4.append(Look.store(Look.make("show:" + j, j, Lib.stable_hash("show:" + j), {"tribe": Appearance.TRIBES[m.find(j) % 5]})))
			_grid(looks4, m, 4, Vector2(10, 60), Vector2(178, 150))
		"walk":
			# one wizard and one villager, walking in the four directions
			for r in 2:
				var look = Appearance.named("john_staff") if r == 0 else Appearance.for_entity({"id": "w:7", "definition": "widelands.lumberjack_worker", "faction_name": "Red", "class": "worker"})
				for d in 4:
					var e := _add(look, Vector2(60 + d * 170, 180 + r * 300), ["down", "left", "right", "up"][d])
					e.anim.set_facing(["down", "left", "right", "up"][d])
					e.moving = true
					e.fixed = true
		"clips":
			var look5 = Appearance.named("archmage")
			var look6 = Appearance.for_entity({"id": "w:9", "definition": "widelands.empire_baker_worker", "faction_name": "Blue", "class": "worker"})
			var i := 0
			for c in ["idle", "walk", "talk", "hurt", "surprise", "cast", "celebrate", "die"]:
				var e := _add(look5 if c in ["cast", "celebrate"] or i % 2 == 0 else look6, Vector2(40 + (i % 4) * 175, 120 + (i / 4) * 330), c)
				e.clip = c
				e.fixed = true
				i += 1
		"dialogue":
			var np = Appearance.named("elder")
			var pl = Appearance.named("john_staff")
			_add(np, Vector2(110, 640), "elder", "elder").anim.set_facing("right")
			_add(pl, Vector2(430, 640), "john", "john").anim.set_facing("left")
			var moods := ["neutral", "smile", "worried", "surprised", "angry"]
			for i in 5:
				var p := Portrait.new()
				p.position = Vector2(20 + i * 138, 110)
				p.custom_minimum_size = Vector2(128, 128)
				p.size = Vector2(128, 128)
				add_child(p)
				p.show_person(np, "mood%d" % i)
				p.set_mood(moods[i])
				portraits.append(p)
			for i in 3:
				var q := Portrait.new()
				q.position = Vector2(20 + i * 138, 300)
				q.size = Vector2(128, 128)
				add_child(q)
				q.show_person([Appearance.named("matron"), Appearance.named("igbut"), Appearance.named("ivy")][i], ["matron", "igbut", "ivy"][i])
				portraits.append(q)
			Bus.speak("elder")
			Bus.speak("matron")
			Bus.speak("igbut")
			Bus.speak("ivy")
		"crowd":
			_crowd_seed = 4
			var e0 := {"definition": "widelands.carrier", "faction_name": "Blue", "class": "carrier"}
			var defs := ["widelands.carrier", "widelands.lumberjack_worker", "widelands.empire_baker_worker", "widelands.barbarians_miner_worker", "widelands.farmer_worker", "widelands.empire_smelter_worker"]
			for i in 60:
				var d: String = defs[i % defs.size()]
				var e := {"id": "crowd:%d" % i, "definition": d, "faction_name": ["Red", "Blue", "Green", "Yellow", "Purple"][i % 5], "class": "worker"}
				var look = Appearance.for_entity(e)
				var en := _add(look, Vector2(30 + (i % 10) * 68, 90 + (i / 10) * 170), "", e.id)
				en.moving = i % 3 != 0
				en.dir = Vector2([1, -1, 0, 0][i % 4], [0, 0, 1, -1][i % 4]) * 0.6
		_:
			if name.begins_with("frames_"):
				_frames_page(name)


## Every frame of every clip, straight from the sheet, for inspection: one row per clip.
func _frames_page(name: String) -> void:
	var parts := name.split("_")
	var look = Appearance.named("archmage") if parts[1] == "wizard" else Appearance.for_entity({"id": "frame:baker", "definition": "widelands.empire_baker_worker", "faction_name": "Blue", "class": "worker"})
	var row: int = {"front": 0, "side": 1, "back": 2}[parts[2]]
	var clips: Array = Lib.data()["clip_sets"]["full" if parts[1] == "wizard" else "civil"]
	for ci in clips.size():
		var c: String = clips[ci]
		for f in Lib.clip_frames(c):
			var e := _add(look, Vector2(8 + f * 114, 56 + ci * 108), "", "frame%d_%d" % [ci, f])
			e["cell"] = Vector2i(Lib.clip_start(c) + f, row)
			e["scale"] = 2.0
			e["fixed"] = true
		_add_label(c, Vector2(8, 56 + ci * 108 + 2))


var labels: Array = []


func _add_label(text: String, pos: Vector2) -> void:
	labels.append({"text": text, "pos": pos})


func _process(delta: float) -> void:
	_t += delta
	for e in entries:
		var dir: Vector2 = e.dir
		if e.moving and dir == Vector2.ZERO and not e.get("fixed", false):
			dir = Vector2(1, 0)
		if e.moving and e.get("dir", Vector2.ZERO) != Vector2.ZERO:
			e.pos += dir * 60.0 * delta
			if e.pos.distance_to(e.home) > 60.0:
				e.dir = -dir
			e.anim.set_facing(Anim.facing_from_vector(e.dir, e.anim.facing))
		if e.has("cell"):
			continue
		if e.has("clip"):
			_drive_clip(e, delta)
		else:
			e.anim.update(delta, e.moving, e.working)
	queue_redraw()


## A tile in the "clips" page keeps showing one clip, restarting it when it ends so every animation can be inspected.
func _drive_clip(e: Dictionary, delta: float) -> void:
	var c: String = e.clip
	e.t = float(e.get("t", 0.0)) + delta
	match c:
		"idle":
			e.anim.update(delta, false)
		"walk":
			e.anim.update(delta, true)
		"talk":
			Bus.speak(e.id)
			e.anim.update(delta, false)
		"hurt", "surprise", "cast", "celebrate":
			if e.t > 1.6:
				e.t = 0.0
				Bus.react(e.id, c)
			e.anim.update(delta, false)
		"die":
			var cyc: float = fmod(e.t, 4.0)
			e.anim.dead = cyc < 2.6
			e.anim.update(delta, false)
		_:
			e.anim.update(delta, false)


func _draw() -> void:
	var vp := get_viewport_rect().size
	for y in range(0, int(vp.y), 64):
		for x in range(0, int(vp.x), 64):
			draw_rect(Rect2(x, y, 64, 64), Color(0.2, 0.4, 0.22) if ((x + y) / 64) % 2 == 0 else Color(0.22, 0.43, 0.24), true)
	Render.draws = 0
	var font := ThemeDB.fallback_font
	var sorted := entries.duplicate()
	sorted.sort_custom(func(a, b): return a.pos.y < b.pos.y)
	var cs := Lib.cell()
	for e in sorted:
		var origin: Vector2 = e.pos
		if e.has("cell"):
			Render.draw(self, e.look, e.cell, false, origin, float(e.scale), Color.WHITE, 0, true)
			continue
		Render.draw(self, e.look, e.anim.cell(), e.anim.flipped(), origin, S, Color.WHITE, 0, true)
		if e.label != "":
			var tw := font.get_string_size(e.label, HORIZONTAL_ALIGNMENT_LEFT, -1, 15).x
			draw_string(font, origin + Vector2(cs.x * S * 0.5 - tw * 0.5, cs.y * S + 16), e.label, HORIZONTAL_ALIGNMENT_LEFT, -1, 15, Color(1, 1, 1))
	for lb in labels:
		draw_string(font, lb.pos, lb.text, HORIZONTAL_ALIGNMENT_LEFT, -1, 14, Color(1, 1, 0.7))
	if PAGES[page] == "dialogue":
		draw_string(font, Vector2(20, 100), "moods: neutral smile worried surprised angry   |  speaking (mouth moves):", HORIZONTAL_ALIGNMENT_LEFT, -1, 15, Color(1, 1, 1))


func _save(path: String) -> void:
	var img := get_viewport().get_texture().get_image()
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	img.save_png(path)
	print("saved ", path)


func _run_shots() -> void:
	await get_tree().process_frame
	for i in PAGES.size():
		page = i
		_build(PAGES[i])
		if PAGES[i] == "walk" or PAGES[i] == "crowd":
			for e in entries:
				e.moving = true
		if PAGES[i] == "dialogue":
			Bus.speak("elder")
		for k in 30:
			await get_tree().process_frame
		_save("%s/%02d_%s.png" % [_shots_dir, i, PAGES[i]])
		# a filmstrip of consecutive frames for the animated pages
		if PAGES[i] in ["walk", "clips", "dialogue"]:
			for f in 12:
				for k in 5:
					await get_tree().process_frame
				_save("%s/film_%s_%02d.png" % [_shots_dir, PAGES[i], f])
	get_tree().quit(0)
