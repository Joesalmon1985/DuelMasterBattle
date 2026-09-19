extends RefCounted
class_name DmbContextActions

## Shared input router: UI choice vs semantic target vs ground movement.
## Single-pointer Travel/Wait/Observe plus formal choice emission.

signal travel_requested(to_node: String)
signal wait_requested(press_id: String)
signal observe_requested(entity_id: String)
signal choice_requested(entity_id: String, action_id: String, payload: Dictionary)
signal choice_cancelled(entity_id: String)

const INTERACTION_RANGE_TILES := 2.0

var _wait_held := false
var _pointer_consumed := false
var _formal_open := false


func press_travel(to_node: String) -> void:
	if _formal_open:
		choice_cancelled.emit("")
		_formal_open = false
	travel_requested.emit(to_node)


func press_wait(press_id: String) -> void:
	if _wait_held:
		return
	_wait_held = true
	wait_requested.emit(press_id)


func release_wait() -> void:
	_wait_held = false


func press_observe(entity_id: String) -> void:
	observe_requested.emit(entity_id)


func begin_formal_choice(entity_id: String) -> void:
	_formal_open = true
	_pointer_consumed = true


func emit_choice(entity_id: String, action_id: String, payload: Dictionary = {}) -> void:
	choice_requested.emit(entity_id, action_id, payload)
	_formal_open = false
	_pointer_consumed = true


func cancel_choice(entity_id: String = "") -> void:
	if _formal_open:
		choice_cancelled.emit(entity_id)
	_formal_open = false
	_pointer_consumed = true


func is_formal_open() -> bool:
	return _formal_open


func consume_pointer() -> void:
	## Mark this press as used by a target/button so ground-move must not also fire.
	_pointer_consumed = true


func pointer_was_consumed() -> bool:
	return _pointer_consumed


func clear_pointer_consumption() -> void:
	_pointer_consumed = false


func route_world_click(nearby: bool, entity_id: String) -> String:
	## Returns "observe", "choice", or "" when nothing applies.
	consume_pointer()
	if entity_id == "":
		return ""
	if nearby:
		begin_formal_choice(entity_id)
		return "choice"
	press_observe(entity_id)
	return "observe"
