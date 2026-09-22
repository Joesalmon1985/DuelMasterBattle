extends CanvasLayer
class_name DmbEraTransitionPresenter

## Presentation-only Prehistoric → Historic sequence (~4s).
## Mechanics are already committed before this runs. Skip never re-converts.

signal finished(skipped: bool)

const VisualLanguage = preload("res://client/world/visual_language.gd")

var _overlay: ColorRect
var _banner: Label
var _detail: Label
var _skip_btn: Button
var _tween: Tween
var _playing := false
var _skipped := false
var _reduced_motion := false
var _payload: Dictionary = {}


func _ready() -> void:
	layer = 80
	visible = false
	process_mode = Node.PROCESS_MODE_ALWAYS
	_overlay = ColorRect.new()
	_overlay.set_anchors_preset(Control.PRESET_FULL_RECT)
	_overlay.color = Color(0.02, 0.02, 0.05, 0.0)
	_overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(_overlay)
	_banner = Label.new()
	_banner.set_anchors_preset(Control.PRESET_CENTER_TOP)
	_banner.offset_top = 48
	_banner.offset_left = -280
	_banner.offset_right = 280
	_banner.offset_bottom = 100
	_banner.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_banner.add_theme_font_size_override("font_size", 28)
	_banner.text = "Era change"
	add_child(_banner)
	_detail = Label.new()
	_detail.set_anchors_preset(Control.PRESET_CENTER)
	_detail.offset_left = -320
	_detail.offset_right = 320
	_detail.offset_top = -20
	_detail.offset_bottom = 80
	_detail.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_detail.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_detail.add_theme_font_size_override("font_size", 16)
	add_child(_detail)
	_skip_btn = Button.new()
	_skip_btn.text = "Skip"
	_skip_btn.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	_skip_btn.offset_left = -120
	_skip_btn.offset_top = -64
	_skip_btn.offset_right = -24
	_skip_btn.offset_bottom = -24
	_skip_btn.pressed.connect(skip)
	add_child(_skip_btn)
	_reduced_motion = bool(ProjectSettings.get_setting("dmb/reduced_motion", false)) \
		or OS.get_environment("DMB_REDUCED_MOTION") == "1"


func play(payload: Dictionary) -> void:
	## payload: presentation_era_transition from Python (already committed).
	if _playing:
		return
	_payload = payload
	if not bool(payload.get("committed", false)):
		# Never animate an uncommitted plan.
		finished.emit(false)
		return
	_playing = true
	_skipped = false
	visible = true
	_banner.text = "Prehistoric → Historic"
	var cores: Array = payload.get("core_settlement_ids", [])
	var legacy: Array = payload.get("legacy_settlement_ids", [])
	var collapsed: Array = payload.get("collapse_faction_ids", [])
	_detail.text = "Cores upgrade · Legacy sites remain · Collapsed sites become ruins"
	if _reduced_motion:
		_overlay.color = Color(0.05, 0.05, 0.1, 0.55)
		_detail.text = "Historic era committed.\nCores: %s\nLegacy: %s\nRuins from: %s" % [
			_join_ids(cores), _join_ids(legacy), _join_ids(collapsed)
		]
		await get_tree().create_timer(0.6).timeout
		_finish(false)
		return
	_overlay.color = Color(0.02, 0.02, 0.05, 0.0)
	_tween = create_tween()
	_tween.set_parallel(false)
	# Stage 1: freeze/dim (~0.6s)
	_detail.text = "The age turns…"
	_tween.tween_property(_overlay, "color", Color(0.02, 0.02, 0.08, 0.55), 0.6)
	# Stage 2: collapse → ruins (~1.0s)
	_tween.tween_callback(_stage_ruins.bind(collapsed))
	_tween.tween_interval(1.0)
	# Stage 3: cores transform (~1.2s)
	_tween.tween_callback(_stage_cores.bind(cores))
	_tween.tween_interval(1.2)
	# Stage 4: legacy labels (~0.8s)
	_tween.tween_callback(_stage_legacy.bind(legacy))
	_tween.tween_interval(0.8)
	# Stage 5: resume (~0.4s)
	_tween.tween_callback(_stage_resume)
	_tween.tween_property(_overlay, "color", Color(0.02, 0.02, 0.05, 0.0), 0.4)
	_tween.tween_callback(_finish.bind(false))


func _join_ids(ids: Array) -> String:
	var parts: PackedStringArray = PackedStringArray()
	for id in ids:
		parts.append(str(id))
	return ", ".join(parts)


func _stage_ruins(collapsed: Array) -> void:
	_detail.text = "Collapsed settlements become ruins"
	if not collapsed.is_empty():
		_detail.text = "Ruins form where %s fell" % _join_ids(collapsed)


func _stage_cores(cores: Array) -> void:
	_banner.text = "Historic cores"
	_detail.text = "Surviving centres reshape for the new era"
	if not cores.is_empty():
		_detail.text = "Historic core(s): %s" % _join_ids(cores)


func _stage_legacy(legacy: Array) -> void:
	_banner.text = "Legacy Prehistoric sites"
	if legacy.is_empty():
		_detail.text = "No legacy sites retained"
	else:
		_detail.text = "Still Prehistoric: %s" % _join_ids(legacy)


func _stage_resume() -> void:
	_banner.text = "Historic age begins"
	_detail.text = "Same land. New era."


func skip() -> void:
	if not _playing:
		return
	_skipped = true
	if _tween != null:
		_tween.kill()
	_finish(true)


func _finish(was_skip: bool) -> void:
	_playing = false
	visible = false
	finished.emit(was_skip or _skipped)


func is_playing() -> bool:
	return _playing
