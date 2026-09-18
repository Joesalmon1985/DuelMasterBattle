extends RefCounted
class_name DmbCatastropheFeedback

## Readable catastrophe cues for G04 (production stop / treatment / outbreak).

var outbreak_count: int = 0
var outbreak_threshold: int = 8
var blocked_sources: Array = []
var treatable_hexes: Array = []
var terminal: bool = false


func update_from_view(view: Dictionary) -> void:
	var fx: Dictionary = view.get("fx_hazard", {})
	var cat: Dictionary = view.get("hazards", {}).get("catastrophe", {})
	if cat.is_empty():
		cat = view.get("catastrophe", {})
	outbreak_count = int(cat.get("era_outbreaks", 0))
	outbreak_threshold = 8
	terminal = bool(view.get("clock", {}).get("terminal", false))
	blocked_sources.clear()
	treatable_hexes.clear()
	for hid in fx.get("hex_labels", {}).keys():
		treatable_hexes.append(str(hid))
	for cube_variant in (cat.get("cubes", {}) as Dictionary).values():
		var cube: Dictionary = cube_variant
		if bool(cube.get("active", true)):
			blocked_sources.append("%s (%s)" % [cube.get("hex_id", "?"), cube.get("type", "?")])


func summary_text() -> String:
	var lines: PackedStringArray = []
	lines.append("Outbreak %d / %d" % [outbreak_count, outbreak_threshold])
	if outbreak_count >= 7:
		lines.append("WARNING: near terminal cascade")
	if blocked_sources.size() > 0:
		lines.append("Sources stopped: %s" % ", ".join(blocked_sources))
	else:
		lines.append("No source blockage")
	if treatable_hexes.size() > 0:
		lines.append("Treatable hexes: %s" % ", ".join(treatable_hexes))
	if terminal:
		lines.append("TERMINAL — return to menu")
	return "\n".join(lines)
