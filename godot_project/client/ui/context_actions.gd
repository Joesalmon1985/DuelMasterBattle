extends RefCounted
class_name DmbContextActions

## Single-pointer Travel/Wait exposure for the G01 local area.

signal travel_requested(to_node: String)
signal wait_requested(press_id: String)
signal observe_requested(entity_id: String)

var _wait_held := false


func press_travel(to_node: String) -> void:
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
