extends SceneTree
## T162 gallery smoke — instantiate badges for every registry entry (headless).

const REGISTRY := "res://content/source/presentation/semantic_visuals.json"


func _init() -> void:
	var text := FileAccess.get_file_as_string(REGISTRY)
	var data = JSON.parse_string(text)
	assert(typeof(data) == TYPE_DICTIONARY, "registry json")
	var entries: Array = data.get("entries", [])
	assert(entries.size() > 0, "registry empty")
	var root := Control.new()
	root.name = "GalleryRoot"
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var grid := GridContainer.new()
	grid.columns = 8
	root.add_child(grid)
	var seen := {}
	for row in entries:
		var sid := str(row.get("semantic_id", ""))
		assert(sid != "", "missing semantic_id")
		assert(not seen.has(sid), "duplicate %s" % sid)
		seen[sid] = true
		assert(not bool(row.get("anonymous", false)), "anonymous %s" % sid)
		var label := str(row.get("label", ""))
		var abbrev := str(row.get("abbrev", ""))
		assert(label != "" or abbrev != "", "unreadable %s" % sid)
		var badge := DmbSemanticPlaceholder.make_badge(sid, Vector2(56, 56), row)
		assert(badge.get_meta("semantic_id") == sid)
		grid.add_child(badge)
	print("G11_GALLERY_OK entries=%d" % entries.size())
	quit(0)
