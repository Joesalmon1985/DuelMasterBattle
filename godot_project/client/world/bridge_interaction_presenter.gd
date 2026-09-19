extends Node
class_name DmbBridgeInteractionPresenter

## Owns WorldInteractionLabel instances for migrated shells.
## Drives observation and Talk from filtered bridge payloads — one foreground panel.

const WIL = preload("res://client/world/world_interaction_label.gd")

signal talk_line_finished(entity_id: String)

var _ui_root: Control
var _camera: Camera2D
var _labels: Dictionary = {}  # entity_id -> WorldInteractionLabel
var _active_id: String = ""
var _cmd: Callable = Callable()


func setup(ui_root: Control, camera: Camera2D = null, cmd: Callable = Callable()) -> void:
	_ui_root = ui_root
	_camera = camera
	_cmd = cmd


func show_observation(entity_id: String, anchor: Node2D, view: Dictionary, semantic: Dictionary = {}) -> void:
	var label = _ensure_label(entity_id, anchor, semantic)
	label.set_bridge_view(view)
	var desc := str(view.get("description", view.get("label", view.get("name", "Observed"))))
	if label.has_method("present_line"):
		label.present_line(desc)
	elif label.has_method("open_observation"):
		label.open_observation()
	_active_id = entity_id


func begin_talk(entity_id: String, anchor: Node2D, speech_lines: Array, responses: Array = [], semantic: Dictionary = {}) -> void:
	var label = _ensure_label(entity_id, anchor, semantic)
	_active_id = entity_id
	if label.has_method("begin_speech"):
		label.begin_speech(speech_lines, responses)
	elif speech_lines.size() > 0 and label.has_method("present_line"):
		label.present_line(str(speech_lines[0]))


func view_name(semantic: Dictionary) -> String:
	return str(semantic.get("name", semantic.get("label", "")))


func notify_player_moved() -> void:
	for id in _labels.keys():
		var label = _labels[id]
		if is_instance_valid(label) and label.has_method("notify_player_moved"):
			label.notify_player_moved()


func clear_entity(entity_id: String) -> void:
	if _labels.has(entity_id):
		var label = _labels[entity_id]
		if is_instance_valid(label):
			label.queue_free()
		_labels.erase(entity_id)
	if _active_id == entity_id:
		_active_id = ""


func _ensure_label(entity_id: String, anchor: Node2D, semantic: Dictionary):
	if _labels.has(entity_id) and is_instance_valid(_labels[entity_id]):
		var existing = _labels[entity_id]
		if existing.has_method("set_bridge_view") and not semantic.is_empty():
			pass
		return existing
	var label := Control.new()
	label.set_script(WIL)
	_ui_root.add_child(label)
	var cam := _camera
	if cam == null and _ui_root.get_viewport() != null:
		cam = _ui_root.get_viewport().get_camera_2d()
	if label.has_method("bind_bridge"):
		label.bind_bridge(semantic, entity_id, anchor, cam, Vector2(0, -48))
	_labels[entity_id] = label
	return label
