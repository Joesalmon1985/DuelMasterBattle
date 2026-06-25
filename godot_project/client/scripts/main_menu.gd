extends Control

const HOW_TO_PLAY_TEXT := (
	"How to play:\n"
	+ "• Pick a magic type for each point: Shield, Body, Staff, Mind.\n"
	+ "• Cast pattern to lock your secret; the bot sets its hidden pattern too.\n"
	+ "• You attack first; then turns alternate one attack at a time.\n"
	+ "• Hit = right magic, right point.\n"
	+ "• Weakness = right magic, wrong point.\n"
	+ "• Use feedback to deduce the enemy pattern before they break yours."
)

@onready var human_vs_bot_btn: Button = $VBox/HumanVsBotButton
@onready var how_to_play_btn: Button = $VBox/HowToPlayButton
@onready var help_panel: PanelContainer = $VBox/HelpPanel
@onready var help_label: Label = $VBox/HelpPanel/HelpLabel


func _ready() -> void:
	human_vs_bot_btn.pressed.connect(_on_human_vs_bot)
	how_to_play_btn.pressed.connect(_on_how_to_play)


func _on_human_vs_bot() -> void:
	get_tree().change_scene_to_file("res://client/scenes/game_board.tscn")


func _on_how_to_play() -> void:
	if help_panel.visible:
		help_panel.visible = false
	else:
		help_label.text = HOW_TO_PLAY_TEXT
		help_panel.visible = true


func ui_action_start_human_vs_bot() -> void:
	_on_human_vs_bot()


func ui_has_help_panel() -> bool:
	return how_to_play_btn != null
