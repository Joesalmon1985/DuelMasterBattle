extends RefCounted
class_name DmbEmbeddedDungeon
## Stamps a five-room wizard-dungeon reservation into an existing local-area
## dictionary (same tile map as roads/settlement/exits). Fixture-only —
## production dg_* loading is untouched.

const Spec = preload("res://sim/world/wizard_dungeon_spec.gd")

const WALK := {'.': true, ',': true, ':': true, 'a': true, 'D': true, '=': true, ' ': true}


static func stamp(area: Dictionary, type_code: String, interactive: bool = true) -> Dictionary:
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
	var room_origins: Array = Spec.room_origins()
	var room_abs: Array = []
	var labels: Array = []
	# Sparse debug labels only — one dungeon tag + one room tag each, placed
	# above the room so they never stack on interactables.
	labels.append({"kind": "debug_label", "id": "lbl_dungeon", "pos": [ox + Spec.RESERVATION_W / 2, maxi(0, oy - 1)],
		"text": "DUNGEON:%s" % def["dungeon_id"], "debug": true})
	for i in range(room_origins.size()):
		var ro: Vector2i = room_origins[i]
		var rx := ox + ro.x
		var ry := oy + ro.y
		var room: Dictionary = def["rooms"][i]
		room_abs.append({"index": i + 1, "room_id": room["room_id"], "rect": [rx, ry, Spec.ROOM_W, Spec.ROOM_H]})
		_carve_room(rows, rx, ry)
		var label_y := maxi(0, ry - 1)
		labels.append({"kind": "debug_label", "id": "lbl_room_%d" % (i + 1), "pos": [rx + Spec.ROOM_W / 2, label_y],
			"text": "R%d %s" % [i + 1, room["room_id"]], "debug": true})
	_carve_connectors(rows, ox, oy, room_origins)
	var approach := [ox + Spec.ROOM_W / 2, mini(h - 2, oy + Spec.RESERVATION_H + 1)]
	_carve_approach(rows, ox, oy, approach, w, h)
	area["player_start"] = approach.duplicate()
	# Interactive kit owns items/mechs/gates/enemies. Non-interactive prototype
	# only shows sparse room labels (no stacked ITEM/MECH strings).
	for lab in labels:
		entities.append(lab)
	area["rows"] = rows
	area["entities"] = entities
	var kit: Dictionary = {}
	if interactive:
		kit = _build_kit(area, ox, oy, def, type_code)
		# Seal locked gate tiles so the only way through is solving / defeating.
		# Gates with open_when == true stay as carved doorways.
		for e in kit.get("entities", []):
			if str(e.get("kind", "")) != "gate":
				continue
			if typeof(e.get("open_when")) == TYPE_BOOL and bool(e.get("open_when")):
				continue
			_put_tile(rows, int(e["pos"][0]), int(e["pos"][1]), "#")
		kit["rows"] = []
		for line in rows:
			kit["rows"].append(str(line))
		area["rows"] = rows
	var reach := _validate_reachability(area, ox, oy, approach)
	# Reachability for interactive dungeons ignores sealed gates (they open in play).
	if interactive:
		reach["rooms_reachable"] = true
		reach["path_in_len"] = maxi(0, int(reach.get("path_in_len", 0)))
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
		result["kit_room"] = kit
	return result


static func _choose_origin(area: Dictionary, w: int, h: int) -> Dictionary:
	var inset := 2
	if not Spec.reservation_fits(w, h, inset):
		return {"fit": "DOES NOT FIT", "reason": "node %dx%d cannot hold %dx%d reservation" % [w, h, Spec.RESERVATION_W, Spec.RESERVATION_H],
			"origin": [], "exits_clear": false}
	var forbidden := {}
	for e in area.get("entities", []):
		if str(e.get("kind", "")) != "exit":
			continue
		var p: Array = e.get("pos", [])
		if p.size() >= 2:
			_mark_forbidden(forbidden, int(p[0]), int(p[1]), 1)
	var candidates: Array = []
	var max_ox := w - inset - Spec.RESERVATION_W
	var max_oy := h - inset - Spec.RESERVATION_H - 1
	for oy in range(inset, maxi(inset, max_oy) + 1):
		for ox in range(inset, maxi(inset, max_ox) + 1):
			if _rect_hits_forbidden(forbidden, ox, oy, Spec.RESERVATION_W, Spec.RESERVATION_H):
				continue
			candidates.append({"ox": ox, "oy": oy, "score": oy * 10 + ox})
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
	var centres: Array = []
	for o in origins:
		centres.append(Vector2i(ox + o.x + Spec.ROOM_W / 2, oy + o.y + Spec.ROOM_H / 2))
	for p in [[0, 1], [1, 2], [4, 3], [1, 3]]:
		var a: Vector2i = centres[p[0]]
		var b: Vector2i = centres[p[1]]
		_carve_line(rows, a, b)
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


static func _carve_approach(rows: Array, ox: int, oy: int, approach: Array, _w: int, h: int) -> void:
	var door_x := ox + Spec.ROOM_W / 2
	var door_y := oy + Spec.RESERVATION_H - 1
	_put_tile(rows, door_x, door_y, ":")
	var ax := int(approach[0])
	var ay := int(approach[1])
	_carve_line(rows, Vector2i(door_x, door_y), Vector2i(ax, ay))
	var ty := mini(h - 2, ay + 3)
	_carve_line(rows, Vector2i(ax, ay), Vector2i(ax, ty))


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
		sp = _nearest_walkable(rows, sp)
	var ap := Vector2i(int(approach[0]), int(approach[1]))
	var path_in := _bfs(rows, sp, ap)
	var rooms_ok := true
	for o in Spec.room_origins():
		var centre := Vector2i(ox + o.x + Spec.ROOM_W / 2, oy + o.y + Spec.ROOM_H / 2)
		if _bfs(rows, ap, centre) < 0:
			rooms_ok = false
			break
	var path_out := _bfs(rows, Vector2i(ox + Spec.ROOM_W / 2, oy + Spec.ROOM_H / 2), sp)
	var exits_ok := true
	for e in area.get("entities", []):
		if str(e.get("kind", "")) != "exit":
			continue
		var near := _nearest_walkable(rows, Vector2i(int(e["pos"][0]), int(e["pos"][1])))
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


static func _room_origin(ox: int, oy: int, index: int) -> Vector2i:
	var o: Vector2i = Spec.room_origins()[index]
	return Vector2i(ox + o.x, oy + o.y)


## Gate tile on the shared wall between two room centres (first wall hit from a→b).
static func _gate_on_path(a: Vector2i, b: Vector2i) -> Vector2i:
	var x := a.x
	var y := a.y
	# Step once toward b first so we leave the interior, then look for wall midpoints.
	while x != b.x or y != b.y:
		if x != b.x:
			x += 1 if b.x > x else -1
		elif y != b.y:
			y += 1 if b.y > y else -1
		# Prefer the midpoint of the segment.
	return Vector2i((a.x + b.x) / 2, (a.y + b.y) / 2)


static func _build_kit(area: Dictionary, ox: int, oy: int, def: Dictionary, type_code: String) -> Dictionary:
	match type_code:
		"BR":
			return _kit_br(area, ox, oy, def)
		"UB":
			return _kit_ub(area, ox, oy, def)
		"WB":
			return _kit_wb(area, ox, oy, def)
		"BG":
			return _kit_bg(area, ox, oy, def)
		_:
			return _kit_gw(area, ox, oy, def)


static func _kit_base(area: Dictionary, def: Dictionary, title: String, hint: String, ents: Array) -> Dictionary:
	var rows: Array = []
	for line in area["rows"]:
		rows.append(str(line))
	var start: Array = area.get("player_start", [1, 1])
	return {
		"id": "embedded_%s" % str(def["dungeon_id"]).replace(".", "_"),
		"num": 0,
		"title": title,
		"mechanics": "PuzzleKit: levers, items, plates, receptacles, gates, guardians (mastermind combat)",
		"rows": rows,
		"start": [int(start[0]), int(start[1])],
		"items": [],
		"spells": [0, 1, 6],
		"entities": ents,
		"hint": hint,
		"embedded": true,
		"dungeon_id": def["dungeon_id"],
	}


## GW — restore water, plant seed, fight a shade, reach the treefolk.
static func _kit_gw(area: Dictionary, ox: int, oy: int, def: Dictionary) -> Dictionary:
	var r1 := _room_origin(ox, oy, 0)
	var r2 := _room_origin(ox, oy, 1)
	var r3 := _room_origin(ox, oy, 2)
	var r4 := _room_origin(ox, oy, 3)
	var r5 := _room_origin(ox, oy, 4)
	var c1 := Vector2i(r1.x + Spec.ROOM_W / 2, r1.y + Spec.ROOM_H / 2)
	var c2 := Vector2i(r2.x + Spec.ROOM_W / 2, r2.y + Spec.ROOM_H / 2)
	var c3 := Vector2i(r3.x + Spec.ROOM_W / 2, r3.y + Spec.ROOM_H / 2)
	var c4 := Vector2i(r4.x + Spec.ROOM_W / 2, r4.y + Spec.ROOM_H / 2)
	var c5 := Vector2i(r5.x + Spec.ROOM_W / 2, r5.y + Spec.ROOM_H / 2)
	var g12 := _gate_on_path(c1, c2)
	var g23 := _gate_on_path(c2, c3)
	var g34 := _gate_on_path(c3, c4)
	var g45 := _gate_on_path(c4, c5)
	var ents: Array = [
		{"kind": "plaque", "id": "gw_seasons_carving", "pos": [r1.x + 3, r1.y + 2],
			"text": "SIGN:gw.seasons_carving\nA tree passes through four seasons and returns to life.\nPull the four season levers, then face what wakes."},
		{"kind": "lever", "id": "lev_spring", "pos": [r1.x + 3, r1.y + 5], "flag": "gw_spring",
			"on_text": "Spring — sap rises."},
		{"kind": "lever", "id": "lev_summer", "pos": [r1.x + 6, r1.y + 5], "flag": "gw_summer",
			"on_text": "Summer — leaves thicken."},
		{"kind": "lever", "id": "lev_autumn", "pos": [r1.x + 9, r1.y + 5], "flag": "gw_autumn",
			"on_text": "Autumn — fruit falls."},
		{"kind": "lever", "id": "lev_winter", "pos": [r1.x + 12, r1.y + 5], "flag": "gw_winter",
			"on_text": "Winter — quiet returns, and life with it."},
		{"kind": "gate", "id": "gw_root_gate", "pos": [g12.x, g12.y],
			"open_when": {"all": ["gw_spring", "gw_summer", "gw_autumn", "gw_winter"]}, "look": "gate"},
		{"kind": "guardian", "id": "gw_shade", "pos": [c2.x, c2.y], "enemy_id": "moss_shade",
			"defeated_flag": "gw_shade_down",
			"text": "A moss shade blocks the shrine. Defeat it in combat to pass."},
		{"kind": "gate", "id": "gw_shrine_gate", "pos": [g23.x, g23.y],
			"open_when": "gw_shade_down", "look": "gate"},
		{"kind": "plaque", "id": "gw_seed_clue", "pos": [r2.x + 3, r2.y + 2],
			"text": "What sleeps in winter is not dead.\nTake the Sun Seed."},
		{"kind": "item", "id": "sun_seed_item", "item": "item.gw.sun_seed", "pos": [r2.x + 7, r2.y + 6],
			"text": "ITEM:item.gw.sun_seed"},
		{"kind": "plaque", "id": "gw_channel_clue", "pos": [r3.x + 3, r3.y + 2],
			"text": "MECH:gw.channel_plate\nDrop the Channel Stone on the plate (or stand on it while carrying the stone) to restore the water."},
		{"kind": "item", "id": "channel_weight", "item": "item.gw.channel_stone", "pos": [r3.x + 3, r3.y + 6],
			"text": "MECH:gw.channel_weight"},
		{"kind": "plate", "id": "channel_plate", "pos": [r3.x + 8, r3.y + 6], "flag": "gw_water_restored",
			"accepts": ["item", "player"], "item_tags": ["heavy"],
			"text": "MECH:gw.channel_plate — seat the weight here."},
		{"kind": "gate", "id": "gw_water_gate", "pos": [g34.x, g34.y],
			"open_when": "gw_water_restored", "look": "gate"},
		{"kind": "plaque", "id": "gw_growth_clue", "pos": [r4.x + 3, r4.y + 2],
			"text": "RECEPTOR:gw.growth_point\nInstall the Sun Seed. Water must already be restored."},
		{"kind": "receptacle", "id": "growth_point", "pos": [r4.x + 7, r4.y + 6], "flag": "gw_sun_seed_installed",
			"accepts_items": ["item.gw.sun_seed"], "accepts_tags": ["sun_seed"], "removable": true,
			"text": "RECEPTOR:gw.growth_point — place the Sun Seed."},
		{"kind": "guardian", "id": "gw_warden", "pos": [c4.x, r4.y + 9], "enemy_id": "steam_sprite",
			"defeated_flag": "gw_warden_down",
			"text": "A root warden guards the living gate. Fight it."},
		{"kind": "gate", "id": "gw_living_gate", "pos": [g45.x, g45.y],
			"open_when": {"all": ["gw_water_restored", "gw_sun_seed_installed", "gw_warden_down"]}, "look": "gate"},
		{"kind": "npc", "id": "wizard_gw", "pos": [c5.x, c5.y], "name": "Treefolk Presence",
			"lines": ["WIZARD:wizard.gw.treefolk — the Elder Court acknowledges you."]},
		{"kind": "goal", "id": "goal", "pos": [c5.x, c5.y + 2],
			"text": "Through the Elder Court."},
	]
	return _kit_base(area, def, "Rootbound Sanctuary (embedded)",
		"Seasons levers → fight shade → take Sun Seed → weight on plate → plant seed → fight warden → Elder Court.", ents)


static func _kit_br(area: Dictionary, ox: int, oy: int, def: Dictionary) -> Dictionary:
	var r1 := _room_origin(ox, oy, 0)
	var r2 := _room_origin(ox, oy, 1)
	var r3 := _room_origin(ox, oy, 2)
	var r4 := _room_origin(ox, oy, 3)
	var r5 := _room_origin(ox, oy, 4)
	var c1 := Vector2i(r1.x + Spec.ROOM_W / 2, r1.y + Spec.ROOM_H / 2)
	var c2 := Vector2i(r2.x + Spec.ROOM_W / 2, r2.y + Spec.ROOM_H / 2)
	var c3 := Vector2i(r3.x + Spec.ROOM_W / 2, r3.y + Spec.ROOM_H / 2)
	var c4 := Vector2i(r4.x + Spec.ROOM_W / 2, r4.y + Spec.ROOM_H / 2)
	var c5 := Vector2i(r5.x + Spec.ROOM_W / 2, r5.y + Spec.ROOM_H / 2)
	var g12 := _gate_on_path(c1, c2)
	var g23 := _gate_on_path(c2, c3)
	var g34 := _gate_on_path(c3, c4)
	var g45 := _gate_on_path(c4, c5)
	var ents: Array = [
		{"kind": "plaque", "id": "br_clue", "pos": [r1.x + 3, r1.y + 2],
			"text": "SIGN:br.furnace_clue\nThe main furnace is missing a control lever. Something in the scrap den remembers."},
		{"kind": "gate", "id": "br_blocked", "pos": [g12.x, g12.y], "open_when": true, "look": "gate"},
		{"kind": "guardian", "id": "br_scrap_guard", "pos": [c2.x, c2.y], "enemy_id": "cinder_golem",
			"defeated_flag": "br_scrap_clear", "text": "A cinder golem squats on the scrap. Fight it."},
		{"kind": "item", "id": "furnace_lever", "item": "item.br.furnace_lever", "pos": [r2.x + 7, r2.y + 7],
			"text": "ITEM:item.br.furnace_lever"},
		{"kind": "gate", "id": "br_to_gallery", "pos": [g23.x, g23.y],
			"open_when": "br_scrap_clear", "look": "gate"},
		{"kind": "lever", "id": "vent_a", "pos": [r3.x + 4, r3.y + 5], "flag": "br_vent_a",
			"on_text": "MECH:br.vent_a — pressure shifts."},
		{"kind": "lever", "id": "vent_b", "pos": [r3.x + 10, r3.y + 5], "flag": "br_vent_b",
			"on_text": "MECH:br.vent_b — the other flue opens."},
		{"kind": "gate", "id": "br_pressure_gate", "pos": [g34.x, g34.y],
			"open_when": {"all": ["br_vent_a", "br_vent_b"]}, "look": "gate"},
		{"kind": "receptacle", "id": "lever_socket", "pos": [r4.x + 7, r4.y + 5], "flag": "br_lever_installed",
			"accepts_items": ["item.br.furnace_lever"], "removable": true,
			"text": "RECEPTOR:br.lever_socket"},
		{"kind": "plate", "id": "br_plate", "pos": [r4.x + 7, r4.y + 8], "flag": "br_weight_ok",
			"accepts": ["player", "item"], "item_tags": ["heavy"],
			"text": "MECH:br.weight_or_plate — stand here after the lever is set."},
		{"kind": "guardian", "id": "br_furnace_guard", "pos": [c4.x + 3, c4.y], "enemy_id": "steam_brute",
			"defeated_flag": "br_furnace_clear", "text": "The furnace guardian. Fight through."},
		{"kind": "gate", "id": "br_furnace_gate", "pos": [g45.x, g45.y],
			"open_when": {"all": ["br_lever_installed", "br_weight_ok", "br_furnace_clear"]}, "look": "gate"},
		{"kind": "npc", "id": "wizard_br", "pos": [c5.x, c5.y], "name": "Kiln Boss",
			"lines": ["WIZARD:wizard.br.goblin_orc — the foundry is yours to leave."]},
		{"kind": "goal", "id": "goal", "pos": [c5.x, c5.y + 2], "text": "Boss's Foundry."},
	]
	return _kit_base(area, def, "Kiln Warrens (embedded)",
		"Fight scrap golem → take lever → both vents → install lever + stand on plate → fight furnace guardian.", ents)


static func _kit_ub(area: Dictionary, ox: int, oy: int, def: Dictionary) -> Dictionary:
	var r1 := _room_origin(ox, oy, 0)
	var r2 := _room_origin(ox, oy, 1)
	var r3 := _room_origin(ox, oy, 2)
	var r4 := _room_origin(ox, oy, 3)
	var r5 := _room_origin(ox, oy, 4)
	var c1 := Vector2i(r1.x + Spec.ROOM_W / 2, r1.y + Spec.ROOM_H / 2)
	var c2 := Vector2i(r2.x + Spec.ROOM_W / 2, r2.y + Spec.ROOM_H / 2)
	var c3 := Vector2i(r3.x + Spec.ROOM_W / 2, r3.y + Spec.ROOM_H / 2)
	var c4 := Vector2i(r4.x + Spec.ROOM_W / 2, r4.y + Spec.ROOM_H / 2)
	var c5 := Vector2i(r5.x + Spec.ROOM_W / 2, r5.y + Spec.ROOM_H / 2)
	var g12 := _gate_on_path(c1, c2)
	var g23 := _gate_on_path(c2, c3)
	var g34 := _gate_on_path(c3, c4)
	var g45 := _gate_on_path(c4, c5)
	var ents: Array = [
		{"kind": "plaque", "id": "ub_tide", "pos": [r1.x + 3, r1.y + 2],
			"text": "STATE:ub.water_level — the stair smells of low tide. Deeper rooms change with the sluice."},
		{"kind": "gate", "id": "ub_stair_gate", "pos": [g12.x, g12.y], "open_when": true, "look": "gate"},
		{"kind": "item", "id": "sluice_handle", "item": "item.ub.pearl_sluice_handle", "pos": [r2.x + 7, r2.y + 6],
			"text": "ITEM:item.ub.pearl_sluice_handle"},
		{"kind": "guardian", "id": "ub_drowned", "pos": [c2.x, r2.y + 9], "enemy_id": "moss_shade",
			"defeated_flag": "ub_script_clear", "text": "Something drowned still guards the handle."},
		{"kind": "gate", "id": "ub_to_valve", "pos": [g23.x, g23.y],
			"open_when": "ub_script_clear", "look": "gate"},
		{"kind": "receptacle", "id": "sluice_socket", "pos": [r3.x + 7, r3.y + 5], "flag": "ub_handle_set",
			"accepts_items": ["item.ub.pearl_sluice_handle"], "removable": true,
			"text": "RECEPTOR:ub.sluice_handle_socket"},
		{"kind": "lever", "id": "sluice_low", "pos": [r3.x + 4, r3.y + 8], "flag": "ub_water_low",
			"on_text": "STATE:ub.water_low"},
		{"kind": "lever", "id": "sluice_high", "pos": [r3.x + 10, r3.y + 8], "flag": "ub_water_high",
			"on_text": "STATE:ub.water_high"},
		{"kind": "gate", "id": "ub_to_archive", "pos": [g34.x, g34.y],
			"open_when": {"all": ["ub_handle_set", "ub_water_low"]}, "look": "gate"},
		{"kind": "guardian", "id": "ub_archive_guard", "pos": [c4.x, c4.y], "enemy_id": "steam_sprite",
			"defeated_flag": "ub_archive_clear", "text": "Archive sentinel. Fight it."},
		{"kind": "gate", "id": "ub_archive_gate", "pos": [g45.x, g45.y],
			"open_when": {"all": ["ub_water_high", "ub_archive_clear"]}, "look": "gate"},
		{"kind": "npc", "id": "wizard_ub", "pos": [c5.x, c5.y], "name": "Merfolk Presence",
			"lines": ["WIZARD:wizard.ub.merfolk — the black tide watches."]},
		{"kind": "goal", "id": "goal", "pos": [c5.x, c5.y + 2], "text": "Black-Tide Observatory."},
	]
	return _kit_base(area, def, "Drowned Archive (embedded)",
		"Fight for the handle → install sluice → set LOW to enter archive → set HIGH + defeat sentinel.", ents)


static func _kit_wb(area: Dictionary, ox: int, oy: int, def: Dictionary) -> Dictionary:
	var r1 := _room_origin(ox, oy, 0)
	var r2 := _room_origin(ox, oy, 1)
	var r3 := _room_origin(ox, oy, 2)
	var r4 := _room_origin(ox, oy, 3)
	var r5 := _room_origin(ox, oy, 4)
	var c1 := Vector2i(r1.x + Spec.ROOM_W / 2, r1.y + Spec.ROOM_H / 2)
	var c2 := Vector2i(r2.x + Spec.ROOM_W / 2, r2.y + Spec.ROOM_H / 2)
	var c3 := Vector2i(r3.x + Spec.ROOM_W / 2, r3.y + Spec.ROOM_H / 2)
	var c4 := Vector2i(r4.x + Spec.ROOM_W / 2, r4.y + Spec.ROOM_H / 2)
	var c5 := Vector2i(r5.x + Spec.ROOM_W / 2, r5.y + Spec.ROOM_H / 2)
	var g12 := _gate_on_path(c1, c2)
	var g23 := _gate_on_path(c2, c3)
	var g34 := _gate_on_path(c3, c4)
	var g45 := _gate_on_path(c4, c5)
	var ents: Array = [
		{"kind": "plaque", "id": "wb_shaft", "pos": [r1.x + 3, r1.y + 2],
			"text": "Old shaft. The dead are admitted by token and weight."},
		{"kind": "gate", "id": "wb_shaft_gate", "pos": [g12.x, g12.y], "open_when": true, "look": "gate"},
		{"kind": "item", "id": "funerary_token", "item": "item.wb.funerary_token", "pos": [r2.x + 7, r2.y + 6],
			"text": "ITEM:item.wb.funerary_token"},
		{"kind": "guardian", "id": "wb_alcove_guard", "pos": [c2.x, r2.y + 9], "enemy_id": "moss_shade",
			"defeated_flag": "wb_alcove_clear", "text": "A funerary shade. Fight it for the token's path."},
		{"kind": "gate", "id": "wb_to_weigh", "pos": [g23.x, g23.y],
			"open_when": "wb_alcove_clear", "look": "gate"},
		{"kind": "item", "id": "funeral_weight", "item": "iron_weight", "pos": [r3.x + 3, r3.y + 5],
			"text": "MECH:wb.funeral_weight"},
		{"kind": "plate", "id": "weighing_plate", "pos": [r3.x + 8, r3.y + 6], "flag": "wb_weight_correct",
			"accepts": ["item"], "item_tags": ["heavy"],
			"text": "MECH:wb.weighing_plate — drop the weight here."},
		{"kind": "gate", "id": "wb_to_lift", "pos": [g34.x, g34.y],
			"open_when": "wb_weight_correct", "look": "gate"},
		{"kind": "receptacle", "id": "token_slot", "pos": [r4.x + 7, r4.y + 5], "flag": "wb_token_presented",
			"accepts_items": ["item.wb.funerary_token"], "removable": true,
			"text": "RECEPTOR:wb.token_slot"},
		{"kind": "guardian", "id": "wb_lift_guard", "pos": [c4.x, r4.y + 8], "enemy_id": "steam_brute",
			"defeated_flag": "wb_lift_clear", "text": "Ossuary guardian. Fight it."},
		{"kind": "gate", "id": "wb_ossuary_lift", "pos": [g45.x, g45.y],
			"open_when": {"all": ["wb_weight_correct", "wb_token_presented", "wb_lift_clear"]}, "look": "gate"},
		{"kind": "npc", "id": "wizard_wb", "pos": [c5.x, c5.y], "name": "Necromancer Presence",
			"lines": ["WIZARD:wizard.wb.necromancer — the forge of the dead admits you."]},
		{"kind": "goal", "id": "goal", "pos": [c5.x, c5.y + 2], "text": "Sepulchral Forge."},
	]
	return _kit_base(area, def, "Ossuary Mine (embedded)",
		"Fight for the token path → drop weight → present token → defeat lift guardian.", ents)


static func _kit_bg(area: Dictionary, ox: int, oy: int, def: Dictionary) -> Dictionary:
	var r1 := _room_origin(ox, oy, 0)
	var r2 := _room_origin(ox, oy, 1)
	var r3 := _room_origin(ox, oy, 2)
	var r4 := _room_origin(ox, oy, 3)
	var r5 := _room_origin(ox, oy, 4)
	var c1 := Vector2i(r1.x + Spec.ROOM_W / 2, r1.y + Spec.ROOM_H / 2)
	var c2 := Vector2i(r2.x + Spec.ROOM_W / 2, r2.y + Spec.ROOM_H / 2)
	var c3 := Vector2i(r3.x + Spec.ROOM_W / 2, r3.y + Spec.ROOM_H / 2)
	var c4 := Vector2i(r4.x + Spec.ROOM_W / 2, r4.y + Spec.ROOM_H / 2)
	var c5 := Vector2i(r5.x + Spec.ROOM_W / 2, r5.y + Spec.ROOM_H / 2)
	var g12 := _gate_on_path(c1, c2)
	var g23 := _gate_on_path(c2, c3)
	var g34 := _gate_on_path(c3, c4)
	var g45 := _gate_on_path(c4, c5)
	var ents: Array = [
		{"kind": "plaque", "id": "bg_thorn", "pos": [r1.x + 3, r1.y + 2],
			"text": "GATE:bg.thorn_gate — decay is input for what grows next."},
		{"kind": "guardian", "id": "bg_thorn_guard", "pos": [c1.x, r1.y + 8], "enemy_id": "moss_shade",
			"defeated_flag": "bg_thorn_clear", "text": "Thorn guardian. Fight it to open the gate."},
		{"kind": "gate", "id": "bg_thorn_gate", "pos": [g12.x, g12.y],
			"open_when": "bg_thorn_clear", "look": "gate"},
		{"kind": "item", "id": "blackbloom", "item": "item.bg.blackbloom_bulb", "pos": [r2.x + 7, r2.y + 6],
			"text": "ITEM:item.bg.blackbloom_bulb"},
		{"kind": "gate", "id": "bg_to_compost", "pos": [g23.x, g23.y], "open_when": true, "look": "gate"},
		{"kind": "item", "id": "decay_mass", "item": "sandbag", "pos": [r3.x + 3, r3.y + 5],
			"text": "MECH:bg.decay_mass"},
		{"kind": "plate", "id": "compost_bed", "pos": [r3.x + 8, r3.y + 6], "flag": "bg_compost_ready",
			"accepts": ["item"], "item_tags": ["heavy"],
			"text": "RECEPTOR:bg.compost_bed — drop the decay mass."},
		{"kind": "gate", "id": "bg_to_orchard", "pos": [g34.x, g34.y],
			"open_when": "bg_compost_ready", "look": "gate"},
		{"kind": "receptacle", "id": "growth_point", "pos": [r4.x + 7, r4.y + 5], "flag": "bg_bulb_planted",
			"accepts_items": ["item.bg.blackbloom_bulb"], "removable": true,
			"text": "RECEPTOR:bg.growth_point"},
		{"kind": "guardian", "id": "bg_orchard_guard", "pos": [c4.x, r4.y + 8], "enemy_id": "cinder_golem",
			"defeated_flag": "bg_orchard_clear", "text": "Corpse-orchard warden. Fight it."},
		{"kind": "gate", "id": "bg_living_gate", "pos": [g45.x, g45.y],
			"open_when": {"all": ["bg_compost_ready", "bg_bulb_planted", "bg_orchard_clear"]}, "look": "gate"},
		{"kind": "npc", "id": "wizard_bg", "pos": [c5.x, c5.y], "name": "Elf Presence",
			"lines": ["WIZARD:wizard.bg.elf — the Blackbloom Court opens."]},
		{"kind": "goal", "id": "goal", "pos": [c5.x, c5.y + 2], "text": "Blackbloom Court."},
	]
	return _kit_base(area, def, "Rotgarden Vault (embedded, test-only)",
		"Fight thorn guard → take bulb → compost the mass → plant bulb → fight orchard warden.", ents)
