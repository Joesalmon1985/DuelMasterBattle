extends RefCounted
class_name DmbVisualLanguage

## Canonical placeholder colours/shapes for full-world presentation.
## See docs/WORLD_VISUAL_LANGUAGE.md

const FACTION_COLORS := {
	"faction:1": Color("#D4A017"),
	"faction:2": Color("#3A6EA5"),
	"faction:3": Color("#3D8B57"),
	"faction:4": Color("#B85C38"),
	"faction:red": Color(0.82, 0.22, 0.22),
	"faction:blue": Color(0.22, 0.42, 0.88),
	"faction:a": Color(0.75, 0.55, 0.15),
}

const NEUTRAL := Color("#7A7A7A")
const HAZARD := Color("#B0006E")

const CATAN_PIP := {
	"timber": Color(0.45, 0.28, 0.12),
	"brick": Color(0.72, 0.35, 0.22),
	"wool": Color(0.92, 0.90, 0.82),
	"grain": Color(0.90, 0.75, 0.20),
	"ore": Color(0.45, 0.48, 0.55),
}


static func faction_color(faction_id: String) -> Color:
	return FACTION_COLORS.get(faction_id, NEUTRAL)


static func cargo_color(good_id: String) -> Color:
	return CATAN_PIP.get(good_id, Color(0.7, 0.7, 0.7))


static func archetype_polygon(archetype: String, radius: float = 14.0) -> PackedVector2Array:
	match str(archetype).to_lower():
		"skirmisher":
			return PackedVector2Array([
				Vector2(0, -radius), Vector2(radius * 0.85, radius * 0.7), Vector2(-radius * 0.85, radius * 0.7)
			])
		"heavy":
			var pts := PackedVector2Array()
			for i in 6:
				var a := TAU * float(i) / 6.0 - PI * 0.5
				pts.append(Vector2(cos(a), sin(a)) * radius)
			return pts
		_:
			# line soldier — square
			return PackedVector2Array([
				Vector2(-radius * 0.7, -radius * 0.7),
				Vector2(radius * 0.7, -radius * 0.7),
				Vector2(radius * 0.7, radius * 0.7),
				Vector2(-radius * 0.7, radius * 0.7),
			])


static func hazard_diamond(radius: float = 18.0) -> PackedVector2Array:
	return PackedVector2Array([
		Vector2(0, -radius), Vector2(radius, 0), Vector2(0, radius), Vector2(-radius, 0)
	])


static func cart_rect(half_w: float = 16.0, half_h: float = 10.0) -> PackedVector2Array:
	return PackedVector2Array([
		Vector2(-half_w, -half_h), Vector2(half_w, -half_h),
		Vector2(half_w, half_h), Vector2(-half_w, half_h)
	])
