extends Control

const HOW_TO_PLAY_TEXT := (
	"How to play:\n"
	+ "• Choose an encounter — each duel has different points, magics, and attack limits.\n"
	+ "• Pick a magic type for each point on your pattern.\n"
	+ "• Cast pattern to lock your secret; the enemy sets theirs too.\n"
	+ "• You attack first; then turns alternate one attack at a time.\n"
	+ "• Hit = right magic, right point. Weakness = right magic, wrong point.\n"
	+ "• Use feedback to deduce the enemy pattern before they break yours."
)

@onready var encounter_option: OptionButton = $VBox/EncounterRow/EncounterOption
@onready var encounter_detail: Label = $VBox/EncounterDetail
@onready var start_duel_btn: Button = $VBox/StartDuelButton
@onready var how_to_play_btn: Button = $VBox/HowToPlayButton
@onready var help_panel: PanelContainer = $VBox/HelpPanel
@onready var help_label: Label = $VBox/HelpPanel/HelpLabel

var _encounters: Array = []


func _ready() -> void:
	_encounters = DmbEncounters.all_encounters()
	encounter_option.clear()
	for i in range(_encounters.size()):
		var rs: DmbDuelRuleset = _encounters[i]
		encounter_option.add_item(rs.display_name, i)
		if rs.id == DmbEncounters.DEFAULT_ENCOUNTER_ID:
			encounter_option.select(i)
	_update_detail()
	encounter_option.item_selected.connect(_on_encounter_selected)
	start_duel_btn.pressed.connect(_on_start_duel)
	how_to_play_btn.pressed.connect(_on_how_to_play)


func _on_encounter_selected(_index: int) -> void:
	_update_detail()


func _update_detail() -> void:
	var idx := encounter_option.selected
	if idx < 0 or idx >= _encounters.size():
		return
	var rs: DmbDuelRuleset = _encounters[idx]
	encounter_detail.text = (
		"%s\n" % rs.enemy_name
		+ "Points: %d · Secret magics: %d · Attack magics: %d · Max attacks: %d\n" % [
			rs.slot_count,
			rs.secret_magic_pool.size(),
			rs.attack_magic_pool.size(),
			rs.effective_max_attacks(),
		]
		+ "Difficulty: %s\n" % rs.enemy_difficulty.capitalize()
		+ "Tell: %s" % rs.enemy_visual_hint
	)


func _session() -> Node:
	return get_node("/root/EncounterSession")


func _on_start_duel() -> void:
	var idx := encounter_option.selected
	if idx >= 0 and idx < _encounters.size():
		var rs: DmbDuelRuleset = _encounters[idx]
		_session().set_encounter(rs.id)
	get_tree().change_scene_to_file("res://client/scenes/game_board.tscn")


func _on_how_to_play() -> void:
	if help_panel.visible:
		help_panel.visible = false
	else:
		help_label.text = HOW_TO_PLAY_TEXT
		help_panel.visible = true


func ui_action_start_encounter(encounter_id: String) -> void:
	for i in range(_encounters.size()):
		var rs: DmbDuelRuleset = _encounters[i]
		if rs.id == encounter_id:
			encounter_option.select(i)
			break
	_update_detail()
	_on_start_duel()


func ui_action_select_encounter(encounter_id: String) -> void:
	for i in range(_encounters.size()):
		var rs: DmbDuelRuleset = _encounters[i]
		if rs.id == encounter_id:
			encounter_option.select(i)
			break
	_update_detail()


func ui_has_help_panel() -> bool:
	return how_to_play_btn != null
