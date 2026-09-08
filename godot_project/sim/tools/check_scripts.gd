extends SceneTree

## Loads every .gd under res:// and fails if any has a parse error.
## godot --headless --path godot_project --script res://sim/tools/check_scripts.gd

var _bad: Array = []


func _init() -> void:
	_walk("res://")
	if _bad.is_empty():
		print("SCRIPT CHECK: all scripts parse")
		quit(0)
	else:
		print("SCRIPT CHECK: FAILED")
		for b in _bad:
			print("  - %s" % b)
		quit(1)


func _walk(path: String) -> void:
	var dir := DirAccess.open(path)
	if dir == null:
		return
	dir.list_dir_begin()
	var name := dir.get_next()
	while name != "":
		var full := path.path_join(name)
		if dir.current_is_dir():
			if not name.begins_with("."):
				_walk(full)
		elif name.ends_with(".gd"):
			var scr = load(full)
			if scr == null or not (scr as GDScript).can_instantiate() and not _is_static_only(scr):
				_bad.append(full)
		name = dir.get_next()
	dir.list_dir_end()


func _is_static_only(scr) -> bool:
	# Scripts extending SceneTree (tools) can't be instantiated here but do parse.
	return scr is GDScript and scr.get_instance_base_type() == "SceneTree"
