class_name DmbArt
extends RefCounted

static var _cache: Dictionary = {}


static func load_texture(relative_path: String) -> Texture2D:
	if _cache.has(relative_path):
		return _cache[relative_path]
	var full: String = ProjectSettings.globalize_path("res://assets/" + relative_path)
	if not FileAccess.file_exists(full):
		return null
	var img := Image.new()
	var err := img.load(full)
	if err != OK:
		return null
	var tex := ImageTexture.create_from_image(img)
	_cache[relative_path] = tex
	return tex


static func magic_icon_path(magic_id: int) -> String:
	var slugs := [
		"flame", "frost", "storm", "stone", "light",
		"shadow", "vine", "metal", "spirit", "arcane",
	]
	if magic_id < 0 or magic_id >= slugs.size():
		return ""
	return "icons/magic_%s.png" % slugs[magic_id]


static func point_icon_path(point_index: int) -> String:
	var slugs := ["shield", "body", "staff", "mind"]
	if point_index < 0 or point_index >= slugs.size():
		return ""
	return "icons/point_%s.png" % slugs[point_index]


static func feedback_icon_path(kind: String) -> String:
	return "icons/feedback_%s.png" % kind


static func expected_asset_paths() -> Array:
	var paths: Array = [
		"sprites/player_wizard.png",
		"sprites/enemy_wizard.png",
		"sprites/duel_background.png",
		"icons/feedback_hit.png",
		"icons/feedback_weakness.png",
		"icons/feedback_unaffected.png",
	]
	for slug in ["flame", "frost", "storm", "stone", "light", "shadow", "vine", "metal", "spirit", "arcane"]:
		paths.append("icons/magic_%s.png" % slug)
	for slug in ["shield", "body", "staff", "mind"]:
		paths.append("icons/point_%s.png" % slug)
	return paths
