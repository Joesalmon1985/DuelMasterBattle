extends RefCounted
class_name DmbSettings

## Accessibility / audio persistence for MVP (T110). Pause settings stay invariant.

const SAVE_PATH := "user://dmb_settings.json"

var master_volume := 1.0
var music_volume := 0.8
var world_volume := 0.9
var ui_volume := 1.0
var muted := false
var reduce_motion := false
var label_scale := 1.0
var colourblind_cues := true
var hints_enabled := true


func load_settings() -> void:
	if not FileAccess.file_exists(SAVE_PATH):
		return
	var f := FileAccess.open(SAVE_PATH, FileAccess.READ)
	var data = JSON.parse_string(f.get_as_text())
	if typeof(data) != TYPE_DICTIONARY:
		return
	master_volume = float(data.get("master_volume", master_volume))
	music_volume = float(data.get("music_volume", music_volume))
	world_volume = float(data.get("world_volume", world_volume))
	ui_volume = float(data.get("ui_volume", ui_volume))
	muted = bool(data.get("muted", muted))
	reduce_motion = bool(data.get("reduce_motion", reduce_motion))
	label_scale = float(data.get("label_scale", label_scale))
	colourblind_cues = bool(data.get("colourblind_cues", colourblind_cues))
	hints_enabled = bool(data.get("hints_enabled", hints_enabled))


func save_settings() -> void:
	var payload := {
		"master_volume": master_volume,
		"music_volume": music_volume,
		"world_volume": world_volume,
		"ui_volume": ui_volume,
		"muted": muted,
		"reduce_motion": reduce_motion,
		"label_scale": label_scale,
		"colourblind_cues": colourblind_cues,
		"hints_enabled": hints_enabled,
		"min_touch_px": 48,
	}
	var f := FileAccess.open(SAVE_PATH, FileAccess.WRITE)
	f.store_string(JSON.stringify(payload))


func effective_volume(bus: String) -> float:
	if muted:
		return 0.0
	match bus:
		"music":
			return master_volume * music_volume
		"world":
			return master_volume * world_volume
		"ui":
			return master_volume * ui_volume
		_:
			return master_volume
