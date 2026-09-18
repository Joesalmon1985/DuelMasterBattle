extends "res://client/scenes/g01_shell.gd"

## G04 FX-HAZARD playable shell — isolated save g04_hazard.

const HazardActor = preload("res://client/world/hazard_actor.gd")
const Feedback = preload("res://client/ui/catastrophe_feedback.gd")
const G04_HAZARD_SAVE := "g04_hazard"

var _feedback
var _feedback_label: Label
var _hex_layer: Node2D
var _hex_nodes: Dictionary = {}


func _ready() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-HAZARD")
	OS.set_environment("DMB_SEED", "408")
	OS.set_environment("DMB_SAVE_SLOT", G04_HAZARD_SAVE)
	super()
	_feedback = Feedback.new()
	_hex_layer = Node2D.new()
	_hex_layer.name = "HazardHexes"
	_world_host.add_child(_hex_layer)
	_feedback_label = Label.new()
	_feedback_label.position = Vector2(12, 64)
	_feedback_label.add_theme_font_size_override("font_size", 13)
	_feedback_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_feedback_label.custom_minimum_size = Vector2(320, 0)
	_ui_root.add_child(_feedback_label)
	_set_status("G04 FX-HAZARD — treat three hexes; watch outbreak warnings")
	_prompt.text = "Isolated save g04_hazard. Pollution has no duel. Terminal uses separate slot."


func _process(delta: float) -> void:
	super(delta)
	if _client == null:
		return
	var view: Dictionary = _client.request_view("player", [
		"hazards", "fx_hazard", "player", "clock", "board"
	])
	_feedback.update_from_view(view)
	_feedback_label.text = _feedback.summary_text()
	_refresh_hexes(view)


func _refresh_hexes(view: Dictionary) -> void:
	var fx: Dictionary = view.get("fx_hazard", {})
	var labels: Dictionary = fx.get("hex_labels", {})
	var cat: Dictionary = view.get("hazards", {}).get("catastrophe", {})
	var cubes: Dictionary = cat.get("cubes", {})
	var i := 0
	for cube_id in cubes.keys():
		var cube: Dictionary = cubes[cube_id]
		if not bool(cube.get("active", true)):
			continue
		if not _hex_nodes.has(cube_id):
			var actor := Node2D.new()
			actor.set_script(HazardActor)
			_hex_layer.add_child(actor)
			_hex_nodes[cube_id] = actor
		var node = _hex_nodes[cube_id]
		var hid := str(cube.get("hex_id", ""))
		cube["treatment_eligible"] = labels.has(hid)
		cube["outbreak_warning"] = int(cat.get("era_outbreaks", 0)) >= int(fx.get("outbreak_warning_at", 7))
		node.bind_cube(cube)
		node.position = Vector2(80.0 + float(i) * 70.0, 180.0)
		i += 1
