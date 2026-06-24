extends Control

@onready var human_vs_bot_btn: Button = $VBox/HumanVsBotButton
@onready var title_label: Label = $VBox/TitleLabel


func _ready() -> void:
	human_vs_bot_btn.pressed.connect(_on_human_vs_bot)


func _on_human_vs_bot() -> void:
	get_tree().change_scene_to_file("res://client/scenes/game_board.tscn")


func ui_action_start_human_vs_bot() -> void:
	_on_human_vs_bot()
