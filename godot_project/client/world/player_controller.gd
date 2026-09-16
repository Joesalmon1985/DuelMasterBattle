extends Node
class_name DmbPlayerController

## One-pointer local movement; strategic exits wait for acknowledgement.

signal move_local(delta: Vector2)
signal exit_acknowledged(node_id: String)

var speculative_node: String = ""
var confirmed_node: String = "node:1"
var _pending_exit := false


func pointer_drag(delta: Vector2) -> void:
	move_local.emit(delta)


func request_exit(to_node: String) -> void:
	if _pending_exit:
		return
	_pending_exit = true
	# Do not mutate confirmed destination until acknowledgement.
	speculative_node = ""


func acknowledge_exit(to_node: String) -> void:
	confirmed_node = to_node
	speculative_node = ""
	_pending_exit = false
	exit_acknowledged.emit(to_node)


func reject_exit() -> void:
	speculative_node = ""
	_pending_exit = false
