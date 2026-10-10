extends SceneTree

const HexCoords = preload("res://client/hybrid/hex_coords.gd")

## Compare HybridHexCoords to the Python fixture. No simulation server required.


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var path := ProjectSettings.globalize_path("res://client/tests/fixtures/hex_samples.json")
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		print("HYBRID_COORDS_FAIL missing fixture")
		quit(1)
		return
	var parsed = JSON.parse_string(file.get_as_text())
	file.close()
	if typeof(parsed) != TYPE_ARRAY:
		print("HYBRID_COORDS_FAIL fixture")
		quit(1)
		return
	var mismatches := 0
	for row in parsed:
		var tx := int(row["tx"])
		var ty := int(row["ty"])
		var got: Vector2i = HexCoords.tile_to_hex(tx, ty)
		if got.x != int(row["q"]) or got.y != int(row["r"]):
			mismatches += 1
			print("HYBRID_COORDS_MISMATCH %d %d got %s expected %s" % [tx, ty, got, Vector2i(int(row["q"]), int(row["r"]))])
			if mismatches > 8:
				break
	if mismatches > 0:
		print("HYBRID_COORDS_FAIL %d" % mismatches)
		quit(1)
		return
	print("HYBRID_COORDS_OK %d" % parsed.size())
	quit(0)
