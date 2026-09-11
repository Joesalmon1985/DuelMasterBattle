extends RefCounted
class_name DmbPuzzleProjection
## Sim-layer adapter (the §13 projection): a catalogue room from
## DmbPuzzleRooms plus its DmbPuzzleKit state becomes a normal
## Overworld-compatible area dict (`id`, `name`, `rows`, `entities`).
## Visual state (markers, tints) is derived from Kit.visual()/helpers — the
## sim owns the visual-state description; the production client only draws it.
## No puzzle-ID-specific logic lives here: everything is driven by generic
## entity kinds and kit state queries.

const Kit = preload("res://sim/world/puzzle_kit.gd")
const Items = preload("res://sim/world/items.gd")

## Overworld tile chars the kit never emits intent for: `f` is walkable floor
## deco in rooms but a solid fence in the production renderer, so remap it.
static func _map_row(line: String) -> String:
	var out := ""
	for i in range(line.length()):
		var ch := line[i]
		out += "." if ch == "f" else ch
	return out


static func _set_tile(rows: Array, pos: Array, ch: String) -> void:
	var x := int(pos[0])
	var y := int(pos[1])
	if y < 0 or y >= rows.size():
		return
	var line: String = rows[y]
	if x < 0 or x >= line.length():
		return
	rows[y] = line.substr(0, x) + ch + line.substr(x + 1)


## Full area dict for the production loader. `rid` is the room id (pz_NN).
static func area_for(room: Dictionary, st: Dictionary) -> Dictionary:
	var rid := str(room["id"])
	var flags: Dictionary = Kit.flags_now(room, st)
	var rows: Array = []
	for line in room["rows"]:
		rows.append(_map_row(str(line)))
	var entities: Array = []
	for e in room["entities"]:
		_project_static(room, st, e, flags, rows, entities, rid)
	_project_beams(room, st, flags, entities, rid)
	_project_state_actors(room, st, flags, entities, rid)
	return {"id": rid, "name": str(room["title"]), "rows": rows, "entities": entities}


static func _base(rid: String, e: Dictionary, kind: String, pos: Array) -> Dictionary:
	var d := {"kind": kind, "id": "puz_%s_%s" % [rid, str(e.get("id", "x"))],
		"pos": pos.duplicate(), "puzzle_room": rid, "puzzle_eid": str(e.get("id", ""))}
	for k in ["name", "text", "facing", "marker", "tint", "sprite", "enemy_id"]:
		if e.has(k):
			d[k] = e[k]
	return d


## Entities fixed to their definition position (or hidden by state).
static func _project_static(room: Dictionary, st: Dictionary, e: Dictionary, flags: Dictionary, rows: Array, entities: Array, rid: String) -> void:
	var k := str(e.get("kind", ""))
	if not e.has("pos"):
		return
	var pos: Array = (e["pos"] as Array).duplicate()
	match k:
		"gate":
			# Puzzle gates are always visible at their own tile: locked looks
			# shut, open looks passable. Same kind/position in both states so
			# the doorway visibly changes without moving. Zero-offset deco
			# keeps the graphic off the goal tile behind it.
			# Kit.blocks() owns collision; the gate needs no interaction.
			var look := str(e.get("look", "gate"))
			var open := Kit.gate_open(e, flags)
			if open:
				_set_tile(rows, pos, ":")
			if look == "wall":
				if not open:
					_set_tile(rows, pos, "#")
			elif look == "water":
				if not open:
					_set_tile(rows, pos, "~")
			else:
				var d := _base(rid, e, "deco", pos)
				d["marker"] = "puzzle_gate_open" if open else "puzzle_gate_locked"
				d.erase("puzzle_eid")
				entities.append(d)
		"plaque":
			entities.append(_base(rid, e, "sign", pos))
		"board":
			var d := _base(rid, e, "sign", pos)
			d["marker"] = "book_red"
			entities.append(d)
		"choice":
			var d := _base(rid, e, "sign", pos)
			d["marker"] = "book_black"
			entities.append(d)
		"lever":
			var d := _base(rid, e, "logs", pos)
			d["marker"] = "staff"
			entities.append(d)
		"button":
			var d := _base(rid, e, "logs", pos)
			d["marker"] = "stone_shard"
			entities.append(d)
		"rotator":
			var d := _base(rid, e, "logs", pos)
			d["marker"] = "ring"
			entities.append(d)
		"container":
			entities.append(_base(rid, e, "logs", pos))
		"receptacle":
			# Pedestal (or niche) always; a solved receptacle additionally shows
			# the installed object's own sprite raised above it, so each
			# offering sits visibly on top.
			var d := _base(rid, e, "logs", pos)
			d["marker"] = str(e.get("marker", "puzzle_alcove_empty"))
			entities.append(d)
			var inst := str(st["rec"].get(str(e.get("id", "")), ""))
			if inst != "":
				var o := _base(rid, e, "deco", pos)
				o.erase("puzzle_eid")
				o["marker"] = Items.sprite_of(inst)
				o["marker_off"] = [0, -10]
				entities.append(o)
		"emitter":
			var d := _base(rid, e, "logs", pos)
			d["marker"] = "mirror"
			entities.append(d)
		"receiver":
			var d := _base(rid, e, "logs", pos)
			d["marker"] = "diamond"
			entities.append(d)
		"magic_target":
			if Kit.cond(e.get("solid_when", true), flags):
				entities.append(_base(rid, e, "fire", pos))
			else:
				var d := _base(rid, e, "deco", pos)
				d["marker"] = "mirror"
				entities.append(d)
		"guardian":
			if Kit.present(room, st, e, flags):
				entities.append(_base(rid, e, "creature", pos))
		"pit":
			if Kit.cond(e.get("bridge_when", false), flags):
				_set_tile(rows, pos, "=")
			elif Kit.cond(e.get("revealed_when", true), flags) or bool(st["tripped"].get(str(e.get("id", "")), false)):
				var d := _base(rid, e, "deco", pos)
				d["marker"] = "rock"
				d["tint"] = Color(0.05, 0.05, 0.08)
				d.erase("puzzle_eid")
				entities.append(d)
		"crumble":
			var c: Dictionary = st["crumble"][str(e.get("id", ""))]
			var d := _base(rid, e, "deco", pos)
			d.erase("puzzle_eid")
			match str(c["state"]):
				"intact":
					d["marker"] = "box"
				"cracked":
					d["marker"] = "box"
					d["tint"] = Color(1.0, 0.45, 0.1)
				_:
					d["marker"] = "rock"
					d["tint"] = Color(0.08, 0.05, 0.05)
			entities.append(d)
		"plate":
			var d := _base(rid, e, "deco", pos)
			d["marker"] = "stone_shard"
			d.erase("puzzle_eid")
			if Kit.plate_active(room, st, e):
				d["tint"] = Color(0.35, 0.75, 1.0)
			entities.append(d)
		"marker":
			var d := _base(rid, e, "deco", pos)
			d["marker"] = "diamond"
			d["tint"] = Kit.visual(room, st, e)["color"]
			d.erase("puzzle_eid")
			entities.append(d)
		"goal":
			var d := _base(rid, e, "deco", pos)
			d["marker"] = "diamond"
			d["tint"] = Color(1.0, 0.85, 0.2)
			d.erase("puzzle_eid")
			entities.append(d)
		"teleporter":
			var d := _base(rid, e, "deco", pos)
			d["marker"] = "mirror"
			var t: Dictionary = st["tele"][str(e.get("id", ""))]
			var cols: Array = Kit.C_TELE
			d["tint"] = cols[int(t["i"]) % cols.size()]
			d.erase("puzzle_eid")
			entities.append(d)
		# sequence: data-only (expected tread order), no visual.
		# npc/critter/item: live positions live in state — see below.


## Beam path tiles as walk-through light decos.
static func _project_beams(room: Dictionary, st: Dictionary, flags: Dictionary, entities: Array, rid: String) -> void:
	for e in room["entities"]:
		if str(e.get("kind", "")) != "emitter" or not e.has("pos"):
			continue
		for p in Kit.beam_path(room, st, e, flags):
			var bp: Vector2i = p
			var d := {"kind": "deco", "id": "puz_%s_beam_%d_%d" % [rid, bp.x, bp.y],
				"pos": [bp.x, bp.y], "marker": "diamond",
				"tint": Color(1.0, 0.95, 0.35, 0.85)}
			entities.append(d)


## Actors whose position lives in state: hazards, teleporters handled above;
## npcs, critters and loose world items move or appear/disappear.
static func _project_state_actors(room: Dictionary, st: Dictionary, flags: Dictionary, entities: Array, rid: String) -> void:
	for e in room["entities"]:
		if str(e.get("kind", "")) == "hazard" and e.has("pos"):
			var d := _base(rid, e, "deco", e["pos"])
			d["pos"] = [Kit.hazard_pos(e, st).x, Kit.hazard_pos(e, st).y]
			d["marker"] = "fire_0"
			d.erase("puzzle_eid")
			if Kit.cond(e.get("jammed_when", false), flags):
				d["tint"] = Color(0.4, 0.4, 0.45)
			entities.append(d)
	for id in st["npcs"]:
		var e := Kit.entity(room, str(id))
		if e.is_empty():
			continue
		var d := _base(rid, e, "npc", (st["npcs"][id]["pos"] as Array).duplicate())
		if not d.has("sprite"):
			d["sprite"] = "villager_a"
		entities.append(d)
	for id in st["critters"]:
		var e := Kit.entity(room, str(id))
		if e.is_empty():
			continue
		var d := _base(rid, e, "creature", (st["critters"][id]["pos"] as Array).duplicate())
		if not d.has("enemy_id"):
			d["enemy_id"] = "rock_grub"
		entities.append(d)
	for w in st["world_items"]:
		if w.has("requires") and not Kit.cond(w["requires"], flags):
			continue
		var d := {"kind": "pickup", "id": "puz_%s_wi_%s_%d_%d" % [rid, str(w["item"]), int(w["pos"][0]), int(w["pos"][1])],
			"pos": (w["pos"] as Array).duplicate(), "sprite": Items.sprite_of(str(w["item"])),
			"puzzle_room": rid, "puzzle_eid": "wi:" + str(w.get("src", str(w["item"])))}
		entities.append(d)
