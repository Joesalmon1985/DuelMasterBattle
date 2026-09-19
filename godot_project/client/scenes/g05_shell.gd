extends Control

## G05 FX-VILLAGE playable shell — Python sidecar owns world state.

const SidecarLauncher = preload("res://client/bridge/sidecar_launcher.gd")
const WorldClient = preload("res://client/bridge/world_client.gd")
const Migrated = preload("res://client/core/migrated_runtime.gd")

var _launcher
var _client
var _label: Label
var _status: Label
var _boot_done := false
var _project_root := ""


func _ready() -> void:
	Migrated.enable()
	OS.set_environment("DMB_FIXTURE", "FX-VILLAGE")
	if OS.get_environment("DMB_SEED") == "":
		OS.set_environment("DMB_SEED", "505")
	set_anchors_and_offsets_preset(PRESET_FULL_RECT)
	_label = Label.new()
	_label.set_anchors_preset(PRESET_TOP_WIDE)
	_label.offset_left = 16
	_label.offset_top = 16
	_label.offset_right = -16
	_label.offset_bottom = 160
	_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_label.text = "G05 FX-VILLAGE — starting Python sidecar…"
	add_child(_label)
	_status = Label.new()
	_status.set_anchors_preset(PRESET_BOTTOM_WIDE)
	_status.offset_left = 16
	_status.offset_top = -96
	_status.offset_right = -16
	_status.offset_bottom = -16
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(_status)
	_launcher = SidecarLauncher.new()
	add_child(_launcher)
	_client = WorldClient.new()
	add_child(_client)
	_project_root = ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
	if _project_root.ends_with("godot_project"):
		_project_root = _project_root.get_base_dir()
	call_deferred("_boot")


func _boot() -> void:
	var started: Dictionary = _launcher.start(_project_root)
	if not started.get("ok", false):
		_label.text = "G05 sidecar failed — no Godot sim fallback"
		_status.text = str(started.get("error", "spawn_failed"))
		return
	if not _client.connect_sidecar(str(started["host"]), int(started["port"]), str(started["token"])):
		_label.text = "G05 handshake failed"
		_status.text = "bridge connect rejected"
		return
	var seed := int(OS.get_environment("DMB_SEED")) if OS.get_environment("DMB_SEED").is_valid_int() else 505
	_label.text = (
		"G05 FX-VILLAGE seed=%d — Python owns durable world state.\n"
		+ "Find Mara at the quiet factory yard. Infer why work stopped.\n"
		+ "Try one solution save, then a fresh save for the other route.\n"
		+ "Optional hints: Pack/.../tracking/gates/G05/optional_hints.md (read after trying)."
	) % seed
	_status.text = "Reset/slots: tracking/gates/G05/reset.md · Scenarios under tracking/gates/G05/scenarios/"
	_boot_done = true


func is_booted() -> bool:
	return _boot_done


func _exit_tree() -> void:
	if _launcher != null:
		_launcher.stop()
