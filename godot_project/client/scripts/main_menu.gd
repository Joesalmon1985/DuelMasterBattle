extends Control
const _VT = preload("res://client/scripts/visual_theme.gd")

const _Encounters = preload("res://sim/encounters.gd")
const _DifficultyProfiles = preload("res://sim/difficulty_profiles.gd")
const _SaveData = preload("res://client/scripts/save_data.gd")

const HOW_TO_PLAY_TEXT := (
	"Choose difficulty and encounter. Set your hidden ward, then cast attacks in real time. "
	+ "Fracture = exact match. Echo = wrong locus. Fade = miss. Feedback is aggregate only."
)
const FEEDBACK_HELP := (
	"Each attack tells you how many essences were exactly right, "
	+ "how many were displaced, and how many faded — never which locus caused each result."
)

@onready var difficulty_option: OptionButton = $Margin/VBox/DifficultyRow/DifficultyOption
@onready var encounter_option: OptionButton = $Margin/VBox/EncounterRow/EncounterOption
@onready var encounter_detail: Label = $Margin/VBox/EncounterDetail
@onready var start_duel_btn: Button = $Margin/VBox/StartDuelButton
@onready var how_to_play_btn: Button = $Margin/VBox/HowToPlayButton
@onready var settings_btn: Button = $Margin/VBox/SettingsButton
@onready var help_panel: PanelContainer = $Margin/VBox/HelpPanel
@onready var help_label: Label = $Margin/VBox/HelpPanel/HelpLabel
@onready var settings_panel: PanelContainer = $Margin/VBox/SettingsPanel
@onready var title_label: Label = $Margin/VBox/TitleLabel
@onready var background: ColorRect = $Background

var _encounters: Array = []
var _difficulties: Array = []


func _ready() -> void:
	_apply_theme()
	_difficulties = _DifficultyProfiles.all_profiles()
	difficulty_option.clear()
	for i in range(_difficulties.size()):
		var d = _difficulties[i]
		difficulty_option.add_item(d.display_name, i)
		if d.id == _SaveData.get_last_difficulty():
			difficulty_option.select(i)
	_encounters = _Encounters.all_encounters()
	encounter_option.clear()
	for i in range(_encounters.size()):
		var rs: DmbDuelRuleset = _encounters[i]
		encounter_option.add_item(rs.display_name, i)
		if rs.id == _Encounters.DEFAULT_ENCOUNTER_ID:
			encounter_option.select(i)
	_build_settings_panel()
	_update_detail()
	difficulty_option.item_selected.connect(func(_i): _update_detail())
	encounter_option.item_selected.connect(_on_encounter_selected)
	start_duel_btn.pressed.connect(_on_start_duel)
	how_to_play_btn.pressed.connect(_on_how_to_play)
	settings_btn.pressed.connect(_on_settings)


func _apply_theme() -> void:
	background.color = _VT.COLOR_BG_DEEP
	_VT.apply_label_primary(title_label)
	_VT.apply_label_secondary(encounter_detail)
	start_duel_btn.add_theme_stylebox_override("normal", _VT.gem_button_style())
	start_duel_btn.add_theme_font_size_override("font_size", _VT.FONT_BUTTON)
	how_to_play_btn.add_theme_stylebox_override("normal", _VT.secondary_button_style())
	settings_btn.add_theme_stylebox_override("normal", _VT.secondary_button_style())
	help_panel.add_theme_stylebox_override("panel", _VT.panel_style())
	settings_panel.add_theme_stylebox_override("panel", _VT.panel_style())


func _build_settings_panel() -> void:
	for c in settings_panel.get_children():
		c.queue_free()
	var vbox := VBoxContainer.new()
	settings_panel.add_child(vbox)
	for key in ["sound_volume", "music_volume", "haptics", "screen_shake", "reduce_motion"]:
		var row := HBoxContainer.new()
		var lbl := Label.new()
		lbl.text = key.replace("_", " ").capitalize()
		_VT.apply_label_secondary(lbl)
		row.add_child(lbl)
		var check := CheckButton.new()
		check.button_pressed = bool(_SaveData.get_setting(key, true)) if key in ["haptics", "screen_shake"] else false
		if key == "reduce_motion":
			check.button_pressed = bool(_SaveData.get_setting(key, false))
		check.toggled.connect(func(on): _SaveData.set_setting(key, on))
		row.add_child(check)
		vbox.add_child(row)


func _on_encounter_selected(_index: int) -> void:
	_update_detail()


func _update_detail() -> void:
	var idx := encounter_option.selected
	if idx < 0 or idx >= _encounters.size():
		return
	var rs: DmbDuelRuleset = _encounters[idx]
	var diff_idx := difficulty_option.selected
	var diff_name := "Medium"
	if diff_idx >= 0 and diff_idx < _difficulties.size():
		diff_name = _difficulties[diff_idx].display_name
	encounter_detail.text = (
		"%s · %d loci · %d casts · %s" % [
			rs.enemy_name, rs.slot_count, rs.effective_max_attacks(), diff_name,
		]
	)


func _session() -> Node:
	return get_node("/root/EncounterSession")


func _on_start_duel() -> void:
	var idx := encounter_option.selected
	if idx >= 0 and idx < _encounters.size():
		_session().set_encounter(_encounters[idx].id)
	var didx := difficulty_option.selected
	if didx >= 0 and didx < _difficulties.size():
		var d = _difficulties[didx]
		_session().set_difficulty(d.id)
		_SaveData.set_last_difficulty(d.id)
	get_tree().change_scene_to_file("res://client/scenes/game_board.tscn")


func _on_how_to_play() -> void:
	settings_panel.visible = false
	if help_panel.visible:
		help_panel.visible = false
	else:
		help_label.text = HOW_TO_PLAY_TEXT + "\n\n" + FEEDBACK_HELP
		help_panel.visible = true


func _on_settings() -> void:
	help_panel.visible = false
	settings_panel.visible = not settings_panel.visible


func ui_action_start_encounter(encounter_id: String) -> void:
	for i in range(_encounters.size()):
		if _encounters[i].id == encounter_id:
			encounter_option.select(i)
			break
	_update_detail()
	_on_start_duel()


func ui_action_select_encounter(encounter_id: String) -> void:
	for i in range(_encounters.size()):
		if _encounters[i].id == encounter_id:
			encounter_option.select(i)
			break
	_update_detail()


func ui_action_select_difficulty(difficulty_id: String) -> void:
	for i in range(_difficulties.size()):
		if _difficulties[i].id == difficulty_id:
			difficulty_option.select(i)
			break
	_update_detail()


func ui_has_help_panel() -> bool:
	return how_to_play_btn != null
