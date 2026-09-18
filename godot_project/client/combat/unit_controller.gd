extends Node2D
class_name DmbUnitController

## Binds one sprite/controller to a persistent unit ID (C07 / T063).

var unit_id: String = ""
var faction_id: String = ""
var archetype: String = ""
var max_health: int = 1
var current_health: int = 1
var alive: bool = true
var attack_cue: bool = false

@onready var _body: ColorRect = $Body if has_node("Body") else null
@onready var _label: Label = $Label if has_node("Label") else null


func bind_unit(state: Dictionary) -> void:
	unit_id = str(state.get("id", ""))
	faction_id = str(state.get("faction_id", ""))
	archetype = str(state.get("archetype", state.get("definition_id", "")))
	max_health = int(state.get("max_health", 1))
	current_health = int(state.get("current_health", max_health))
	alive = bool(state.get("alive", true))
	var pos = state.get("position", [0, 0])
	if pos is Array and pos.size() >= 2:
		position = Vector2(float(pos[0]) * 32.0, float(pos[1]) * 32.0)
	_refresh_visual()


func apply_checkpoint(state: Dictionary) -> void:
	if str(state.get("id", "")) != unit_id and unit_id != "":
		return
	current_health = int(state.get("current_health", current_health))
	alive = bool(state.get("alive", true))
	var pos = state.get("position", null)
	if pos is Array and pos.size() >= 2:
		position = Vector2(float(pos[0]) * 32.0, float(pos[1]) * 32.0)
	attack_cue = false
	_refresh_visual()


func flash_attack() -> void:
	attack_cue = true
	_refresh_visual()


func _refresh_visual() -> void:
	if _label:
		_label.text = "%s HP %s/%s" % [archetype if archetype != "" else unit_id, current_health, max_health]
		_label.visible = alive
	if _body:
		_body.modulate = Color(0.35, 0.75, 0.4) if alive else Color(0.25, 0.25, 0.25)
		if attack_cue:
			_body.modulate = Color(1.0, 0.55, 0.2)
