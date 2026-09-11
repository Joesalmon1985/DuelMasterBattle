extends SceneTree
## TEMP QA tool (not shipped): walks every catalogue room from start to its
## goal tile (BFS, gates open, relocation edges like the reachability test),
## stepping through Kit.on_step, and dumps start/mid/end frames (player pos,
## solved flag, visual_map) plus the full position trace as JSON lines to
## room_walk.json. Proves the player token can traverse each room start->finish.

const Kit = preload("res://sim/world/puzzle_kit.gd")
const Rooms = preload("res://sim/world/puzzle_rooms.gd")

const DIRS := [Vector2i(1, 0), Vector2i(0, 1), Vector2i(-1, 0), Vector2i(0, -1)]


func _init() -> void:
	var rooms: Array = Rooms.all()
	rooms.sort_custom(func(a, b): return int(a["num"]) < int(b["num"]))
	var f := FileAccess.open("res://room_walk.json", FileAccess.WRITE)
	var n := 0
	for r in rooms:
		f.store_line(JSON.stringify(_walk(r)))
		n += 1
	f.close()
	print("WALK_DONE rooms=%d" % n)
	quit()


func _walk(room: Dictionary) -> Dictionary:
	var st: Dictionary = Kit.fresh_state(room)
	var ctx := {"items": room.get("items", []), "spells": room.get("spells", [])}
	Kit.sync_inventory(st, ctx["items"])
	var path := _bfs_path(room)
	var frames: Array = [_frame(room, st, 0)]
	var trace: Array = []
	var step := 0
	for p in path:
		if Kit.blocks(room, st, p):
			trace.append({"to": [p.x, p.y], "blocked": true})
			continue
		step += 1
		var res: Dictionary = Kit.on_step(room, st, p, ctx)
		trace.append({"to": [p.x, p.y], "solved_now": bool(res.get("solved_now", false))})
		if step == path.size() / 2:
			frames.append(_frame(room, st, step))
	frames.append(_frame(room, st, step))
	return {
		"id": str(room["id"]), "num": int(room["num"]),
		"title": str(room["title"]), "rows": room["rows"],
		"start": room["start"], "path_len": path.size(), "steps": step,
		"solved": bool(st["solved"]), "frames": frames, "trace": trace,
	}


func _frame(room: Dictionary, st: Dictionary, step: int) -> Dictionary:
	return {
		"step": step, "player": (st["player"] as Array).duplicate(),
		"solved": bool(st["solved"]),
		"extra": Kit.visual_map(room, st),
	}


func _bfs_path(room: Dictionary) -> Array:
	var rows: Array = room["rows"]
	var w := str(rows[0]).length()
	var h := rows.size()
	var start := Kit._pos(room["start"])
	var goals := []
	for e in room["entities"]:
		if e is Dictionary and str(e.get("kind", "")) == "goal" and e.has("pos"):
			goals.append(Kit._pos(e["pos"]))
	if goals.is_empty():
		return []
	var jump := {}
	for e in room["entities"]:
		if not (e is Dictionary and e.has("pos")):
			continue
		var from: Vector2i = Kit._pos(e["pos"])
		var dests: Array = []
		match str(e.get("kind", "")):
			"pit":
				dests.append(Kit._pos(e.get("fall_to", room["start"])))
			"teleporter":
				for t in e.get("targets", []):
					dests.append(Kit._pos(t))
		for fx in e.get("on_enter", []):
			if fx is Dictionary and (fx as Dictionary).has("relocate"):
				dests.append(Kit._pos((fx as Dictionary)["relocate"]))
		if not dests.is_empty():
			jump[from] = dests
	var prev := {start: null}
	var queue := [start]
	while not queue.is_empty():
		var cur: Vector2i = queue.pop_front()
		if cur in goals:
			var path := []
			var c = cur
			while c != start:
				path.push_front(c)
				c = prev[c]
			return path
		var nexts := []
		for d in DIRS:
			var np: Vector2i = cur + d
			if np.x >= 0 and np.y >= 0 and np.x < w and np.y < h \
					and str(rows[np.y])[np.x] != "#" and not prev.has(np):
				nexts.append(np)
		if jump.has(cur):
			for dest in jump[cur]:
				if not prev.has(dest):
					nexts.append(dest)
		for np in nexts:
			prev[np] = cur
			queue.append(np)
	return []
