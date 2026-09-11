extends DmbTestCase
## Puzzle catalogue rooms (docs/Duel_Master_Battle_Puzzle_Catalogue.txt):
## all 50 pz_01..pz_50 rooms well-formed, statically traversable, and
## smoke-playable through DmbPuzzleKit without errors.

const Kit = preload("res://sim/world/puzzle_kit.gd")
const Rooms = preload("res://sim/world/puzzle_rooms.gd")
const Items = preload("res://sim/world/items.gd")

const KNOWN_KINDS := ["goal", "gate", "plaque", "lever", "button", "plate",
	"receptacle", "rotator", "emitter", "receiver", "npc", "critter",
	"guardian", "board", "container", "choice", "magic_target", "teleporter",
	"pit", "hazard", "crumble", "marker", "sequence", "item", "pedestal"]
const DIRS := [Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 0), Vector2i(0, -1)]


func run() -> void:
	_test_catalogue_complete()
	_test_data_integrity()
	_test_goals_statically_reachable()
	_test_gated_items_appear()
	_test_sim_smoke_all_rooms()


func _rooms() -> Array:
	var all: Array = Rooms.all()
	all.sort_custom(func(a, b): return int(a["num"]) < int(b["num"]))
	return all


func _test_catalogue_complete() -> void:
	var all := _rooms()
	assert_eq(all.size(), 50, "catalogue has 50 rooms")
	var seen := {}
	for r in all:
		var want := "pz_%02d" % int(r["num"])
		assert_eq(str(r["id"]), want, "room id matches position")
		assert_true(not seen.has(str(r["id"])), "room id unique: " + str(r["id"]))
		seen[str(r["id"])] = true
		assert_true(str(r.get("title", "")) != "", "title: " + want)
		assert_true(str(r.get("mechanics", "")) != "", "mechanics: " + want)
		assert_true(str(r.get("hint", "")) != "", "hint: " + want)


func _test_data_integrity() -> void:
	for r in _rooms():
		var rid := str(r["id"])
		var rows: Array = r["rows"]
		assert_true(rows.size() >= 7, rid + " has rows")
		var w := str(rows[0]).length()
		assert_true(w >= 7, rid + " has columns")
		for line in rows:
			assert_eq(str(line).length(), w, rid + " rows rectangular")
		var h := rows.size()
		# Walled border keeps the player inside.
		for x in range(w):
			assert_eq(str(rows[0])[x], "#", rid + " top border")
			assert_eq(str(rows[h - 1])[x], "#", rid + " bottom border")
		for y in range(h):
			assert_eq(str(rows[y])[0], "#", rid + " left border")
			assert_eq(str(rows[y])[w - 1], "#", rid + " right border")
		assert_true(r.has("start"), rid + " has start")
		_assert_in_bounds(r, Kit._pos(r["start"]), rid + " start in bounds")
		var ids := {}
		var goals := 0
		for e in r["entities"]:
			assert_true(e is Dictionary, rid + " entity is dict")
			assert_true(str(e.get("id", "")) != "", rid + " entity has id")
			assert_true(not ids.has(str(e["id"])), rid + " entity id unique: " + str(e["id"]))
			ids[str(e["id"])] = true
			assert_true(str(e.get("kind", "")) in KNOWN_KINDS, rid + " known kind: " + str(e.get("kind")))
			if e.has("pos"):
				_assert_in_bounds(r, Kit._pos(e["pos"]), rid + "/" + str(e["id"]) + " pos in bounds")
			if str(e.get("kind")) == "goal":
				goals += 1
		assert_true(goals >= 1, rid + " has a goal")
		for it in r.get("items", []):
			assert_true(Items.known(str(it)), rid + " known item: " + str(it))
		for s in r.get("spells", []):
			assert_true(int(s) >= 0 and int(s) <= 6, rid + " valid spell: " + str(s))
		for e in r["entities"]:
			if e is Dictionary and str(e.get("kind", "")) == "item":
				assert_true(Items.known(str(e["item"])), rid + " known item: " + str(e["item"]))
		_test_interactables_standable(r, rid)


func _assert_in_bounds(r: Dictionary, p: Vector2i, what: String) -> void:
	var rows: Array = r["rows"]
	assert_true(p.x >= 0 and p.y >= 0 and p.y < rows.size() and p.x < str(rows[0]).length(), what)


func _test_gated_items_appear() -> void:
	# Two-stage puzzles (pz_04 idol drops when the grille opens, pz_37 key
	# floats up when the basin fills): an item gated behind a plain-flag
	# `requires` must be absent at start and present once its flag is set,
	# so the second half of the puzzle is actually reachable.
	for r in _rooms():
		var rid := str(r["id"])
		for e in r["entities"]:
			if not (e is Dictionary):
				continue
			if str(e.get("kind", "")) != "item" or not e.has("requires"):
				continue
			var req := str(e["requires"])
			if req.begins_with("!") or req == "":
				continue
			var st: Dictionary = Kit.fresh_state(r)
			var before := false
			for w in Kit.world_items(r, st):
				if str(w.get("src", "")) == str(e["id"]):
					before = true
			assert_true(not before, rid + " gated hidden at start:" + str(e["id"]))
			st["flags"][req] = true
			var after := false
			for w in Kit.world_items(r, st):
				if str(w.get("src", "")) == str(e["id"]):
					after = true
			assert_true(after, rid + " gated appears on flag:" + str(e["id"]))


func _test_interactables_standable(r: Dictionary, rid: String) -> void:
	var kinds := ["goal", "pit", "plate", "marker", "teleporter", "item"]
	for e in r["entities"]:
		if e is Dictionary and e.has("pos") and str(e.get("kind", "")) in kinds:
			var p := Kit._pos(e["pos"])
			assert_true(not (Kit.tile_char(r, p) in Kit.SOLID_CHARS),
				rid + " standable " + str(e.get("kind")) + ":" + str(e.get("id")))


func _test_goals_statically_reachable() -> void:
	# BFS over non-solid tiles from start, plus relocation edges (pits drop you,
	# teleporters fold you, ladder-type markers move you). Every goal must be
	# reachable with all gates open. Catches sealed rooms; dynamic gating
	# (flags, keys, sequences) is covered by the sim smoke test.
	for r in _rooms():
		var rid := str(r["id"])
		var jumps := _relocation_edges(r)
		var seen := {}
		var queue: Array = [Kit._pos(r["start"])]
		seen["%d,%d" % [queue[0].x, queue[0].y]] = true
		while not queue.is_empty():
			var p: Vector2i = queue.pop_back()
			var next: Array = []
			for d in DIRS:
				var n: Vector2i = p + d
				if Kit.tile_char(r, n) in Kit.SOLID_CHARS:
					continue
				next.append(n)
			if jumps.has("%d,%d" % [p.x, p.y]):
				for t in jumps["%d,%d" % [p.x, p.y]]:
					next.append(t)
			for n in next:
				var k := "%d,%d" % [n.x, n.y]
				if seen.has(k):
					continue
				seen[k] = true
				queue.append(n)
		for e in r["entities"]:
			if str(e.get("kind")) == "goal" and e.has("pos"):
				var gp := Kit._pos(e["pos"])
				assert_true(seen.has("%d,%d" % [gp.x, gp.y]), rid + " goal reachable: " + str(e["id"]))


## Extra BFS edges for travel that is not plain walking: pit falls, teleporter
## targets, and marker/npc on_enter relocations (ladders, slides, trapdoors).
func _relocation_edges(r: Dictionary) -> Dictionary:
	var jumps := {}
	for e in r["entities"]:
		if not (e is Dictionary and e.has("pos")):
			continue
		var from: Vector2i = Kit._pos(e["pos"])
		var dests: Array = []
		match str(e.get("kind", "")):
			"pit":
				dests.append(Kit._pos(e.get("fall_to", r["start"])))
			"teleporter":
				for t in e.get("targets", []):
					dests.append(Kit._pos(t))
		for fx in e.get("on_enter", []):
			if fx is Dictionary and (fx as Dictionary).has("relocate"):
				dests.append(Kit._pos((fx as Dictionary)["relocate"]))
		if not dests.is_empty():
			jumps["%d,%d" % [from.x, from.y]] = dests
	return jumps


func _test_sim_smoke_all_rooms() -> void:
	for r in _rooms():
		_smoke_room(r)


func _smoke_room(r: Dictionary) -> void:
	var rid := str(r["id"])
	var st: Dictionary = Kit.fresh_state(r)
	var inv: Array = (r.get("items", []) as Array).duplicate()
	var spells: Array = (r.get("spells", []) as Array).duplicate()
	Kit.sync_inventory(st, inv)
	var ctx := {"items": inv, "spells": spells}
	assert_true(st.has("player") and st.has("flags") and st.has("steps"), rid + " state well-formed")
	var vm: Dictionary = Kit.visual_map(r, st)
	assert_true(not vm.is_empty(), rid + " visual map non-empty")
	var dir_i := 0
	for step in range(300):
		var pp := Kit._pos(st["player"])
		# Interact with whatever is here or around.
		for d in [Vector2i.ZERO, DIRS[0], DIRS[1], DIRS[2], DIRS[3]]:
			var e: Dictionary = Kit.entity_at(r, st, pp + d)
			if e.is_empty():
				continue
			var acts: Array = Kit.actions_for(r, st, e, ctx)
			if acts.is_empty():
				continue
			var res: Dictionary = Kit.act(r, st, e, acts[step % acts.size()]["action"], ctx)
			assert_true(res.has("text") and res.has("changed"), rid + " result well-formed")
			for c in res.get("grant", []):
				inv.append(str(c))
			for c in res.get("consume", []):
				inv.erase(str(c))
			Kit.sync_inventory(st, inv)
		# Step somewhere passable.
		var moved := false
		for t in range(4):
			var d: Vector2i = DIRS[(dir_i + t) % 4]
			if not Kit.blocks(r, st, pp + d):
				var res2: Dictionary = Kit.on_step(r, st, pp + d, ctx)
				assert_true(res2.has("text"), rid + " step result well-formed")
				for c in res2.get("grant", []):
					inv.append(str(c))
				for c in res2.get("consume", []):
					inv.erase(str(c))
				Kit.sync_inventory(st, inv)
				dir_i = (dir_i + t + 1) % 4
				moved = true
				break
		if step % 5 == 0:
			var rt: Dictionary = Kit.tick(r, st, 0.1)
			assert_true(rt.has("changed"), rid + " tick result well-formed")
		if not moved:
			dir_i = (dir_i + 1) % 4
	assert_true(int(st["steps"]) > 0, rid + " steps advance")
