extends SceneTree

## Headed M3 test: the settlement story, driven through the real Godot UI over the one simulation. Needs the sim started with
## HYBRID_PROFILE=developer HYBRID_FIXTURE=story (a genuine Widelands coal mine whose reserve has run dry; the person, the quest and
## the dungeon come from that state). Real mouse clicks open the dialogue and press its buttons, real key presses enter the gallery and
## walk the first room, and the duel is played by clicking the colour buttons. Remaining dungeon moves are sent through the same UI ops.

var _world: Node
var _ui: Node
var _fails: Array[String] = []
var _dir := ""
var _seq := 0


func _init() -> void:
	call_deferred("_run")


func _check(ok: bool, label: String) -> void:
	print("STORY %s %s" % ["ok  " if ok else "FAIL", label])
	if not ok:
		_fails.append(label)


func _frames(n: int) -> void:
	for _i in n:
		await process_frame


func _win(pos: Vector2) -> Vector2:
	return pos * (Vector2(DisplayServer.window_get_size()) / get_root().get_visible_rect().size)


func _mouse(vpos: Vector2, pressed: bool) -> void:
	var pos := _win(vpos)
	var e := InputEventMouseButton.new()
	e.position = pos
	e.global_position = pos
	e.button_index = MOUSE_BUTTON_LEFT
	e.pressed = pressed
	e.button_mask = 1 if pressed else 0
	Input.parse_input_event(e)


func _click_at(vpos: Vector2) -> void:
	var m := InputEventMouseMotion.new()
	m.position = _win(vpos)
	m.global_position = _win(vpos)
	Input.parse_input_event(m)
	await _frames(1)
	_mouse(vpos, true)
	await _frames(1)
	_mouse(vpos, false)
	await _frames(4)


func _click_button(b: Button) -> void:
	await _click_at(b.get_global_rect().get_center())


func _key(code: int) -> void:
	for pressed in [true, false]:
		var e := InputEventKey.new()
		e.keycode = code
		e.physical_keycode = code
		e.pressed = pressed
		Input.parse_input_event(e)
		await _frames(1)
	await _frames(2)


func _shot(name: String) -> Image:
	await _frames(4)
	await RenderingServer.frame_post_draw
	var image: Image = get_root().get_viewport().get_texture().get_image()
	DirAccess.make_dir_recursive_absolute(_dir)
	image.save_png(_dir.replace("\\", "/") + "/%s.png" % name)
	print("STORY_SHOT %s" % name)
	return image


func _sim_advance(seconds: int) -> void:
	_seq = int(_world._snapshot.get("clock_sequence", _seq)) + 1
	var reply: Dictionary = _world._sim.op({"op": "advance", "ms": seconds * 1000, "sequence": _seq, "tree_delta": true})
	if str(reply.get("status", "")) == "ok":
		_world._apply_snapshot(reply.get("snapshot", {}))


func _entity(kind: String) -> Dictionary:
	for e in _world._snapshot.get("entities", []):
		if str(e.get("kind", "")) == kind and str(e.get("class", "")) in ["npc", "landmark"]:
			return e
	return {}


func _mine() -> Dictionary:
	for e in _world._snapshot.get("entities", []):
		if str(e.get("kind", "")) == "mine":
			return e
	return {}


func _teleport_next_to(e: Dictionary) -> void:
	for d in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1), Vector2i(2, 0), Vector2i(0, 2), Vector2i(-2, 0), Vector2i(0, -2)]:
		var t: Vector2i = Vector2i(int(e["tx"]), int(e["ty"])) + (d as Vector2i)
		if _world.is_walkable(t):
			_world.set_john_pos(t)
			_world._arrived()
			await _frames(3)
			return


func _focus(e: Dictionary, zoom := 0.9) -> void:
	_world.camera_focus = (Vector2(float(e["tx"]), float(e["ty"])) + Vector2(0.5, 0.5)) * float(_world.TPX)
	_world._camera.zoom = Vector2(zoom, zoom)


func _screen_of(e: Dictionary) -> Vector2:
	var wp: Vector2 = (Vector2(float(e["tx"]), float(e["ty"])) + Vector2(0.5, 0.5)) * float(_world.TPX)
	return _world.get_canvas_transform() * wp


func _cd(a: Color, b: Color) -> float:
	return sqrt(pow(a.r - b.r, 2) + pow(a.g - b.g, 2) + pow(a.b - b.b, 2))


func _count_near(img: Image, centre: Vector2, col: Color, tol: float, r := 36) -> int:
	var sc := Vector2(img.get_size()) / get_root().get_visible_rect().size
	var n := 0
	for dy in range(-r, r + 1, 2):
		for dx in range(-r, r + 1, 2):
			var q := Vector2i((centre + Vector2(dx, dy)) * sc)
			if q.x >= 0 and q.y >= 0 and q.x < img.get_width() and q.y < img.get_height() and _cd(img.get_pixelv(q), col) < tol:
				n += 1
	return n


# ---------------------------------------------------------------- dungeon helpers (BFS over the view the UI received)

func _bfs(goal_adjacent: Vector2i, goal_tile := Vector2i(-1, -1)) -> Array:
	var view: Dictionary = _ui.view
	var rows: Array = view["rows"]
	var pos := Vector2i(int(view["pos"][0]), int(view["pos"][1]))
	var solid := {}
	for e in view["entities"]:
		if str(e["kind"]) in ["door", "logs", "sign"]:
			solid[Vector2i(int(e["pos"][0]), int(e["pos"][1]))] = true
	var prev := {pos: pos}
	var q: Array = [pos]
	while not q.is_empty():
		var cur: Vector2i = q.pop_front()
		var done := cur == goal_tile if goal_tile != Vector2i(-1, -1) else absi(cur.x - goal_adjacent.x) + absi(cur.y - goal_adjacent.y) <= 1
		if done:
			var path: Array = []
			while cur != pos:
				path.push_front(cur)
				cur = prev[cur]
			return path
		for d in [Vector2i(0, -1), Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 0)]:
			var n: Vector2i = cur + d
			if prev.has(n) or n.y < 0 or n.y >= rows.size() or n.x < 0 or n.x >= String(rows[0]).length():
				continue
			if String(rows[n.y])[n.x] == "#" or solid.has(n):
				continue
			prev[n] = cur
			q.append(n)
	return []


func _walk_path(path: Array) -> void:
	var cur := Vector2i(int(_ui.view["pos"][0]), int(_ui.view["pos"][1]))
	for step in path:
		_ui._op({"op": "dungeon_move", "dx": step.x - cur.x, "dy": step.y - cur.y})
		cur = step
		await _frames(1)


func _go_adjacent(e: Dictionary) -> void:
	await _walk_path(_bfs(Vector2i(int(e["pos"][0]), int(e["pos"][1]))))


func _use(e: Dictionary, item := "", spell := -1) -> void:
	await _go_adjacent(e)
	var msg := {"op": "dungeon_interact", "entity": str(e["id"])}
	if item != "":
		msg["item"] = item
	if spell >= 0:
		msg["spell"] = spell
	_ui._op(msg)
	await _frames(2)


func _ents_in_room(room: int) -> Array:
	var oy := 1 + (3 - room) * 8
	var out: Array = []
	for e in _ui.view["entities"]:
		if int(e["pos"][1]) >= oy and int(e["pos"][1]) < oy + 7:
			out.append(e)
	return out


func _order_of(text: String) -> Array:
	var words := ["first", "second", "third", "fourth"]
	var rx := RegEx.new()
	rx.compile("(first|second|third|fourth)(?:, then (?:first|second|third|fourth))+")
	var m := rx.search(text)
	var out: Array = []
	var rx2 := RegEx.new()
	rx2.compile("first|second|third|fourth")
	for mm in rx2.search_all(m.get_string()):
		out.append(words.find(mm.get_string()))
	return out


func _solve_room(room: int) -> void:
	var ents := _ents_in_room(room)
	var clue := ""
	for e in ents:
		if str(e["id"]).ends_with("_clue"):
			clue = str(e["text"])
	var low := clue.to_lower()
	for e in ents:
		if str(e["kind"]) == "pickup" and not str(e["id"]).ends_with("_reward") and not str(e["id"]).ends_with("_sigil"):
			await _use(e)
	var mech: Array = []
	for e in _ents_in_room(room):
		if str(e["kind"]) == "logs":
			mech.append(e)
	mech.sort_custom(func(a, b): return str(a["id"]) < str(b["id"]))
	var inv: Array = _ui.view["inventory"]
	var locals := ["clay_idol", "brass_gear", "tallow_candle", "mirror_shard", "black_seed"]
	if low.contains("two niches"):
		var local := ""
		var sigil := ""
		for i in inv:
			if str(i).begins_with("sigil_"):
				sigil = str(i)
			elif str(i) in locals:
				local = str(i)
		await _use(mech[0], local)
		await _use(mech[1], sigil)
	elif low.contains("key sits on a plate"):
		var fodder := ""
		for i in inv:
			if str(i) in locals:
				fodder = str(i)
		await _use(mech[0], fodder)
		await _use(mech[0])
	elif low.contains("three levers"):
		for i in _order_of(clue):
			await _use(mech[int(i)])
	elif low.contains("four coloured stones"):
		for i in _order_of(clue):
			await _use(mech[int(i)])
	elif low.contains("a plate in the floor"):
		await _use(mech[0], "grey_stone")
	elif low.contains("pull the lever and the gate lifts"):
		var lever := {}
		var gate := {}
		for e in mech:
			if str(e["id"]).ends_with("_gate"):
				gate = e
			else:
				lever = e
		await _use(lever)
		await _use(gate)
	elif low.contains("wants a wizard"):
		await _use(mech[0], "", 1 if low.contains("brazier") else (6 if low.contains("chasm") else 0))
	elif low.contains("carved face says"):
		var said := 0 if low.contains("pull the left") else 1
		var liar := low.contains("the face lies")
		await _use(mech[1 - said if liar else said])


func _consistent_guess(history: Array) -> Array:
	var cands: Array = []
	for a in 6:
		for b in 6:
			for c in 6:
				for d in 6:
					cands.append([a, b, c, d])
	for h in history:
		var keep: Array = []
		for c in cands:
			var s := _score(c, h["guess"])
			if s[0] == h["exact"] and s[1] == h["colour"]:
				keep.append(c)
		cands = keep
	if cands.is_empty():
		print("STORY solver has no consistent code left: history ", history)
		return [0, 0, 1, 1]
	return cands[0] if not history.is_empty() else [0, 0, 1, 1]


func _score(secret: Array, guess: Array) -> Array:
	var exact := 0
	var sr: Array = []
	var gr: Array = []
	for i in 4:
		if secret[i] == guess[i]:
			exact += 1
		else:
			sr.append(secret[i])
			gr.append(guess[i])
	var colour := 0
	for g in gr:
		var idx := sr.find(g)
		if idx >= 0:
			colour += 1
			sr.remove_at(idx)
	return [exact, colour]


func _run() -> void:
	_dir = OS.get_environment("HYBRID_SHOT_DIR")
	if _dir == "":
		_dir = "res://../WizardRTSHybrid/docs/evidence/m3"
	_world = load("res://client/scenes/hybrid_world.tscn").instantiate()
	root.add_child(_world)
	DisplayServer.window_set_size(Vector2i(1280, 720))
	await _frames(40)
	_ui = _world.story_ui
	_world.wizard_labels.enabled = false
	var prof: Dictionary = _world._sim.op({"op": "profile"})
	_check(str(prof.get("profile", "")) == "developer", "developer profile with the story fixture")
	var npc := _entity("npc")
	var gallery := _entity("dungeon_entrance")
	_check(not npc.is_empty() and bool(npc.get("has_quest", false)), "the snapshot has a miner with a quest (from the real exhausted mine)")
	_check(not gallery.is_empty(), "the snapshot has the disused gallery entrance")
	var mine := _mine()
	_check(not mine.is_empty() and not npc.is_empty() and bool(npc.get("has_quest", false)), "the fixture's coal mine has caved in (since D22 mines never run dry) and its miner has a quest")
	# 1. the settlement at the start: the person with a quest marker beside the dry mine
	await _teleport_next_to(npc)
	_focus(npc)
	await _frames(8)
	var img := await _shot("01_miner_with_quest")
	var sp := _screen_of(npc)
	_check(_count_near(img, sp + Vector2(0, -60 * 0.9), Color(1.0, 0.85, 0.3), 0.25, 24) > 4, "a small gold quest mark is drawn over the miner (an ordinary worker figure under it)")
	# 2. real click on the person opens the dialogue with facts from the live world
	_world.wizard_labels.enabled = true
	await _click_at(sp)
	await _frames(10)
	var talk_btn: Button = _world.wizard_labels.panel.choice_button("talk")
	_check(_world.wizard_labels.panel.visible and talk_btn != null, "a real mouse click on the miner opens his card with Talk")
	if talk_btn != null:
		await _click_at(talk_btn.get_global_rect().get_center())
		await _frames(8)
	_world.wizard_labels.enabled = false
	_check(_ui.dialog.visible, "Talk opens the dialogue")
	var text := str(_ui.dialog_text.text)
	_check(text.contains("caved in") and text.contains("Timber props on site") and text.contains("The warehouse holds"), "the dialogue cites the real collapse, the props and the stock")
	await _shot("02_dialogue_offer")
	for c in ["ask_cause", "ask_gallery", "accept_help", "persuade"]:
		await _frames(4)
		await RenderingServer.frame_post_draw  # the card fits itself over two frames after its content changes: click where the button finally is
		var b: Button = _ui.dialog_card.choice_button(c)
		_check(b != null and not b.disabled, "choice %s is offered" % c)
		if b != null:
			_ui.dialog_card.scroll.ensure_control_visible(b)
			await _frames(3)
			await RenderingServer.frame_post_draw
			await _click_button(b)
	_check(str(_ui.dialog_text.text).contains("relents"), "the empathy check passes after the evidence was gathered")
	await _shot("03_dialogue_accepted")
	await _key(KEY_ESCAPE)
	_check(not _ui.dialog.visible, "Escape closes the dialogue")
	# 3. into the gallery with real keys
	await _teleport_next_to(gallery)
	_focus(gallery)
	await _frames(6)
	await _shot("04_gallery_entrance")
	await _key(KEY_E)
	_check(_ui.dungeon.visible and not _ui.view.is_empty(), "E at the entrance enters the dungeon (overlay shown)")
	await _frames(6)
	await _shot("05_dungeon_start")
	var start_y := int(_ui.view["pos"][1])
	var start_x := int(_ui.view["pos"][0])
	for i in 3:
		await _key(KEY_LEFT)
	_check(int(_ui.view["pos"][0]) == start_x - 3 and int(_ui.view["pos"][1]) == start_y, "three real Left key presses walk the wizard three tiles")
	for i in 3:
		await _key(KEY_RIGHT)
	# 4. four puzzle rooms
	for room in 4:
		await _solve_room(room)
		_check(bool(_ui.view["solved"][room]), "room %d answered" % (room + 1))
		await _shot("06_room_%d_solved" % (room + 1))
		if room < 3:
			var nxt_y := 1 + (3 - (room + 1)) * 8 + 6
			await _walk_path(_bfs(Vector2i(-1, -1), Vector2i(6, nxt_y)))
	# 5. the warden's duel, played by clicking the colour buttons
	var reward := {}
	for e in _ui.view["entities"]:
		if str(e["id"]).ends_with("_reward"):
			reward = e
	await _go_adjacent(reward)
	await _key(KEY_E)
	_check(_ui.duel.visible, "E at the plinth opens the warden's duel board")
	await _shot("07_duel_board")
	var history: Array = []
	var solved := false
	for cast in 12:
		var g := _consistent_guess(history)
		for slot in 4:
			var cb: Button = _ui.duel.get_node("VBoxContainer/Palette/Colour%d" % int(g[slot])) if _ui.duel.has_node("VBoxContainer/Palette") else null
			if cb == null:
				cb = _ui.duel.find_child("Colour%d" % int(g[slot]), true, false)
			await _click_button(cb)
		var cast_btn: Button = _ui.duel.find_child("Cast", true, false)
		await _click_button(cast_btn)
		var dview: Dictionary = _world._sim.op({"op": "story_view"}).get("duel", {})
		print("STORY duel view after cast ", cast, ": ", dview)
		if dview.is_empty():
			solved = true
			break
		if dview.get("guesses", []).is_empty():
			print("STORY no guess recorded: the click did not cast")
			break
		var last: Dictionary = dview["guesses"][dview["guesses"].size() - 1]
		var gi: Array = []
		for x in last["guess"]:
			gi.append(int(x))
		history.append({"guess": gi, "exact": int(last["exact"]), "colour": int(last["colour_only"])})
	print("STORY loop ended solved=", solved, " history=", history.size())
	_check(solved, "the code is broken with real clicks (%d casts)" % (history.size() + 1))
	await _shot("08_duel_won")
	# 6. out of the gallery, and the world has changed
	print("STORY view now: ", _ui.view.keys(), " pos ", _ui.view.get("pos"))
	var exit_pos := Vector2i(6, 32)
	await _walk_path(_bfs(Vector2i(-1, -1), exit_pos))
	await _frames(6)
	_check(not _ui.dungeon.visible, "walking onto the exit returns to the settlement")
	_sim_advance(60)
	await _frames(6)
	mine = _mine()
	_check(int(mine.get("deposit_left", 0)) > 0 and not bool(mine.get("deposit_exhausted", false)), "the mine's reserve is back (deposit_left %d)" % int(mine.get("deposit_left", 0)))
	npc = _entity("npc")
	_check(not bool(npc.get("has_quest", true)) and str(npc.get("quest_status", "")) == "completed", "the person's quest is completed")
	_focus(mine)
	await _frames(8)
	var after := await _shot("09_mine_working_again")
	var npc_now := _entity("npc")
	_check(npc_now.is_empty() or not bool(npc_now.get("has_quest", true)), "the miner no longer carries a quest mark (the simulation says so; the picture follows the snapshot)")
	if _fails.is_empty():
		print("HYBRID_STORY_OK")
		quit(0)
	else:
		print("HYBRID_STORY_FAIL %s" % ", ".join(_fails))
		quit(1)
