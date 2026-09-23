extends RefCounted
class_name DmbPresentationMode

## Central presentation visibility owner for G05 integrated shell.
## Simulation/pause ownership stays with Python + shell acquire_pause/release_pause.
## This only toggles Godot presentation roots so Ward Duel is a clean screen.

enum Mode { WORLD, LOCAL_BATTLE, WARD_DUEL, MODAL }

const MODE_NAMES := {
	Mode.WORLD: "WORLD",
	Mode.LOCAL_BATTLE: "LOCAL_BATTLE",
	Mode.WARD_DUEL: "WARD_DUEL",
	Mode.MODAL: "MODAL",
}

## World-space / chrome roots that must not leak into Ward Duel.
const FORBIDDEN_DURING_WARD_DUEL := [
	"Overworld",
	"ShellUILayer",
	"StatusLabel",
	"TimeHud",
	"WorkerController",
	"WorldLayerPresenters",
	"LocalBattleHost",
]

var mode: int = Mode.WORLD
var _world_root: Node = null
var _ui_layer: Node = null
var _chrome: Array = []
var _duel_layer: CanvasLayer = null
var _duel_host: Control = null
var _saved_world_process: int = Node.PROCESS_MODE_INHERIT
var _apply_count := 0


func bind(
	world_root: Node,
	ui_layer: Node,
	chrome: Array,
	duel_layer: CanvasLayer,
	duel_host: Control,
) -> void:
	_world_root = world_root
	_ui_layer = ui_layer
	_chrome = chrome
	_duel_layer = duel_layer
	_duel_host = duel_host


func set_world_root(world_root: Node) -> void:
	_world_root = world_root


func current_name() -> String:
	return str(MODE_NAMES.get(mode, "UNKNOWN"))


func is_ward_duel() -> bool:
	return mode == Mode.WARD_DUEL


func set_mode(next_mode: int) -> void:
	if next_mode == mode and _apply_count > 0:
		_apply()
		return
	mode = next_mode
	_apply()


func _apply() -> void:
	_apply_count += 1
	var ward := mode == Mode.WARD_DUEL
	_set_world_presentation(not ward)
	_set_chrome_visible(not ward and mode != Mode.MODAL)
	if _ui_layer != null and is_instance_valid(_ui_layer):
		# Modals live on ui_layer; keep it for MODAL, hide for Ward Duel.
		_ui_layer.visible = not ward
	if _duel_layer != null and is_instance_valid(_duel_layer):
		_duel_layer.visible = ward
	if _duel_host != null and is_instance_valid(_duel_host):
		_duel_host.visible = ward
		_duel_host.mouse_filter = Control.MOUSE_FILTER_STOP if ward else Control.MOUSE_FILTER_IGNORE
		if ward:
			_duel_host.move_to_front()


func _set_world_presentation(show: bool) -> void:
	if _world_root == null or not is_instance_valid(_world_root):
		return
	if show:
		_world_root.visible = true
		_world_root.process_mode = _saved_world_process
	else:
		_saved_world_process = _world_root.process_mode
		_world_root.visible = false
		# Block input + _process on overworld / local battle / workers / labels.
		_world_root.process_mode = Node.PROCESS_MODE_DISABLED


func _set_chrome_visible(show: bool) -> void:
	for node in _chrome:
		if node != null and is_instance_valid(node):
			node.visible = show


func assert_ward_duel_clean() -> Dictionary:
	## Structural check used by regression tests (not aesthetic judgement).
	var leaks: Array = []
	if _world_root != null and is_instance_valid(_world_root):
		if _world_root.visible:
			leaks.append("Overworld.visible")
		if _world_root.process_mode != Node.PROCESS_MODE_DISABLED:
			leaks.append("Overworld.process_mode")
	if _ui_layer != null and is_instance_valid(_ui_layer) and _ui_layer.visible:
		leaks.append("ShellUILayer.visible")
	for node in _chrome:
		if node != null and is_instance_valid(node) and node.visible:
			leaks.append("%s.visible" % node.name)
	if _duel_host == null or not is_instance_valid(_duel_host) or not _duel_host.visible:
		leaks.append("DuelHost.missing_or_hidden")
	if _duel_layer != null and is_instance_valid(_duel_layer) and not _duel_layer.visible:
		leaks.append("DuelLayer.hidden")
	return {
		"ok": leaks.is_empty(),
		"mode": current_name(),
		"leaks": leaks,
		"apply_count": _apply_count,
	}


func assert_world_restored() -> Dictionary:
	var issues: Array = []
	if mode != Mode.WORLD and mode != Mode.LOCAL_BATTLE and mode != Mode.MODAL:
		issues.append("mode=%s" % current_name())
	if _world_root != null and is_instance_valid(_world_root):
		if not _world_root.visible:
			issues.append("Overworld.hidden")
		if _world_root.process_mode == Node.PROCESS_MODE_DISABLED:
			issues.append("Overworld.still_disabled")
	if _duel_host != null and is_instance_valid(_duel_host) and _duel_host.visible:
		issues.append("DuelHost.still_visible")
	if _duel_layer != null and is_instance_valid(_duel_layer) and _duel_layer.visible:
		issues.append("DuelLayer.still_visible")
	return {
		"ok": issues.is_empty(),
		"mode": current_name(),
		"issues": issues,
		"apply_count": _apply_count,
	}
