extends Node2D
class_name DmbUnitController

## Binds one controller to a persistent unit ID (C07).
## Visuals are created in ensure_visuals() — never rely on @onready for late-added children.

const TILE := 64.0

signal selected(unit_id: String)

var unit_id: String = ""
var faction_id: String = ""
var archetype: String = ""
var definition_id: String = ""
var max_health: int = 1
var current_health: int = 1
var alive: bool = true
var selected_flag: bool = false
var attack_flash_ms: float = 0.0
var hit_flash_ms: float = 0.0
var death_flash_ms: float = 0.0

var _poly: Polygon2D
var _outline: Line2D
var _label: Label
var _hp_bg: ColorRect
var _hp_fg: ColorRect
var _built := false

const FACTION_COLORS := {
	"faction:red": Color(0.82, 0.22, 0.22),
	"faction:blue": Color(0.22, 0.42, 0.88),
	"faction:a": Color(0.75, 0.55, 0.15),
}

const ARCHETYPE_SHORT := {
	"skirmisher": "SKIRM",
	"line": "LINE",
	"heavy": "HEAVY",
}


func _ready() -> void:
	ensure_visuals()
	_refresh_visual()


func _process(delta: float) -> void:
	var dirty := false
	if attack_flash_ms > 0.0:
		attack_flash_ms = maxf(0.0, attack_flash_ms - delta * 1000.0)
		dirty = true
	if hit_flash_ms > 0.0:
		hit_flash_ms = maxf(0.0, hit_flash_ms - delta * 1000.0)
		dirty = true
	if death_flash_ms > 0.0:
		death_flash_ms = maxf(0.0, death_flash_ms - delta * 1000.0)
		dirty = true
	if dirty:
		_refresh_visual()


func ensure_visuals() -> void:
	if _built:
		return
	_poly = Polygon2D.new()
	_poly.name = "Body"
	add_child(_poly)
	_outline = Line2D.new()
	_outline.name = "Outline"
	_outline.width = 2.0
	_outline.default_color = Color(1, 1, 0.35)
	_outline.visible = false
	add_child(_outline)
	_hp_bg = ColorRect.new()
	_hp_bg.name = "HpBg"
	_hp_bg.size = Vector2(36, 5)
	_hp_bg.position = Vector2(-18, -28)
	_hp_bg.color = Color(0.1, 0.1, 0.1, 0.85)
	add_child(_hp_bg)
	_hp_fg = ColorRect.new()
	_hp_fg.name = "HpFg"
	_hp_fg.size = Vector2(36, 5)
	_hp_fg.position = Vector2(-18, -28)
	_hp_fg.color = Color(0.25, 0.85, 0.35)
	add_child(_hp_fg)
	_label = Label.new()
	_label.name = "Label"
	_label.position = Vector2(-42, 16)
	_label.add_theme_font_size_override("font_size", 11)
	_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_label.custom_minimum_size = Vector2(84, 0)
	add_child(_label)
	_built = true


func grid_to_world(pos) -> Vector2:
	var gx := 0.0
	var gy := 0.0
	if pos is Vector2:
		gx = pos.x
		gy = pos.y
	elif pos is Array and pos.size() >= 2:
		gx = float(pos[0])
		gy = float(pos[1])
	return Vector2(gx * TILE + TILE * 0.5, gy * TILE + TILE * 0.5)


func bind_unit(state: Dictionary) -> void:
	ensure_visuals()
	unit_id = str(state.get("id", ""))
	faction_id = str(state.get("faction_id", ""))
	definition_id = str(state.get("definition_id", ""))
	archetype = _archetype_from_definition(definition_id, state)
	max_health = maxi(1, int(state.get("max_health", 1)))
	var prev_hp := current_health
	current_health = int(state.get("current_health", max_health))
	var was_alive := alive
	alive = bool(state.get("alive", true)) and current_health > 0
	if prev_hp > current_health and alive:
		flash_hit()
	if was_alive and not alive:
		flash_death()
	position = grid_to_world(state.get("position", [0, 0]))
	_refresh_visual()


func apply_checkpoint(state: Dictionary) -> void:
	if str(state.get("id", "")) != unit_id and unit_id != "":
		return
	bind_unit(state)


func set_selected(on: bool) -> void:
	selected_flag = on
	_refresh_visual()


func flash_attack() -> void:
	attack_flash_ms = 180.0
	_refresh_visual()


func flash_hit() -> void:
	hit_flash_ms = 160.0
	_refresh_visual()


func flash_death() -> void:
	death_flash_ms = 400.0
	_refresh_visual()


func _archetype_from_definition(def_id: String, state: Dictionary) -> String:
	var from_state := str(state.get("archetype", "")).to_lower()
	if from_state in ARCHETYPE_SHORT:
		return from_state
	var lowered := def_id.to_lower()
	for name in ["skirmisher", "line", "heavy"]:
		if name in lowered:
			return name
	return "line"


func _shape_points(kind: String) -> PackedVector2Array:
	match kind:
		"skirmisher":
			return PackedVector2Array([
				Vector2(0, -16), Vector2(14, 14), Vector2(-14, 14)
			])
		"heavy":
			var pts := PackedVector2Array()
			for i in range(6):
				var a := -PI / 2.0 + float(i) * TAU / 6.0
				pts.append(Vector2(cos(a), sin(a)) * 15.0)
			return pts
		_:
			return PackedVector2Array([
				Vector2(-12, -12), Vector2(12, -12), Vector2(12, 12), Vector2(-12, 12)
			])


func _refresh_visual() -> void:
	if not _built:
		return
	var color: Color = FACTION_COLORS.get(faction_id, Color(0.7, 0.7, 0.7))
	if not alive:
		color = Color(0.25, 0.25, 0.28)
	elif attack_flash_ms > 0.0:
		color = color.lerp(Color(1.0, 0.85, 0.2), 0.65)
	elif hit_flash_ms > 0.0:
		color = color.lerp(Color(1.0, 0.35, 0.35), 0.7)
	_poly.color = color
	_poly.polygon = _shape_points(archetype)
	_outline.visible = selected_flag and alive
	if _outline.visible:
		var outline_pts := _shape_points(archetype)
		outline_pts.append(outline_pts[0])
		_outline.points = outline_pts
	var ratio := clampf(float(current_health) / float(max_health), 0.0, 1.0)
	_hp_fg.size = Vector2(36.0 * ratio, 5)
	_hp_fg.color = Color(0.25, 0.85, 0.35) if ratio > 0.35 else Color(0.9, 0.25, 0.2)
	_hp_bg.visible = alive or death_flash_ms > 0.0
	_hp_fg.visible = _hp_bg.visible
	var faction_short := faction_id.get_slice(":", 1).capitalize() if ":" in faction_id else faction_id
	var type_short: String = ARCHETYPE_SHORT.get(archetype, archetype.to_upper())
	_label.text = "%s %s\n%d/%d" % [faction_short, type_short, current_health, max_health]
	_label.modulate = Color(1, 1, 1, 1) if alive else Color(0.6, 0.6, 0.6, 0.7)
	modulate.a = 0.45 if (not alive and death_flash_ms <= 0.0) else 1.0
