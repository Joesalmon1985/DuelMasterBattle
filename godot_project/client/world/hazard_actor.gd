extends Node2D
class_name DmbHazardActor

## Visible hazard manifestation for eligible cube duels (C08/C10).
## Not a win button — starts a real playable duel lease.

var cube_id: String = ""
var hex_id: String = ""
var hazard_type: String = ""
var duel_eligible: bool = false
var treatment_eligible: bool = false
var outbreak_warning: bool = false

signal duel_requested(cube_id)


func bind_cube(state: Dictionary) -> void:
	cube_id = str(state.get("id", ""))
	hex_id = str(state.get("hex_id", ""))
	hazard_type = str(state.get("type", ""))
	duel_eligible = hazard_type != "pollution" and bool(state.get("active", true))
	treatment_eligible = bool(state.get("treatment_eligible", false))
	outbreak_warning = bool(state.get("outbreak_warning", false))
	queue_redraw()


func request_duel() -> void:
	if not duel_eligible:
		return
	duel_requested.emit(cube_id)


func _draw() -> void:
	var color := Color(0.75, 0.2, 0.25)
	if hazard_type == "pollution":
		color = Color(0.35, 0.55, 0.25)
	elif hazard_type == "alien":
		color = Color(0.55, 0.35, 0.75)
	draw_circle(Vector2.ZERO, 14.0, color)
	if outbreak_warning:
		draw_arc(Vector2.ZERO, 20.0, 0.0, TAU, 24, Color(1, 0.8, 0.2), 2.0)
