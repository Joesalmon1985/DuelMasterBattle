extends SceneTree

const HybridArt = preload("res://client/hybrid/hybrid_art.gd")

## Red Alert building states through the real hybrid_art: every building with imported states resolves a texture for idle, the construction animation follows
## the build progress with different frames, and a damaged building shows its damaged picture. No simulation server required.


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var art := HybridArt.new()
	art.load_catalogue()
	var bad := 0
	var n := 0
	var made := 0
	for id in art.items.keys():
		var item: Dictionary = art.items[id]
		if not str(id).begins_with("openra.") or not item.has("states"):
			continue
		n += 1
		var e := {"class": "building", "hp": 100, "max_hp": 100, "definition": str(id)}
		var idle: Texture2D = art.state_texture(e, item, 0.0)
		if idle == null or idle.get_width() < 4:
			print("FAIL idle ", id)
			bad += 1
		if item["states"].has("damaged"):
			var d := {"class": "building", "hp": 40, "max_hp": 100}
			if art.state_for(d, item) != "damaged":
				print("FAIL damaged state ", id)
				bad += 1
		if item["states"].has("make") and (item["states"]["make"]["files"] as Array).size() > 3:
			var a := {"class": "building", "hp": 15, "max_hp": 100, "constructing": {}}
			var b := {"class": "building", "hp": 95, "max_hp": 100, "constructing": {}}
			var ta: Texture2D = art.state_texture(a, item, 0.0)
			var tb: Texture2D = art.state_texture(b, item, 0.0)
			if ta == null or tb == null or ta == tb:
				print("FAIL make progress ", id)
				bad += 1
			else:
				made += 1
	print("buildings with states ", n, " with a construction animation ", made)
	print("HYBRID_OPENRA_BUILDINGS_OK" if bad == 0 and n > 20 else "HYBRID_OPENRA_BUILDINGS_FAIL %d" % bad)
	quit(0 if bad == 0 else 1)
