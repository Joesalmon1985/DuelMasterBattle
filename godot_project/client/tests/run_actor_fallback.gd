extends SceneTree

## An unknown sprite key still becomes a real character (never a rectangle), and the geometric stand-in is only the last resort when the
## character library is not installed.
##
## godot --headless --path godot_project --script res://client/tests/run_actor_fallback.gd

const Visual = preload("res://client/world/actor_visual.gd")
const Lib = preload("res://client/characters/character_library.gd")


func _init() -> void:
	var sprite := Sprite2D.new()
	root.add_child(sprite)
	var rel: String = Visual.rel_path("no_such_npc_zzz", "down", 0)
	var path := "res://assets/pixel/" + rel
	if ResourceLoader.exists(path):
		push_error("fixture sprite unexpectedly exists: " + path)
		quit(1)
		return
	var ok := true
	# 1. normal case: the library is present, so an unknown key is a person built from the key
	var used: bool = Visual.apply(sprite, "res://assets/pixel/", "no_such_npc_zzz", "down", 0, "Miner")
	var view = Visual.view_of(sprite)
	ok = ok and not used and view != null and not Visual.is_placeholder(sprite) and sprite.get_node_or_null("fallback_label") == null
	ok = ok and view.look != null and Lib.has_outfit(view.look.outfit)
	var again: bool = Visual.apply(sprite, "res://assets/pixel/", "no_such_npc_zzz", "left", 0, "Miner")
	ok = ok and not again and sprite.get_meta("facing") == "left" and Visual.view_of(sprite) == view
	var key_a: String = view.look.key
	var other := Sprite2D.new()
	root.add_child(other)
	Visual.apply(other, "res://assets/pixel/", "no_such_npc_zzz", "down", 0, "Miner")
	ok = ok and Visual.view_of(other).look.describe() == view.look.describe()  # the same key and label are the same person
	# 2. last resort: no character library at all -> the labelled geometric stand-in, exactly as before
	var saved: Dictionary = Lib._data
	Lib._data = {"version": 0}
	var bare := Sprite2D.new()
	root.add_child(bare)
	var used2: bool = Visual.apply(bare, "res://assets/pixel/", "no_such_npc_zzz", "down", 0, "Miner")
	var label: Label = bare.get_node_or_null("fallback_label")
	ok = ok and used2 and bare.texture != null and label != null and label.visible and label.text == "Miner" and Visual.is_placeholder(bare)
	Lib._data = saved
	if ok:
		print("ACTOR FALLBACK: ALL PASSED")
		quit(0)
	else:
		print("ACTOR FALLBACK: FAILED used=%s view=%s used2=%s" % [used, view, used2])
		quit(1)
