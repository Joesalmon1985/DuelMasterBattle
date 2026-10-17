extends RefCounted
class_name DmbCharLib

## The character catalogue: sheets, clip tables and palettes written by tools/character_sprites (assets/characters/characters.json).
## Everything is loaded through ResourceLoader (never Image.load on res://), so it also works from an exported APK.

const ROOT := "res://assets/characters/"
const BANDS := ["line", "skin", "a", "b", "c", "detail"]

static var _data: Dictionary = {}
static var _tex: Dictionary = {}
static var _missing: Dictionary = {}


static func data() -> Dictionary:
	if _data.is_empty():
		_data = _load_json(ROOT + "characters.json")
	return _data


static func available() -> bool:
	return not data().is_empty() and data().has("outfits")


static func _load_json(path: String) -> Dictionary:
	var parsed: Variant = null
	if ResourceLoader.exists(path):
		var res: Resource = load(path)
		if res is JSON:
			parsed = (res as JSON).data
	if parsed == null and FileAccess.file_exists(path):
		var f := FileAccess.open(path, FileAccess.READ)
		if f != null:
			parsed = JSON.parse_string(f.get_as_text())
	return parsed if typeof(parsed) == TYPE_DICTIONARY else {}


static func texture(rel: String) -> Texture2D:
	if _tex.has(rel):
		return _tex[rel]
	var path := ROOT + rel
	var t: Texture2D = null
	if ResourceLoader.exists(path):
		t = load(path) as Texture2D
	if t == null:
		_missing[rel] = true
	_tex[rel] = t
	return t


static func missing() -> Array:
	return _missing.keys()


static func cell() -> Vector2i:
	var c: Array = data().get("cell", [56, 48])
	return Vector2i(int(c[0]), int(c[1]))


static func outfit(id: String) -> Dictionary:
	return data().get("outfits", {}).get(id, {})


static func has_outfit(id: String) -> bool:
	return data().get("outfits", {}).has(id)


static func clip(name: String) -> Dictionary:
	return data().get("clips", {}).get(name, {})


static func clip_available(outfit_id: String, name: String) -> bool:
	var o := outfit(outfit_id)
	if o.is_empty():
		return false
	var set_name := str(o.get("clips", "civil"))
	return name in data().get("clip_sets", {}).get(set_name, [])


static func fps(name: String) -> float:
	return float(data().get("fps", {}).get(name, 8))


static func loops(name: String) -> bool:
	return bool(data().get("loop", {}).get(name, true))


static func clip_frames(name: String) -> int:
	return int(clip(name).get("frames", 1))


static func clip_start(name: String) -> int:
	return int(clip(name).get("start", 0))


## FNV-1a over the UTF-8 bytes: identical on every platform and every run (String.hash() is not promised to be).
static func stable_hash(s: String) -> int:
	var h := 2166136261
	for b in s.to_utf8_buffer():
		h = ((h ^ int(b)) * 16777619) & 0xFFFFFFFF
	return h


static func pick_weighted(weights: Array, r: int) -> int:
	var total := 0
	for w in weights:
		total += int(w)
	if total <= 0:
		return 0
	var x := r % total
	for i in weights.size():
		x -= int(weights[i])
		if x < 0:
			return i
	return weights.size() - 1


static func to_color(rgb: Array) -> Color:
	return Color(float(rgb[0]) / 255.0, float(rgb[1]) / 255.0, float(rgb[2]) / 255.0, 1.0)


## Luminance layers are multiplied by a tint; the ramp's base level is 0.9, so the tint is the wanted colour / 0.9.
static func to_tint(rgb: Array) -> Color:
	return Color(minf(float(rgb[0]) / 255.0 / 0.9, 1.0), minf(float(rgb[1]) / 255.0 / 0.9, 1.0), minf(float(rgb[2]) / 255.0 / 0.9, 1.0), 1.0)
