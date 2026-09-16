extends SceneTree

## Headless check: local area controller does not speculate destination.

const Migrated = preload("res://client/core/migrated_runtime.gd")

func _init() -> void:
	Migrated.enable()
	var controller = load("res://client/world/player_controller.gd").new()
	controller.request_exit("node:2")
	if controller.confirmed_node != "node:1":
		push_error("speculative destination mutation")
		quit(1)
		return
	if controller.speculative_node != "":
		push_error("speculative node set before ack")
		quit(1)
		return
	controller.acknowledge_exit("node:2")
	if controller.confirmed_node != "node:2":
		push_error("ack failed")
		quit(1)
		return
	var actions = load("res://client/ui/context_actions.gd").new()
	var waits := []
	actions.wait_requested.connect(func(press_id): waits.append(press_id))
	actions.press_wait("press-1")
	actions.press_wait("press-1")
	if waits != ["press-1"]:
		push_error("held wait must send once")
		quit(1)
		return
	if not Migrated.active:
		push_error("migrated runtime inactive")
		quit(1)
		return
	print("G01_LOCAL_OK")
	quit(0)
