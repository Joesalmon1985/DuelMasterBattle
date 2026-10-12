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
	# Large filled diamond — readable against terrain at typical zoom.
	_poly.polygon = PackedVector2Array([
		Vector2(0, -28), Vector2(28, 0), Vector2(0, 28), Vector2(-28, 0)
	])
	add_child(_poly)
	_outline = Line2D.new()
	_outline.width = 4.0
	_outline.default_color = Color(1.0, 0.95, 0.55, 1.0)
	_outline.visible = true
	add_child(_outline)
	_label = Label.new()
	_label.position = Vector2(-52, 30)
	_label.add_theme_font_size_override("font_size", 13)
	_label.add_theme_color_override("font_color", Color(1, 0.92, 0.85))
	_label.add_theme_color_override("font_outline_color", Color(0, 0, 0, 1))
	_label.add_theme_constant_override("outline_size", 4)
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
	# Distinct filled colour per hazard type; demon stays vivid red.
	var color := Color(0.92, 0.12, 0.14)
	var outline := Color(1.0, 0.95, 0.45, 1.0)
	var type_label := "Demon"
	if hazard_type == "pollution":
		color = Color(0.28, 0.62, 0.22)
		outline = Color(0.85, 1.0, 0.55, 1.0)
		type_label = "Pollution"
	elif hazard_type == "alien":
		color = Color(0.58, 0.28, 0.82)
		outline = Color(0.95, 0.75, 1.0, 1.0)
		type_label = "Alien"
	elif hazard_type != "" and hazard_type != "demon":
		type_label = hazard_type.capitalize()
	if outbreak_warning:
		color = color.lerp(Color(1.0, 0.85, 0.2), 0.35)
	_poly.color = color
	# Always draw a contrasting ring so the body reads against terrain/zoom.
	_outline.visible = active
	_outline.default_color = Color(1.0, 1.0, 0.2, 1.0) if selected_flag else outline
	_outline.width = 5.0 if selected_flag else 4.0
	var pts := _poly.polygon
	var ring := PackedVector2Array(pts)
	ring.append(pts[0])
	_outline.points = ring
	# Player-facing label only — no diagnostic "treat OK" strings.
	_label.text = type_label if cube_count <= 1 else "%s ×%d" % [type_label, cube_count]
	z_index = 12
	modulate.a = 1.0 if active else 0.0
