extends SceneTree
## TEMP QA tool (not shipped): dumps every catalogue room + its fresh-state
## visual_map (exactly what the test-room driver draws) as line-delimited JSON
## to room_export.json in the project root, for offline rendering.
const Kit = preload("res://sim/world/puzzle_kit.gd")
const Rooms = preload("res://sim/world/puzzle_rooms.gd")

func _init() -> void:
	var out := FileAccess.open("res://room_export.json", FileAccess.WRITE)
	var all: Array = Rooms.all()
	for r in all:
		var st: Dictionary = Kit.fresh_state(r)
		var inv: Array = (r.get("items", []) as Array).duplicate()
		Kit.sync_inventory(st, inv)
		var vmap: Dictionary = Kit.visual_map(r, st)
		var ents_out := []
		for e in r["entities"]:
			var v: Dictionary = vmap.get(str(e.get("id", "")), {})
			var c: Color = v.get("color", Color(1, 1, 1))
			ents_out.append({
				"id": str(e.get("id", "")), "kind": str(e.get("kind", "")),
				"pos": e.get("pos", [-1, -1]),
				"state": str(v.get("state", "?")), "color": c.to_html(),
				"label": str(v.get("label", "")), "shape": str(v.get("shape", "block")),
				"visible": bool(v.get("visible", true)),
			})
		var extra := []
		for k in vmap:
			if str(k).begins_with("wi_") or str(k).begins_with("beam_"):
				var v2: Dictionary = vmap[k]
				var c2: Color = v2.get("color", Color(1, 1, 1))
				extra.append({"key": str(k), "pos": v2.get("pos", [-1, -1]),
					"state": str(v2.get("state", "")), "color": c2.to_html(),
					"label": str(v2.get("label", "")), "shape": str(v2.get("shape", "block"))})
		var rec := {"id": str(r["id"]), "num": int(r["num"]), "title": str(r["title"]),
			"rows": r["rows"], "start": r["start"],
			"entities": ents_out, "extra": extra}
		out.store_line(JSON.stringify(rec))
	out.close()
	print("EXPORT_DONE rooms=", all.size())
	quit()
