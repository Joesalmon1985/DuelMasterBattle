class_name DmbArt
extends RefCounted

static var _cache: Dictionary = {}
static var _manifest_cache: Dictionary = {}

const LOCUS_SLUGS := [
	"roach", "uzag", "lieana", "gyse", "vorr", "mael", "oshen", "keth",
]

const ESSENCE_SLUGS := [
	"flame", "frost", "storm", "stone", "light",
	"shadow", "vine", "metal", "spirit", "arcane",
]

const ENEMY_ARCHETYPE_MAP := {
	"blue_wizard": "blue_apprentice",
	"thorn_druid": "thorn_adept",
	"mirror_mage": "mirror_mage",
	"archmage": "archmage",
	"eightfold_warden": "eightfold_warden",
}

const ENEMY_PORTRAITS := {
	"blue_wizard": "sprites/enemy_blue_apprentice.png",
	"thorn_druid": "sprites/enemy_thorn_adept.png",
	"mirror_mage": "sprites/enemy_mirror_mage.png",
	"archmage": "sprites/enemy_archmage.png",
	"eightfold_warden": "sprites/enemy_eightfold_warden.png",
}

const COMPOSITE_ROOT := "generated/composite/"


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
	if magic_id < 0 or magic_id >= ESSENCE_SLUGS.size():
		return ""
	return "icons/magic_%s.png" % ESSENCE_SLUGS[magic_id]


static func locus_icon_path(locus_index: int) -> String:
	if locus_index < 0 or locus_index >= LOCUS_SLUGS.size():
		return ""
	return "icons/locus_%s.png" % LOCUS_SLUGS[locus_index]


static func point_icon_path(point_index: int) -> String:
	return locus_icon_path(point_index)


static func essence_slug(essence_id: int) -> String:
	if essence_id < 0 or essence_id >= ESSENCE_SLUGS.size():
		return ""
	return ESSENCE_SLUGS[essence_id]


static func essence_layer_path(essence_id: int, layer: String) -> String:
	var slug := essence_slug(essence_id)
	if slug == "":
		return ""
	return COMPOSITE_ROOT + "essences/%s/%s.png" % [slug, layer]


static func locus_rune_path(locus_index: int, filled: bool) -> String:
	if locus_index < 0 or locus_index >= LOCUS_SLUGS.size():
		return ""
	var state := "rune_filled" if filled else "rune_empty"
	return COMPOSITE_ROOT + "loci/%s/%s.png" % [LOCUS_SLUGS[locus_index], state]


static func ward_part_path(part: String) -> String:
	return COMPOSITE_ROOT + "wards/%s.png" % part


static func effect_part_path(part: String) -> String:
	return COMPOSITE_ROOT + "effects/%s.png" % part


static func ui_chrome_path(name: String) -> String:
	return COMPOSITE_ROOT + "ui/%s.png" % name


static func wizard_archetype_from_enemy(archetype: String) -> String:
	if ENEMY_ARCHETYPE_MAP.has(archetype):
		return ENEMY_ARCHETYPE_MAP[archetype]
	return archetype


static func wizard_part_path(archetype: String, part: String) -> String:
	return COMPOSITE_ROOT + "wizards/%s/%s.png" % [archetype, part]


static func composite_wizard_manifest_path(archetype: String) -> String:
	return COMPOSITE_ROOT + "wizards/%s/manifest.json" % archetype


static func load_wizard_manifest(archetype: String) -> Dictionary:
	if _manifest_cache.has(archetype):
		return _manifest_cache[archetype]
	var path := composite_wizard_manifest_path(archetype)
	var full := ProjectSettings.globalize_path("res://assets/" + path)
	if not FileAccess.file_exists(full):
		_manifest_cache[archetype] = {}
		return {}
	var f := FileAccess.open(full, FileAccess.READ)
	if f == null:
		return {}
	var data = JSON.parse_string(f.get_as_text())
	if typeof(data) != TYPE_DICTIONARY:
		data = {}
	_manifest_cache[archetype] = data
	return data


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
	for slug in ESSENCE_SLUGS:
		paths.append("icons/magic_%s.png" % slug)
		for layer in ["core_glyph", "inner_glow", "outer_aura", "trail", "spark"]:
			paths.append(COMPOSITE_ROOT + "essences/%s/%s.png" % [slug, layer])
	for slug in LOCUS_SLUGS:
		paths.append("icons/locus_%s.png" % slug)
		for state in ["rune_empty", "rune_filled"]:
			paths.append(COMPOSITE_ROOT + "loci/%s/%s.png" % [slug, state])
	for path in ENEMY_PORTRAITS.values():
		paths.append(path)
	for part in ["outer_ring", "inner_ring", "runes", "surface", "cracks", "instability"]:
		paths.append(ward_part_path(part))
	for part in ["impact_flash", "shockwave_ring", "ward_ripple", "fracture_glyph", "echo_ring", "fade_mote"]:
		paths.append(effect_part_path(part))
	for name in ["button_gem", "button_gem_pressed", "timer_ring"]:
		paths.append(ui_chrome_path(name))
	for arch in ["player", "blue_apprentice", "thorn_adept", "mirror_mage", "archmage", "eightfold_warden"]:
		for part in ["torso", "head", "back_aura", "cast_glow"]:
			paths.append(wizard_part_path(arch, part))
	return paths
