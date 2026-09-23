extends RefCounted
class_name DmbEmbeddedDungeon
## Stamps a five-room wizard-dungeon reservation into an existing local-area
## dictionary (same tile map as roads/settlement/exits). Fixture-only —
## production dg_* loading is untouched.

const Spec = preload("res://sim/world/wizard_dungeon_spec.gd")

const WALK := {'.': true, ',': true, ':': true, 'a': true, 'D': true, '=': true, ' ': true}


static func stamp(area: Dictionary, type_code: String, interactive: bool = false) -> Dictionary:
	var def := Spec.dungeon_def(type_code)
	if def.is_empty():
		return {"fit": "UNKNOWN_TYPE", "type": type_code}
	var rows: Array = area.get("rows", [])
	if rows.is_empty():
		return {"fit": "EMPTY_AREA", "type": type_code}
	var w: int = str(rows[0]).length()
	var h: int = rows.size()
	var place := _choose_origin(area, w, h)
	if str(place.get("fit", "")) == "DOES NOT FIT":
		return place
	var ox: int = int(place["origin"][0])
	var oy: int = int(place["origin"][1])
	_carve_reservation(rows, ox, oy)
	var entities: Array = area.get("entities", [])
	var labels: Array = []
	labels.append({"kind": "debug_label", "id": "lbl_dungeon", "pos": [ox + 1, oy],
		"text": "DUNGEON:%s" % def["dungeon_id"], "debug": true})
	var room_origins: Array = Spec.room_origins()
	var room_abs: Array = []
	for i in range(room_origins.size()):
		var ro: Vector2i = room_origins[i]
		var rx := ox + ro.x
		var ry := oy + ro.y
		var room: Dictionary = def["rooms"][i]
		room_abs.append({"index": i + 1, "room_id": room["room_id"], "rect": [rx, ry, Spec.ROOM_W, Spec.ROOM_H]})
		_carve_room(rows, rx, ry)
		labels.append({"kind": "debug_label", "id": "lbl_room_%d" % (i + 1), "pos": [rx + 1, ry + 1],
			"text": "ROOM:%s" % room["room_id"], "debug": true})
		for lab in room.get("labels", []):
			var lx := rx + 2 + (labels.size() % 5)
			var ly := ry + 2 + ((labels.size() / 5) % 8)
			labels.append({"kind": "debug_label", "id": "lbl_%s_%d" % [room["room_id"], labels.size()],
				"pos": [lx, ly], "text": str(lab), "debug": true})
			_marker_entity(entities, lab, lx, ly, room["room_id"])
		if i == 4:
			labels.append({"kind": "debug_label", "id": "lbl_wizard", "pos": [rx + Spec.ROOM_W / 2, ry + Spec.ROOM_H / 2],
				"text": "WIZARD:%s" % def["wizard_id"], "debug": true})
			entities.append({"kind": "npc", "id": "wizard_%s" % type_code, "name": str(def["name"]),
				"sprite": "hedge_mage", "pos": [rx + Spec.ROOM_W / 2, ry + Spec.ROOM_H / 2], "facing": "down",
				"lines": ["Fixture wizard marker for %s. Not the final plot." % def["wizard_id"]],
				"debug_label": "WIZARD:%s" % def["wizard_id"]})
	_carve_connectors(rows, ox, oy, room_origins)
	var approach := [ox + Spec.ROOM_W / 2, mini(h - 2, oy + Spec.RESERVATION_H + 1)]
	_carve_approach(rows, ox, oy, approach, w, h)
	# Keep arrival outside the reservation so the player walks in from the exterior.
	area["player_start"] = approach.duplicate()
	for lab in labels:
		entities.append(lab)
	area["rows"] = rows
	area["entities"] = entities
	var reach := _validate_reachability(area, ox, oy, approach)
	var result := {
		"fit": "OK",
		"type": type_code,
		"dungeon_id": def["dungeon_id"],
		"wizard_id": def["wizard_id"],
		"origin": [ox, oy],
		"size": [Spec.RESERVATION_W, Spec.RESERVATION_H],
		"rooms": room_abs,
		"approach": approach,
		"interactive": interactive,
		"exits_clear": bool(reach["exits_clear"]),
		"rooms_reachable": bool(reach["rooms_reachable"]),
		"settlement_reachable": bool(reach["settlement_reachable"]),
		"path_in_len": int(reach["path_in_len"]),
		"path_out_len": int(reach["path_out_len"]),
		"flow": def["flow"],
		"states": def["states"],
	}
	if interactive:
		result["kit_room"] = _build_specimen_kit(area, ox, oy, def)
	return result


static func _choose_origin(area: Dictionary, w: int, h: int) -> Dictionary:
	var inset := 2
	if not Spec.reservation_fits(w, h, inset):
		return {"fit": "DOES NOT FIT", "reason": "node %dx%d cannot hold %dx%d reservation" % [w, h, Spec.RESERVATION_W, Spec.RESERVATION_H],
			"origin": [], "exits_clear": false}
	# Only hard-forbid strategic exit tiles. Player arrival is relocated south
	# of the reservation after carving so a centred spawn cannot block fit.
	var forbidden := {}
	for e in area.get("entities", []):
		if str(e.get("kind", "")) != "exit":
			continue
		var p: Array = e.get("pos", [])
		if p.size() >= 2:
			_mark_forbidden(forbidden, int(p[0]), int(p[1]), 1)
	var candidates: Array = []
	var max_ox := w - inset - Spec.RESERVATION_W
	var max_oy := h - inset - Spec.RESERVATION_H - 1  # leave approach strip
	for oy in range(inset, maxi(inset, max_oy) + 1):
		for ox in range(inset, maxi(inset, max_ox) + 1):
			if _rect_hits_forbidden(forbidden, ox, oy, Spec.RESERVATION_W, Spec.RESERVATION_H):
				continue
			# Prefer upper placements so southern exits/roads stay freer.
			var score := oy * 10 + ox
			candidates.append({"ox": ox, "oy": oy, "score": score})
	if candidates.is_empty():
		return {"fit": "DOES NOT FIT", "reason": "reservation overlaps exits/arrival", "origin": [], "exits_clear": false}
	candidates.sort_custom(func(a, b): return int(a["score"]) < int(b["score"]))
	var best: Dictionary = candidates[0]
	return {"fit": "OK", "origin": [int(best["ox"]), int(best["oy"])], "exits_clear": true}


static func _mark_forbidden(f: Dictionary, x: int, y: int, r: int) -> void:
	for dx in range(-r, r + 1):
		for dy in range(-r, r + 1):
			f["%d,%d" % [x + dx, y + dy]] = true


static func _rect_hits_forbidden(f: Dictionary, ox: int, oy: int, ww: int, hh: int) -> bool:
	for y in range(oy, oy + hh):
		for x in range(ox, ox + ww):
			if f.has("%d,%d" % [x, y]):
				return true
	return false


static func _put_tile(rows: Array, x: int, y: int, ch: String) -> void:
	if y < 0 or y >= rows.size():
		return
	var line: String = rows[y]
	if x < 0 or x >= line.length():
		return
	rows[y] = line.substr(0, x) + ch + line.substr(x + 1)


static func _carve_reservation(rows: Array, ox: int, oy: int) -> void:
	for y in range(oy, oy + Spec.RESERVATION_H):
		for x in range(ox, ox + Spec.RESERVATION_W):
			var edge := x == ox or y == oy or x == ox + Spec.RESERVATION_W - 1 or y == oy + Spec.RESERVATION_H - 1
			_put_tile(rows, x, y, "#" if edge else ",")


static func _carve_room(rows: Array, rx: int, ry: int) -> void:
	for y in range(ry, ry + Spec.ROOM_H):
		for x in range(rx, rx + Spec.ROOM_W):
			var edge := x == rx or y == ry or x == rx + Spec.ROOM_W - 1 or y == ry + Spec.ROOM_H - 1
			_put_tile(rows, x, y, "#" if edge else ".")


static func _carve_connectors(rows: Array, ox: int, oy: int, origins: Array) -> void:
	# Horizontal links R1-R2-R3 and R5-R4; vertical R2-R4.
	var centres: Array = []
	for o in origins:
		centres.append(Vector2i(ox + o.x + Spec.ROOM_W / 2, oy + o.y + Spec.ROOM_H / 2))
	var pairs := [[0, 1], [1, 2], [4, 3], [1, 3]]
	for p in pairs:
		var a: Vector2i = centres[p[0]]
		var b: Vector2i = centres[p[1]]
		_carve_line(rows, a, b)
		# Door gaps in room walls along the line.
		_open_door_on_segment(rows, a, b)


static func _carve_line(rows: Array, a: Vector2i, b: Vector2i) -> void:
	var x := a.x
	var y := a.y
	_put_tile(rows, x, y, ":")
	while x != b.x or y != b.y:
		if x != b.x:
			x += 1 if b.x > x else -1
		elif y != b.y:
			y += 1 if b.y > y else -1
		_put_tile(rows, x, y, ":")


static func _open_door_on_segment(rows: Array, a: Vector2i, b: Vector2i) -> void:
	# Ensure wall tiles on the path become doorways.
	var x := a.x
	var y := a.y
	while true:
		if y >= 0 and y < rows.size():
			var line: String = rows[y]
			if x >= 0 and x < line.length() and line[x] == "#":
				_put_tile(rows, x, y, ":")
		if x == b.x and y == b.y:
			break
		if x != b.x:
			x += 1 if b.x > x else -1
		elif y != b.y:
			y += 1 if b.y > y else -1


static func _carve_approach(rows: Array, ox: int, oy: int, approach: Array, w: int, h: int) -> void:
	var door_x := ox + Spec.ROOM_W / 2
	var door_y := oy + Spec.RESERVATION_H - 1
	_put_tile(rows, door_x, door_y, ":")
	var ax := int(approach[0])
	var ay := int(approach[1])
	_carve_line(rows, Vector2i(door_x, door_y), Vector2i(ax, ay))
	# Extend south toward typical player_start / bottom of map if space.
	var ty := mini(h - 2, ay + 3)
	_carve_line(rows, Vector2i(ax, ay), Vector2i(ax, ty))


static func _marker_entity(entities: Array, lab: String, x: int, y: int, room_id: String) -> void:
	var kind := "logs"
	var marker := "box"
	var text := lab
	if lab.begins_with("ITEM:"):
		kind = "pickup"
		marker = "ring"
		text = lab
	elif lab.begins_with("GATE:"):
		kind = "door"
		marker = "door_dungeon"
	elif lab.begins_with("MECH:") or lab.begins_with("RECEPTOR:"):
		marker = "staff"
	elif lab.begins_with("SIGN:") or lab.begins_with("STATE:"):
		kind = "sign"
		marker = "book_red"
	entities.append({"kind": kind, "id": "emb_%s_%d_%d" % [room_id, x, y], "pos": [x, y],
		"marker": marker, "text": text, "debug_label": lab, "fixture_marker": true})


static func _walkable(rows: Array, x: int, y: int) -> bool:
	if y < 0 or y >= rows.size():
		return false
	var line: String = rows[y]
	if x < 0 or x >= line.length():
		return false
	return WALK.has(line[x])


static func _bfs(rows: Array, start: Vector2i, goal: Vector2i) -> int:
	if start == goal:
		return 0
	if not _walkable(rows, start.x, start.y) or not _walkable(rows, goal.x, goal.y):
		return -1
	var q: Array = [start]
	var dist := {"%d,%d" % [start.x, start.y]: 0}
	var qi := 0
	while qi < q.size():
		var cur: Vector2i = q[qi]
		qi += 1
		var d: int = dist["%d,%d" % [cur.x, cur.y]]
		for dir in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
			var n: Vector2i = cur + dir
			var key := "%d,%d" % [n.x, n.y]
			if dist.has(key) or not _walkable(rows, n.x, n.y):
				continue
			if n == goal:
				return d + 1
			dist[key] = d + 1
			q.append(n)
	return -1


static func _validate_reachability(area: Dictionary, ox: int, oy: int, approach: Array) -> Dictionary:
	var rows: Array = area["rows"]
	var start: Array = area.get("player_start", approach)
	var sp := Vector2i(int(start[0]), int(start[1]))
	if not _walkable(rows, sp.x, sp.y):
		# Nudge to nearest walkable.
		sp = _nearest_walkable(rows, sp)
	var ap := Vector2i(int(approach[0]), int(approach[1]))
	var path_in := _bfs(rows, sp, ap)
	var rooms_ok := true
	var origins := Spec.room_origins()
	for o in origins:
		var centre := Vector2i(ox + o.x + Spec.ROOM_W / 2, oy + o.y + Spec.ROOM_H / 2)
		if _bfs(rows, ap, centre) < 0:
			rooms_ok = false
			break
	var path_out := _bfs(rows, Vector2i(ox + Spec.ROOM_W / 2, oy + Spec.ROOM_H / 2), sp)
	var exits_ok := true
	for e in area.get("entities", []):
		if str(e.get("kind", "")) != "exit":
			continue
		var ep := Vector2i(int(e["pos"][0]), int(e["pos"][1]))
		# Exit tiles themselves may be border; check arrival neighbour.
		var near := _nearest_walkable(rows, ep)
		if _bfs(rows, sp, near) < 0:
			exits_ok = false
	var plaza_ok := true
	var layout: Dictionary = area.get("layout", {})
	if layout.has("plaza"):
		var pl: Array = layout["plaza"]
		if pl.size() >= 4:
			var pc := Vector2i(int(pl[0]) + int(pl[2]) / 2, int(pl[1]) + int(pl[3]) / 2)
			pc = _nearest_walkable(rows, pc)
			plaza_ok = _bfs(rows, sp, pc) >= 0
	return {
		"exits_clear": exits_ok,
		"rooms_reachable": rooms_ok and path_in >= 0,
		"settlement_reachable": plaza_ok,
		"path_in_len": path_in,
		"path_out_len": path_out,
	}


static func _nearest_walkable(rows: Array, p: Vector2i) -> Vector2i:
	if _walkable(rows, p.x, p.y):
		return p
	for r in range(1, 8):
		for dx in range(-r, r + 1):
			for dy in range(-r, r + 1):
				var n := Vector2i(p.x + dx, p.y + dy)
				if _walkable(rows, n.x, n.y):
					return n
	return p


## Build a PuzzleKit room covering the full node map with GW-style mechanisms
## in the five envelopes. Reuses generic kit entity kinds (not a new engine).
static func _build_specimen_kit(area: Dictionary, ox: int, oy: int, def: Dictionary) -> Dictionary:
	var rows: Array = []
	for line in area["rows"]:
		rows.append(str(line))
	var start: Array = area.get("player_start", [ox + Spec.ROOM_W / 2, oy + Spec.RESERVATION_H])
	var ents: Array = []
	var o := Spec.room_origins()
	# Room 1 — sequence levers open root gate into room 2 corridor.
	var r1 := Vector2i(ox + o[0].x, oy + o[0].y)
	ents.append({"kind": "plaque", "id": "gw_seasons_carving", "pos": [r1.x + 2, r1.y + 2],
		"text": "SIGN:gw.seasons_carving — a tree passes through four seasons and returns to life."})
	ents.append({"kind": "lever", "id": "gw_root_barrier", "pos": [r1.x + 4, r1.y + 5], "flag": "gw_spring",
		"on_text": "MECH:gw.root_barrier — sap rises."})
	ents.append({"kind": "lever", "id": "gw_root_barrier_b", "pos": [r1.x + 6, r1.y + 5], "flag": "gw_summer",
		"on_text": "Leaves thicken."})
	ents.append({"kind": "lever", "id": "gw_root_barrier_c", "pos": [r1.x + 8, r1.y + 5], "flag": "gw_autumn",
		"on_text": "Fruit falls."})
	ents.append({"kind": "lever", "id": "gw_root_barrier_d", "pos": [r1.x + 10, r1.y + 5], "flag": "gw_winter",
		"on_text": "Quiet returns — and life with it."})
	ents.append({"kind": "gate", "id": "gw_root_gate", "pos": [r1.x + Spec.ROOM_W - 1, r1.y + Spec.ROOM_H / 2],
		"open_when": {"all": ["gw_spring", "gw_summer", "gw_autumn", "gw_winter"]}, "look": "gate"})
	# Room 2 — sun seed item.
	var r2 := Vector2i(ox + o[1].x, oy + o[1].y)
	ents.append({"kind": "plaque", "id": "gw_seed_clue", "pos": [r2.x + 2, r2.y + 2],
		"text": "What sleeps in winter is not dead."})
	ents.append({"kind": "item", "id": "sun_seed_item", "item": "item.gw.sun_seed", "pos": [r2.x + 7, r2.y + 6],
		"text": "ITEM:item.gw.sun_seed"})
	# Room 3 — weight/plate restores water (drop heavy stone on plate).
	var r3 := Vector2i(ox + o[2].x, oy + o[2].y)
	ents.append({"kind": "item", "id": "channel_weight", "item": "item.gw.channel_stone", "pos": [r3.x + 3, r3.y + 4],
		"text": "MECH:gw.channel_weight"})
	ents.append({"kind": "plate", "id": "channel_plate", "pos": [r3.x + 7, r3.y + 6], "flag": "gw_water_restored",
		"accepts": ["item", "player"], "item_tags": ["heavy"], "text": "MECH:gw.channel_plate"})
	ents.append({"kind": "lever", "id": "water_switch", "pos": [r3.x + 10, r3.y + 4], "flag": "gw_water_switch",
		"on_text": "MECH:gw.water_switch — channels open. STATE:gw.water_restored when the plate holds."})
	# Room 4 — install seed at growth point; living gate needs water + seed.
	var r4 := Vector2i(ox + o[3].x, oy + o[3].y)
	ents.append({"kind": "receptacle", "id": "growth_point", "pos": [r4.x + 7, r4.y + 5], "flag": "gw_sun_seed_installed",
		"accepts_items": ["item.gw.sun_seed"], "accepts_tags": ["sun_seed"], "removable": true,
		"text": "RECEPTOR:gw.growth_point"})
	ents.append({"kind": "gate", "id": "living_gate", "pos": [r4.x, r4.y + Spec.ROOM_H / 2],
		"open_when": {"all": ["gw_water_restored", "gw_sun_seed_installed"]}, "look": "gate"})
	# Room 5 — wizard + goal.
	var r5 := Vector2i(ox + o[4].x, oy + o[4].y)
	ents.append({"kind": "npc", "id": "wizard_gw", "pos": [r5.x + Spec.ROOM_W / 2, r5.y + Spec.ROOM_H / 2],
		"name": "Treefolk Presence", "lines": ["WIZARD:wizard.gw.treefolk — the Elder Court acknowledges you."]})
	ents.append({"kind": "goal", "id": "goal", "pos": [r5.x + Spec.ROOM_W / 2, r5.y + Spec.ROOM_H / 2 + 2],
		"text": "Through the Elder Court. The embedded specimen holds."})
	return {
		"id": "embedded_gw_specimen",
		"num": 0,
		"title": "Embedded Rootbound Sanctuary (spatial specimen)",
		"mechanics": "sequence, item, plate/weight, receptacle, gate, npc — PuzzleKit generic kinds",
		"rows": rows,
		"start": [int(start[0]), int(start[1])],
		"items": [],
		"spells": [],
		"entities": ents,
		"hint": "Walk from the exterior into room 1. Season levers → seed → water plate → install seed → living gate → wizard.",
		"embedded": true,
		"dungeon_id": def["dungeon_id"],
	}
