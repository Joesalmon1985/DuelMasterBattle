extends SceneTree

## T090 dungeon area import smoke.
## godot --headless --path godot_project --script res://client/tests/run_t090_dungeon.gd

func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	await process_frame
	var packed := load("res://client/adventure/dungeon_area.tscn")
	if packed == null:
		push_error("missing dungeon_area.tscn")
		print("T090_DUNGEON_FAIL")
		quit(1)
		return
	var scene = packed.instantiate()
	root.add_child(scene)
	await process_frame
	if scene.get_node_or_null("PuzzlePresenter") == null:
		push_error("PuzzlePresenter missing")
		print("T090_DUNGEON_FAIL")
		quit(1)
		return
	if scene.get_node_or_null("Rooms/Chamber") == null:
		push_error("Chamber marker missing")
		print("T090_DUNGEON_FAIL")
		quit(1)
		return
	print("T090_DUNGEON_OK")
	quit(0)
