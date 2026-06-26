class_name DmbArt
extends RefCounted

static var _cache: Dictionary = {}

const LOCUS_SLUGS := [
	"roach", "uzag", "lieana", "gyse", "vorr", "mael", "oshen", "keth",
]

const ENEMY_PORTRAITS := {
	"blue_wizard": "sprites/enemy_blue_apprentice.png",
	"thorn_druid": "sprites/enemy_thorn_adept.png",
	"mirror_mage": "sprites/enemy_mirror_mage.png",
	"archmage": "sprites/enemy_archmage.png",
	"eightfold_warden": "sprites/enemy_eightfold_warden.png",
}


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


static func locus_icon_path(locus_index: int) -> String:
	if locus_index < 0 or locus_index >= LOCUS_SLUGS.size():
		return point_icon_path(locus_index)
	return "icons/locus_%s.png" % LOCUS_SLUGS[locus_index]


static func point_icon_path(point_index: int) -> String:
	return locus_icon_path(point_index)


static func enemy_portrait_path(archetype: String) -> String:
	if ENEMY_PORTRAITS.has(archetype):
		return ENEMY_PORTRAITS[archetype]
	return "sprites/enemy_wizard.png"


static func feedback_icon_path(kind: String) -> String:
	var mapped := kind
	if kind == "fracture":
		mapped = "hit"
	elif kind == "echo":
		mapped = "weakness"
	elif kind == "fade":
		mapped = "unaffected"
	return "icons/feedback_%s.png" % mapped


static func expected_asset_paths() -> Array:
	var paths: Array = [
		"sprites/player_wizard.png",
		"sprites/enemy_wizard.png",
		"sprites/duel_background.png",
		"icons/feedback_hit.png",
		"icons/feedback_weakness.png",
		"icons/feedback_unaffected.png",
		"icons/feedback_clash.png",
		"icons/feedback_stalemate.png",
		"icons/feedback_last_stand.png",
	]
	for slug in ["flame", "frost", "storm", "stone", "light", "shadow", "vine", "metal", "spirit", "arcane"]:
		paths.append("icons/magic_%s.png" % slug)
	for slug in LOCUS_SLUGS:
		paths.append("icons/locus_%s.png" % slug)
	for path in ENEMY_PORTRAITS.values():
		paths.append(path)
	return paths
