extends Control

const _Encounters = preload("res://sim/encounters.gd")
const _DifficultyProfiles = preload("res://sim/difficulty_profiles.gd")
const _SaveData = preload("res://client/scripts/save_data.gd")

const HOW_TO_PLAY_TEXT := (
	"How to play:\n"
	+ "• Choose difficulty and encounter.\n"
	+ "• Set your hidden ward — one essence per locus.\n"
	+ "• Cast attacks in real time when your cast window opens.\n"
	+ "• Read aggregate Fracture / Echo / Fade feedback.\n"
	+ "• Break the rival's ward before yours collapses."
)
const FEEDBACK_HELP := (
	"Each attack tells you how many essences were exactly right, "
	+ "how many were present but displaced, and how many faded. "
	+ "It never tells you which specific locus caused each result."
)

@onready var difficulty_option: OptionButton = $VBox/DifficultyRow/DifficultyOption
@onready var encounter_option: OptionButton = $VBox/EncounterRow/EncounterOption
@onready var encounter_detail: Label = $VBox/EncounterDetail
@onready var start_duel_btn: Button = $VBox/StartDuelButton
@onready var how_to_play_btn: Button = $VBox/HowToPlayButton
@onready var settings_btn: Button = $VBox/SettingsButton
@onready var help_panel: PanelContainer = $VBox/HelpPanel
@onready var help_label: Label = $VBox/HelpPanel/HelpLabel
@onready var settings_panel: PanelContainer = $VBox/SettingsPanel

var _encounters: Array = []
var _difficulties: Array = []


func _ready() -> void:
	_difficulties = _DifficultyProfiles.all_profiles()
	difficulty_option.clear()
	for i in range(_difficulties.size()):
		var d = _difficulties[i]
		difficulty_option.add_item("%s — %s" % [d.display_name, d.description], i)
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


func _build_settings_panel() -> void:
	for c in settings_panel.get_children():
		c.queue_free()
	var vbox := VBoxContainer.new()
	settings_panel.add_child(vbox)
	for key in ["sound_volume", "music_volume", "haptics", "screen_shake", "reduce_motion"]:
		var row := HBoxContainer.new()
		var lbl := Label.new()
		lbl.text = key.replace("_", " ").capitalize()
		row.add_child(lbl)
		var check := CheckButton.new()
		check.button_pressed = bool(_SaveData.get_setting(key, true)) if key in ["haptics", "screen_shake"] else false
		if key == "reduce_motion":
			check.button_pressed = bool(_SaveData.get_setting(key, false))
		check.toggled.connect(func(on): _SaveData.set_setting(key, on))
		row.add_child(check)
		vbox.add_child(row)
	var help_lbl := Label.new()
	help_lbl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	help_lbl.text = FEEDBACK_HELP
	vbox.add_child(help_lbl)


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
		"%s\n" % rs.enemy_name
		+ "Loci: %d · Secret essences: %d · Attack essences: %d · Cast limit: %d\n" % [
			rs.slot_count,
			rs.secret_magic_pool.size(),
			rs.attack_magic_pool.size(),
			rs.effective_max_attacks(),
		]
		+ "Difficulty: %s\n" % diff_name
		+ "Tell: %s" % rs.enemy_visual_hint
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
