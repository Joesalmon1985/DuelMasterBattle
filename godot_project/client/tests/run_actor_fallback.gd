extends SceneTree

## Missing NPC sprite takes the geometric fallback and does not load a missing file.
##
## godot --headless --path godot_project --script res://client/tests/run_actor_fallback.gd

const Visual = preload("res://client/world/actor_visual.gd")


func _init() -> void:
	var sprite := Sprite2D.new()
	root.add_child(sprite)
	var rel: String = Visual.rel_path("no_such_npc_zzz", "down", 0)
	var path := "res://assets/pixel/" + rel
	if ResourceLoader.exists(path):
		push_error("fixture sprite unexpectedly exists: " + path)
		quit(1)
		return
	var used: bool = Visual.apply(sprite, "res://assets/pixel/", "no_such_npc_zzz", "down", 0, "Miner")
	var label: Label = sprite.get_node_or_null("fallback_label")
	var ok: bool = used and sprite.texture != null and label != null and label.visible and label.text == "Miner"
	ok = ok and Visual.is_placeholder(sprite)
	if ok:
		print("ACTOR FALLBACK: ALL PASSED")
		quit(0)
	else:
		print("ACTOR FALLBACK: FAILED used=%s texture=%s label=%s" % [used, sprite.texture != null, label])
		quit(1)
