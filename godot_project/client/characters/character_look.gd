extends RefCounted
class_name DmbCharLook

## One persistent appearance: an outfit sheet, a hairstyle, a beard and the tints of every layer.
## Built only from stable identifiers (a named character, a simulation entity id), never from a random generator, so the same person
## looks the same after a reload, on every client of a LAN game, and whenever it leaves and re-enters the screen.

const Lib = preload("res://client/characters/character_library.gd")

var key := ""
var outfit := ""
var body := "adult"
var hair_style := "bald"
var beard_style := "none"
var tint_skin := Color.WHITE
var tint_hair := Color.WHITE
var tint_a := Color.WHITE
var tint_b := Color.WHITE
var tint_c := Color.WHITE
var clips := "civil"
var magic := Color(0.6, 0.86, 1.0)
var display_name := ""
var phase := 0.0  # a stable offset so a crowd does not breathe in unison
var scale_mul := 1.0

static var _cache: Dictionary = {}


static func make(key_: String, outfit_: String, h: int, spec: Dictionary = {}) -> DmbCharLook:
	var d := Lib.data()
	var o := Lib.outfit(outfit_)
	var look := DmbCharLook.new()
	look.key = key_
	look.outfit = outfit_
	look.body = str(o.get("body", "adult"))
	look.clips = str(o.get("clips", "civil"))
	look.phase = float(h % 1000) / 1000.0
	var mg: Array = o.get("magic", [150, 220, 255])
	look.magic = Lib.to_color(mg)
	# skin and hair
	var skin_rgb: Array
	if spec.has("skin"):
		skin_rgb = _rgb(spec["skin"], d.get("skin", []))
	else:
		skin_rgb = d["skin"][Lib.pick_weighted(d.get("skin_weights", []), h >> 3)]
	look.tint_skin = Lib.to_tint(skin_rgb)
	var hair_rgb: Array
	if spec.has("hair"):
		hair_rgb = _rgb(spec["hair"], d.get("hair", []))
	else:
		hair_rgb = d["hair"][Lib.pick_weighted(d.get("hair_weights", []), h >> 7)]
	look.tint_hair = Lib.to_tint(hair_rgb)
	var styles: Array = o.get("hairs", ["short"])
	look.hair_style = str(spec.get("hair_style", styles[(h >> 11) % styles.size()]))
	var beards: Array = o.get("beards", ["none"])
	look.beard_style = str(spec.get("beard", beards[(h >> 15) % beards.size()]))
	if look.body == "child":
		look.beard_style = "none"
	# clothes: a / b / c from the outfit's palette, tribe or wizard colours filling the T* / W* slots
	var pal: Dictionary = o.get("pal", {})
	var over: Dictionary = spec.get("pal", {})
	var tribe_name := str(spec.get("tribe", ""))
	var tribe_sets: Array = d.get("tribes", {}).get(tribe_name, d.get("tribes", {}).get("empire", []))
	var tset: Array = tribe_sets[(h >> 19) % tribe_sets.size()] if not tribe_sets.is_empty() else [[150, 150, 150], [150, 150, 150], [150, 150, 150]]
	var wsets: Array = d.get("wizard_sets", [])
	var wset: Array = wsets[(h >> 19) % wsets.size()] if not wsets.is_empty() else tset
	if spec.has("wizard_set"):
		wset = spec["wizard_set"]
	for slot in ["a", "b", "c"]:
		var v: Variant = over.get(slot, pal.get(slot, [160, 160, 160]))
		var rgb: Array
		if typeof(v) == TYPE_STRING:
			var idx := int(str(v).substr(1, 1))
			rgb = tset[idx] if str(v).begins_with("T") else wset[idx]
		else:
			rgb = v
		var tint := Lib.to_tint(rgb)
		match slot:
			"a":
				look.tint_a = tint
			"b":
				look.tint_b = tint
			"c":
				look.tint_c = tint
	return look


static func _rgb(v: Variant, table: Array) -> Array:
	if typeof(v) == TYPE_ARRAY:
		return v
	return table[clampi(int(v), 0, table.size() - 1)]


static func cached(key_: String) -> DmbCharLook:
	return _cache.get(key_)


static func store(look: DmbCharLook) -> DmbCharLook:
	_cache[look.key] = look
	return look


func outfit_texture() -> Texture2D:
	return Lib.texture("outfits/%s.png" % outfit)


func portrait_texture() -> Texture2D:
	return Lib.texture("outfits/%s_p.png" % outfit)


func hair_texture(portrait := false) -> Texture2D:
	if hair_style == "bald" or hair_style == "":
		return null
	return Lib.texture("hair/hair_%s_%s%s.png" % [body, hair_style, "_p" if portrait else ""])


func beard_texture(portrait := false) -> Texture2D:
	if beard_style == "none" or beard_style == "":
		return null
	return Lib.texture("hair/beard_adult_%s%s.png" % [beard_style, "_p" if portrait else ""])


func describe() -> Dictionary:
	return {"key": key, "outfit": outfit, "hair": hair_style, "beard": beard_style, "skin": tint_skin.to_html(false), "a": tint_a.to_html(false), "b": tint_b.to_html(false), "c": tint_c.to_html(false)}
