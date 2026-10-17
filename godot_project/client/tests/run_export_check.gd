extends SceneTree

## Run against an exported pack to prove the character assets are inside it and load without the source tree:
##   godot --headless --export-pack Android /tmp/game.pck        (from godot_project)
##   cd $(mktemp -d) && godot --headless --main-pack /tmp/game.pck --script res://client/tests/run_export_check.gd
## It must find the library JSON, every sheet, and draw a look using nothing but the pack.

const Lib = preload("res://client/characters/character_library.gd")
const Appearance = preload("res://client/characters/character_appearance.gd")


func _init() -> void:
	var fails := 0
	var path := "res://assets/characters/characters.json"
	print("json exists via ResourceLoader: ", ResourceLoader.exists(path), "  via FileAccess: ", FileAccess.file_exists(path))
	if not Lib.available():
		print("EXPORT_CHECK_FAIL library JSON did not load from the pack")
		quit(1)
		return
	var n := 0
	var bad := []
	for id in Lib.data()["outfits"]:
		for suffix in ["", "_p"]:
			var t := Lib.texture("outfits/%s%s.png" % [id, suffix])
			n += 1
			if t == null:
				bad.append(id + suffix)
	for body in Lib.data()["hair_styles"]:
		for st in Lib.data()["hair_styles"][body]:
			for suffix in ["", "_p"]:
				n += 1
				if Lib.texture("hair/hair_%s_%s%s.png" % [body, st, suffix]) == null:
					bad.append("hair_%s_%s%s" % [body, st, suffix])
	for st in Lib.data()["beard_styles"]:
		for suffix in ["", "_p"]:
			n += 1
			if Lib.texture("hair/beard_adult_%s%s.png" % [st, suffix]) == null:
				bad.append("beard_%s%s" % [st, suffix])
	print("textures loaded from the pack: %d of %d" % [n - bad.size(), n])
	if not bad.is_empty():
		print("EXPORT_CHECK_FAIL missing: ", bad.slice(0, 12))
		fails += 1
	var look = Appearance.named("archmage")
	if look == null or look.outfit_texture() == null or look.portrait_texture() == null:
		print("EXPORT_CHECK_FAIL named look")
		fails += 1
	print("EXPORT_CHECK_OK" if fails == 0 else "EXPORT_CHECK_FAIL")
	quit(1 if fails > 0 else 0)
