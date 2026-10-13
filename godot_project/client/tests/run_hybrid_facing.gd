extends SceneTree

const HybridArt = preload("res://client/hybrid/hybrid_art.gd")

## Facing proof for imported sequence art (plan v2 8.5 "Facing"). For each unit with a protruding weapon, ask the real hybrid_art
## code which frame it draws for a unit facing east and west, load that frame and check the sprite extends towards its heading
## (barrel / rifle on the side it faces). Also prints the full index table. No simulation server required.

const UNITS := ["openra.e1", "openra.e3", "openra.3tnk", "openra.4tnk"]  # the sprites whose weapon sticks out far enough for a pixel test to tell east from west
const COMPASS := ["n", "ne", "e", "se", "s", "sw", "w", "nw"]


func _init() -> void:
	call_deferred("_run")


func _extent_bias(path: String) -> float:
	# (distance from the opaque centroid to the leftmost pixel) - (distance to the rightmost): > 0 means mass sticks out to the left
	var img := Image.load_from_file(ProjectSettings.globalize_path(path))
	if img == null:
		return NAN
	var minx := 9999
	var maxx := -1
	var sx := 0.0
	var n := 0
	for y in img.get_height():
		for x in img.get_width():
			if img.get_pixel(x, y).a > 0.1:
				minx = mini(minx, x)
				maxx = maxi(maxx, x)
				sx += x
				n += 1
	if n == 0:
		return NAN
	var cx := sx / n
	return (cx - minx) - (maxx - cx)


func _run() -> void:
	var art := HybridArt.new()
	art.load_catalogue()
	var bad := 0
	for id in UNITS:
		var item: Dictionary = art.items.get(id, {})
		if item.is_empty():
			print("HYBRID_FACING_FAIL missing item ", id)
			bad += 1
			continue
		var table := {}
		for c in COMPASS:
			table[c] = art._sequence_index(item, {"facing": c, "status": "idle"})
		print("table ", id, " ", JSON.stringify(table))
		var pattern := "res://client/hybrid/art/openra/%s-%%04d.png" % String(item["prefix"])
		var east := _extent_bias(pattern % int(table["e"]))
		var west := _extent_bias(pattern % int(table["w"]))
		var ok: bool = east < west and east < 0.0  # the rifle or barrel sticks out on the side the unit faces (east = right = negative bias)
		print("  ", id, " bias east=", snappedf(east, 0.01), " west=", snappedf(west, 0.01), " ", "ok" if ok else "WRONG")
		if not ok:
			bad += 1
	print("HYBRID_FACING_", "OK" if bad == 0 else "FAIL", " ", bad)
	quit(0 if bad == 0 else 1)
