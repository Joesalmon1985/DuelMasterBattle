extends Node2D
class_name DmbHazardActor

## Visible hazard manifestation for eligible cube duels (C08/C10).
## Not a win button — starts a real playable duel lease.

const TILE := 64.0

var cube_id: String = ""
var hex_id: String = ""
var hazard_type: String = ""
var cube_count: int = 1
var duel_eligible: bool = false
var treatment_eligible: bool = false
var outbreak_warning: bool = false
var selected_flag: bool = false
var active: bool = true

signal duel_requested(cube_id)

var _poly: Polygon2D
var _outline: Line2D
var _label: Label
var _built := false


func _ready() -> void:
	_ensure()
	_refresh()


func _ensure() -> void:
	if _built:
		return
	_poly = Polygon2D.new()
	_poly.name = "Body"
	_poly.polygon = PackedVector2Array([
		Vector2(0, -24), Vector2(24, 0), Vector2(0, 24), Vector2(-24, 0)
	])
	add_child(_poly)
	_outline = Line2D.new()
	_outline.width = 3.0
	_outline.default_color = Color(1, 1, 0.35)
	_outline.visible = false
	add_child(_outline)
	_label = Label.new()
	_label.position = Vector2(-52, 28)
	_label.add_theme_font_size_override("font_size", 12)
	_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_label.custom_minimum_size = Vector2(104, 0)
	_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_label)
	_built = true


func grid_to_world(grid) -> Vector2:
	var gx := float(grid[0]) if grid is Array else float(grid.x)
	var gy := float(grid[1]) if grid is Array else float(grid.y)
	return Vector2(gx * TILE + TILE * 0.5, gy * TILE + TILE * 0.5)


func bind_cube(state: Dictionary) -> void:
	_ensure()
	cube_id = str(state.get("id", ""))
	hex_id = str(state.get("hex_id", ""))
	hazard_type = str(state.get("type", ""))
	cube_count = int(state.get("cube_count", 1))
	active = bool(state.get("active", true))
	duel_eligible = hazard_type != "pollution" and active
	treatment_eligible = bool(state.get("treatment_eligible", false))
	outbreak_warning = bool(state.get("outbreak_warning", false))
	visible = active
	_refresh()


func set_selected(on: bool) -> void:
	selected_flag = on
	_refresh()


func request_duel() -> void:
	if not duel_eligible or not treatment_eligible:
		return
	duel_requested.emit(cube_id)


func _refresh() -> void:
	if not _built:
		return
	var color := Color(0.85, 0.18, 0.22)
	if hazard_type == "pollution":
		color = Color(0.35, 0.55, 0.25)
	elif hazard_type == "alien":
		color = Color(0.55, 0.35, 0.75)
	if outbreak_warning:
		color = color.lerp(Color(1.0, 0.85, 0.2), 0.35)
	_poly.color = color
	_outline.visible = selected_flag and active
	if _outline.visible:
		var pts := _poly.polygon
		var ring := PackedVector2Array(pts)
		ring.append(pts[0])
		_outline.points = ring
	var eligibility := "treat OK" if treatment_eligible else "treat blocked"
	_label.text = "%s  x%d\n%s" % [hex_id, cube_count, eligibility]
	modulate.a = 1.0 if active else 0.0
