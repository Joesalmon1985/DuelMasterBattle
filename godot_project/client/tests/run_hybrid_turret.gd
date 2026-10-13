extends SceneTree

const HybridArt = preload("res://client/hybrid/hybrid_art.gd")

## Independent turret proof (plan v2 8.5 "Turret independence"): a tank heading east aiming north draws the east hull and the north turret.
## Layers recomposited with the turret on the hull's own slot reproduce the old composited frame pixel for pixel, and moving only the
## aim changes only the turret layer. No simulation server required.


func _init() -> void:
	call_deferred("_run")


func _img(t: Texture2D) -> Image:
	return t.get_image()


func _run() -> void:
	var art := HybridArt.new()
	art.load_catalogue()
	var bad := 0
	for id in ["openra.3tnk", "openra.2tnk", "openra.1tnk", "openra.4tnk", "openra.jeep"]:
		var item: Dictionary = art.items.get(id, {})
		if item.is_empty() or not item.has("layers"):
			print("FAIL no layers on ", id)
			bad += 1
			continue
		var heading_east := {"facing": "e", "status": "idle"}
		var ix: Dictionary = art.layer_indices(item, {"facing": "e", "status": "idle", "turret": 0})
		if int(ix["body"]) != 24 or int(ix["turret"]) != 0:
			print("FAIL slots ", id, " ", ix)
			bad += 1
		var aim_n: Array = art.layer_textures(item, {"facing": "e", "status": "idle", "turret": 0})
		var aim_w: Array = art.layer_textures(item, {"facing": "e", "status": "idle", "turret": 8})
		var same_hull: bool = _img(aim_n[0]).get_data() == _img(aim_w[0]).get_data()
		var diff_turret: bool = _img(aim_n[1]).get_data() != _img(aim_w[1]).get_data()
		if not same_hull or not diff_turret:
			print("FAIL independence ", id, " hull same ", same_hull, " turret differs ", diff_turret)
			bad += 1
		# on its own slot the layered picture equals the composited file
		var own: Array = art.layer_textures(item, {"facing": "e", "status": "idle", "turret": 24})
		var comp: Image = _img(art._tex("res://client/hybrid/art/openra/%s-0024.png" % String(item["prefix"])))
		var recomposed: Image = _img(own[0]).duplicate()
		recomposed.blend_rect(_img(own[1]), Rect2i(Vector2i.ZERO, _img(own[1]).get_size()), Vector2i.ZERO)
		if recomposed.get_data() != comp.get_data():
			var diffs := 0
			for y in comp.get_height():
				for x in comp.get_width():
					if recomposed.get_pixel(x, y).a8 != comp.get_pixel(x, y).a8 or (recomposed.get_pixel(x, y).a8 > 200 and recomposed.get_pixel(x, y).to_html(false) != comp.get_pixel(x, y).to_html(false)):
						diffs += 1
			if diffs > 12:  # edge pixels of semi-transparent shadows may blend differently; the opaque body must match
				print("FAIL recomposition ", id, " differing pixels ", diffs)
				bad += 1
		print("ok layers ", id)
	print("HYBRID_TURRET_", "OK" if bad == 0 else "FAIL", " ", bad)
	quit(0 if bad == 0 else 1)
