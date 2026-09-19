extends SceneTree

## T087 inventory UI binder.
## godot --headless --path godot_project --script res://client/tests/run_t087_inventory.gd

const Inv = preload("res://client/ui/inventory.gd")

var _failures: Array = []


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	await process_frame
	var ui = Inv.new()
	ui.apply_player_items([{"id": "item:1", "equipped_slot": "focus"}])
	ui.apply_ground_items([{"id": "item:2"}])
	_assert(ui.has_item("item:1"), "player item missing")
	_assert(ui.has_item("item:2"), "ground item missing")
	_assert(ui.equipped_slot("item:1") == "focus", "focus slot")
	_assert(ui.player_ids() == ["item:1"], "player ids")
	if _failures.is_empty():
		print("T087_INVENTORY_OK")
		quit(0)
	else:
		for f in _failures:
			push_error(str(f))
		print("T087_INVENTORY_FAIL")
		quit(1)


func _assert(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)
