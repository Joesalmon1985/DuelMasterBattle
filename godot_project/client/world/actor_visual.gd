extends RefCounted
class_name DmbActorVisual
## One fallback for a character sprite that is not on disk.
## Never calls load() on a missing resource. The stand-in is a generated
## rectangle-and-circle texture plus a name label, so the NPC stays visible.


static func rel_path(sprite: String, facing: String, frame: int = 0) -> String:
	return "chars/%s_%s_%d.png" % [sprite, facing, frame]


static func resource_exists(pixel_root: String, rel: String) -> bool:
	return ResourceLoader.exists(pixel_root + rel)


## Apply a real texture, or a geometric placeholder if the resource is missing.
## Returns true when the placeholder path was used.
static func apply(node: Sprite2D, pixel_root: String, sprite: String, facing: String, frame: int, label: String) -> bool:
	var rel := rel_path(sprite, facing, frame)
	var missing := not resource_exists(pixel_root, rel)
	node.set_meta("sprite", sprite)
	node.set_meta("facing", facing)
	node.set_meta("placeholder", missing)
	node.set_meta("label", label)
	if missing:
		node.texture = _placeholder_texture(label if label != "" else sprite)
		_ensure_label(node, label if label != "" else sprite)
		return true
	var tex: Texture2D = load(pixel_root + rel)
	node.texture = tex
	_clear_label(node)
	return false


static func is_placeholder(node: Sprite2D) -> bool:
	return node != null and bool(node.get_meta("placeholder", false))


static func _placeholder_texture(label: String) -> ImageTexture:
	var img := Image.create(16, 24, false, Image.FORMAT_RGBA8)
	img.fill(Color(0, 0, 0, 0))
	var hue := float(label.hash() % 360) / 360.0
	var body := Color.from_hsv(hue, 0.45, 0.72, 1.0)
	var head := Color.from_hsv(hue, 0.25, 0.92, 1.0)
	for y in range(10, 23):
		for x in range(2, 14):
			img.set_pixel(x, y, body)
	var cx := 8
	var cy := 6
	for y in range(2, 11):
		for x in range(4, 12):
			if (x - cx) * (x - cx) + (y - cy) * (y - cy) <= 16:
				img.set_pixel(x, y, head)
	return ImageTexture.create_from_image(img)


static func _ensure_label(node: Sprite2D, text: String) -> void:
	var lbl: Label = node.get_node_or_null("fallback_label")
	if lbl == null:
		lbl = Label.new()
		lbl.name = "fallback_label"
		lbl.position = Vector2(-4, -14)
		lbl.add_theme_font_size_override("font_size", 8)
		lbl.add_theme_color_override("font_color", Color(1, 1, 1, 1))
		lbl.add_theme_color_override("font_outline_color", Color(0, 0, 0, 1))
		lbl.add_theme_constant_override("outline_size", 3)
		node.add_child(lbl)
	lbl.text = text
	lbl.visible = true


static func _clear_label(node: Sprite2D) -> void:
	var lbl: Label = node.get_node_or_null("fallback_label")
	if lbl != null:
		lbl.visible = false
