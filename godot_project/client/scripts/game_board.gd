extends Control
class_name GameBoard

const _MagicPickerScript = preload("res://client/components/magic_picker.gd")
const _Art = preload("res://client/scripts/art.gd")

const HOW_TO_PLAY_TEXT := (
	"How to play:\n"
	+ "• Pick a magic type for each point: Shield, Body, Staff, Mind.\n"
	+ "• Cast pattern to lock your secret; the bot sets its hidden pattern too.\n"
	+ "• You attack first; then turns alternate one attack at a time.\n"
	+ "• Hit = right magic, right point.\n"
	+ "• Weakness = right magic, wrong point.\n"
	+ "• Use feedback to deduce the enemy pattern before they break yours."
)
const HOW_FEEDBACK_TEXT := (
	"How feedback works:\n"
	+ "• Hit = right magic, right point.\n"
	+ "• Weakness = right magic, wrong point.\n"
	+ "• Unaffected = no revealed match."
)

signal game_finished

@onready var background: TextureRect = $Background
@onready var status_label: Label = $VBox/StatusLabel
@onready var secret_row: HBoxContainer = $VBox/DuelPanel/PlayerColumn/SecretSection/SecretRow
@onready var lock_button: Button = $VBox/DuelPanel/PlayerColumn/SecretSection/SecretRow/LockButton
@onready var bot_board: VBoxContainer = $VBox/DuelPanel/EnemyColumn/BotScroll/BotBoard
@onready var bot_scroll: ScrollContainer = $VBox/DuelPanel/EnemyColumn/BotScroll
@onready var human_attack_section: VBoxContainer = $VBox/DuelPanel/PlayerColumn/HumanAttackSection
@onready var human_history_board: VBoxContainer = $VBox/DuelPanel/PlayerColumn/HumanAttackSection/HumanHistoryScroll/HumanHistoryBoard
@onready var human_history_scroll: ScrollContainer = $VBox/DuelPanel/PlayerColumn/HumanAttackSection/HumanHistoryScroll
@onready var human_guess_section: VBoxContainer = $VBox/HumanGuessSection
@onready var human_guess_row: HBoxContainer = $VBox/HumanGuessSection/HumanGuessRow
@onready var submit_button: Button = $VBox/HumanGuessSection/HumanGuessRow/SubmitButton
@onready var skip_button: Button = $VBox/SkipButton
@onready var result_panel: PanelContainer = $VBox/ResultPanel
@onready var result_label: Label = $VBox/ResultPanel/ResultLabel
@onready var restart_button: Button = $VBox/RestartButton
@onready var back_to_menu_button: Button = $VBox/BackToMenuButton
@onready var difficulty_option: OptionButton = $VBox/DifficultyRow/DifficultyOption
@onready var player_wizard: TextureRect = $VBox/DuelPanel/PlayerColumn/PlayerWizardRow/PlayerWizard
@onready var enemy_wizard: TextureRect = $VBox/DuelPanel/EnemyColumn/EnemyWizardRow/EnemyWizard
@onready var enemy_wizard_label: Label = $VBox/DuelPanel/EnemyColumn/EnemyWizardRow/EnemyWizardLabel
@onready var enemy_tell_label: Label = $VBox/DuelPanel/EnemyColumn/EnemyTellLabel
@onready var secret_point_headers: HBoxContainer = $VBox/DuelPanel/PlayerColumn/SecretSection/SecretPointHeaders
@onready var human_point_headers: HBoxContainer = $VBox/HumanGuessSection/HumanPointHeaders
@onready var how_to_play_button: Button = $VBox/HelpRow/HowToPlayButton
@onready var how_feedback_button: Button = $VBox/HelpRow/HowFeedbackButton
@onready var help_content: PanelContainer = $VBox/HelpContent
@onready var help_label: Label = $VBox/HelpContent/HelpLabel

var game: DmbSequentialDuelGame
var _magic_picker: PanelContainer
var _secret_slots: Array = []
var _guess_slots: Array = []
var _bot_rows: Array = []
var _human_rows: Array = []
var _active_mode: String = ""
var _active_slot: int = -1
var _bot_seed: int = 42
var _ruleset: DmbDuelRuleset
var _active_pool: Array = []
var _bot_attack_delay_sec: float = 0.75
var _base_bot_delay_sec: float = 0.75
var _skip_bot_attacks: bool = false
var _help_mode: String = ""


func _session() -> Node:
	return get_node("/root/EncounterSession")


func _ready() -> void:
	_ruleset = _session().get_ruleset()
	_build_board_from_ruleset()
	_setup_art()
	_configure_bot_pacing_for_environment()
	_apply_encounter_presentation()
	_magic_picker = _MagicPickerScript.new()
	_magic_picker.name = "MagicPicker"
	add_child(_magic_picker)
	_magic_picker.magic_selected.connect(_on_magic_selected)
	lock_button.pressed.connect(_on_lock_pressed)
	submit_button.pressed.connect(_on_submit_pressed)
	restart_button.pressed.connect(_on_restart_pressed)
	back_to_menu_button.pressed.connect(_on_back_to_menu_pressed)
	skip_button.pressed.connect(_on_skip_pressed)
	how_to_play_button.pressed.connect(_on_how_to_play_pressed)
	how_feedback_button.pressed.connect(_on_how_feedback_pressed)
	start_new_game(_bot_seed)


func _build_board_from_ruleset() -> void:
	_secret_slots = _build_slots(secret_row, _ruleset.slot_count, _ruleset.point_names, _on_secret_slot_pressed)
	_guess_slots = _build_slots(human_guess_row, _ruleset.slot_count, _ruleset.point_names, _on_guess_slot_pressed, 1)
	_setup_point_headers(secret_point_headers, _ruleset.point_names)
	_setup_point_headers(human_point_headers, _ruleset.point_names)


func _build_slots(row: HBoxContainer, count: int, point_names: Array, callback: Callable, insert_after: int = 0) -> Array:
	var to_remove: Array = []
	for child in row.get_children():
		if child is PegSlot:
			to_remove.append(child)
	for child in to_remove:
		row.remove_child(child)
		child.queue_free()
	var slots: Array = []
	for i in range(count):
		var slot := PegSlot.new()
		slot.slot_index = i
		if i < point_names.size():
			slot.point_label = str(point_names[i])
		row.add_child(slot)
		row.move_child(slot, insert_after + i)
		slot.slot_pressed.connect(callback)
		slots.append(slot)
	return slots


func _apply_encounter_presentation() -> void:
	enemy_wizard_label.text = _ruleset.enemy_name
	if _ruleset.enemy_visual_hint != "":
		enemy_tell_label.text = "Enemy tell: %s" % _ruleset.enemy_visual_hint
		enemy_tell_label.visible = true
	else:
		enemy_tell_label.visible = false
	_bot_attack_delay_sec = _base_bot_delay_sec * _ruleset.bot_delay_multiplier()


func _configure_bot_pacing_for_environment() -> void:
	_base_bot_delay_sec = 0.75
	if DisplayServer.get_name() == "headless":
		_base_bot_delay_sec = 0.0


func _setup_art() -> void:
	var bg_tex := _Art.load_texture("sprites/duel_background.png")
	if bg_tex != null:
		background.texture = bg_tex
	else:
		background.visible = false
	var player_tex := _Art.load_texture("sprites/player_wizard.png")
	if player_tex != null:
		player_wizard.texture = player_tex
	var enemy_tex := _Art.load_texture("sprites/enemy_wizard.png")
	if enemy_tex != null:
		enemy_wizard.texture = enemy_tex


func _setup_point_headers(container: HBoxContainer, point_names: Array) -> void:
	for c in container.get_children():
		c.queue_free()
	for i in range(point_names.size()):
		var cell := _make_point_header_cell(i, str(point_names[i]))
		container.add_child(cell)


func _make_point_header_cell(point_index: int, point_name: String) -> VBoxContainer:
	var cell := VBoxContainer.new()
	cell.alignment = BoxContainer.ALIGNMENT_CENTER
	cell.custom_minimum_size = Vector2(56, 0)
	var icon_row := HBoxContainer.new()
	icon_row.alignment = BoxContainer.ALIGNMENT_CENTER
	var tex_path := _Art.point_icon_path(point_index)
	var tex := _Art.load_texture(tex_path)
	if tex != null:
		var icon := TextureRect.new()
		icon.custom_minimum_size = Vector2(20, 20)
		icon.texture = tex
		icon.expand_mode = TextureRect.EXPAND_FIT_WIDTH_PROPORTIONAL
		icon.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		icon_row.add_child(icon)
	cell.add_child(icon_row)
	var lbl := Label.new()
	lbl.text = point_name
	lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	cell.add_child(lbl)
	return cell


func _on_how_to_play_pressed() -> void:
	_toggle_help("play", HOW_TO_PLAY_TEXT)


func _on_how_feedback_pressed() -> void:
	_toggle_help("feedback", HOW_FEEDBACK_TEXT)


func _toggle_help(mode: String, text: String) -> void:
	if _help_mode == mode and help_content.visible:
		_help_mode = ""
		help_content.visible = false
	else:
		_help_mode = mode
		help_label.text = text
		help_content.visible = true


func start_new_game(bot_seed: int = 42) -> void:
	_bot_seed = bot_seed
	_ruleset = _session().get_ruleset()
	game = DmbSequentialDuelGame.new(_ruleset, bot_seed)
	_apply_encounter_presentation()
	_active_mode = ""
	_active_slot = -1
	_skip_bot_attacks = false
	skip_button.visible = false
	_magic_picker.close()
	result_panel.visible = false
	help_content.visible = false
	_help_mode = ""
	_clear_bot_rows()
	_clear_human_rows()
	_refresh_all()



func _on_secret_slot_pressed(slot: int) -> void:
	if game.phase != DmbSequentialDuelGame.GamePhase.HUMAN_SETUP:
		return
	_active_mode = "secret"
	_active_slot = slot
	_active_pool = _ruleset.secret_magic_pool
	_magic_picker.set_allowed_magics(_active_pool)
	_open_picker_for_slot(_secret_slots[slot])


func _on_guess_slot_pressed(slot: int) -> void:
	if game.phase != DmbSequentialDuelGame.GamePhase.HUMAN_TURN:
		return
	_active_mode = "guess"
	_active_slot = slot
	_active_pool = _ruleset.attack_magic_pool
	_magic_picker.set_allowed_magics(_active_pool)
	_open_picker_for_slot(_guess_slots[slot])


func _open_picker_for_slot(slot_ctrl: PegSlot) -> void:
	var pos := slot_ctrl.global_position + Vector2(0, slot_ctrl.size.y + 4)
	_magic_picker.open_at(pos)


func _on_magic_selected(colour: int) -> void:
	if _active_slot < 0:
		return
	if _active_mode == "secret":
		game.set_human_secret_peg(_active_slot, colour)
	elif _active_mode == "guess":
		game.set_human_guess_peg(_active_slot, colour)
	_active_slot = -1
	_refresh_all()


func _on_lock_pressed() -> void:
	if not game.can_lock_human_secret():
		return
	game.lock_human_secret()
	_refresh_all()


func _on_skip_pressed() -> void:
	_skip_bot_attacks = true


func _on_submit_pressed() -> void:
	if not game.can_submit_human_guess():
		return
	var rec := game.submit_human_guess()
	_add_human_row(rec)
	_scroll_human_board_to_end()
	_refresh_all()
	if game.phase == DmbSequentialDuelGame.GamePhase.FINISHED:
		_show_result()
	elif game.phase == DmbSequentialDuelGame.GamePhase.BOT_TURN:
		_run_single_bot_turn.call_deferred()


func _run_single_bot_turn() -> void:
	_skip_bot_attacks = false
	skip_button.visible = true
	if game.phase != DmbSequentialDuelGame.GamePhase.BOT_TURN:
		skip_button.visible = false
		return
	var rec := game.bot_make_guess()
	if rec != null:
		_add_bot_row(rec)
		_highlight_latest_bot_row()
		_scroll_bot_board_to_end()
	_refresh_all()
	if game.phase == DmbSequentialDuelGame.GamePhase.FINISHED:
		skip_button.visible = false
		_show_result()
		return
	if _skip_bot_attacks or _bot_attack_delay_sec <= 0.0:
		skip_button.visible = false
		return
	await get_tree().create_timer(_bot_attack_delay_sec).timeout
	skip_button.visible = false
	_refresh_all()


func _on_restart_pressed() -> void:
	start_new_game(_bot_seed)


func _on_back_to_menu_pressed() -> void:
	get_tree().change_scene_to_file("res://client/scenes/main_menu.tscn")


func _add_bot_row(rec: DmbGuessRecord) -> void:
	if _bot_rows.size() > 0:
		var prev: FeedbackDisplay = _bot_rows[_bot_rows.size() - 1]
		prev.set_highlighted(false)
	var row := FeedbackDisplay.new()
	row.name = "BotRow%d" % _bot_rows.size()
	bot_board.add_child(row)
	row.show_guess(rec.guess, rec.exact, rec.colour_only)
	_bot_rows.append(row)


func _add_human_row(rec: DmbGuessRecord) -> void:
	if _human_rows.size() > 0:
		var prev: FeedbackDisplay = _human_rows[_human_rows.size() - 1]
		prev.set_highlighted(false)
	var row := FeedbackDisplay.new()
	row.name = "HumanRow%d" % _human_rows.size()
	human_history_board.add_child(row)
	row.show_guess(rec.guess, rec.exact, rec.colour_only)
	row.set_highlighted(true)
	_human_rows.append(row)


func _highlight_latest_bot_row() -> void:
	if _bot_rows.is_empty():
		return
	var latest: FeedbackDisplay = _bot_rows[_bot_rows.size() - 1]
	latest.set_highlighted(true)


func _scroll_bot_board_to_end() -> void:
	await get_tree().process_frame
	var vbar := bot_scroll.get_v_scroll_bar()
	if vbar != null:
		bot_scroll.scroll_vertical = int(vbar.max_value)


func _scroll_human_board_to_end() -> void:
	await get_tree().process_frame
	var vbar := human_history_scroll.get_v_scroll_bar()
	if vbar != null:
		human_history_scroll.scroll_vertical = int(vbar.max_value)


func _clear_human_rows() -> void:
	for r in _human_rows:
		r.queue_free()
	_human_rows.clear()
	for c in human_history_board.get_children():
		c.queue_free()


func _clear_bot_rows() -> void:
	for r in _bot_rows:
		r.queue_free()
	_bot_rows.clear()
	for c in bot_board.get_children():
		c.queue_free()


func _refresh_all() -> void:
	_update_status()
	_update_secret_row()
	_update_lock_button()
	_update_magic_picker()
	_update_human_guess_row()
	_update_submit_button()


func _update_status() -> void:
	match game.phase:
		DmbSequentialDuelGame.GamePhase.HUMAN_SETUP:
			status_label.text = "Choose your magical pattern"
		DmbSequentialDuelGame.GamePhase.HUMAN_TURN:
			status_label.text = "Your turn to attack (%d left)" % game.human_guesses_remaining()
		DmbSequentialDuelGame.GamePhase.BOT_TURN:
			status_label.text = "Enemy wizard is attacking"
		DmbSequentialDuelGame.GamePhase.FINISHED:
			status_label.text = "Duel result"


func _update_secret_row() -> void:
	var setup := game.phase == DmbSequentialDuelGame.GamePhase.HUMAN_SETUP
	for i in range(_secret_slots.size()):
		var slot: PegSlot = _secret_slots[i]
		if setup:
			slot.disabled = false
			var c = game.human_setup_pegs[i]
			slot.set_colour(c if c != null else -1)
		else:
			slot.set_hidden_mode()
	lock_button.visible = setup


func _update_lock_button() -> void:
	lock_button.disabled = not game.can_lock_human_secret()


func _update_magic_picker() -> void:
	var active := game.phase == DmbSequentialDuelGame.GamePhase.HUMAN_SETUP \
		or game.phase == DmbSequentialDuelGame.GamePhase.HUMAN_TURN
	_magic_picker.set_interactive(active)
	if not active:
		_magic_picker.close()


func _update_human_guess_row() -> void:
	var active := game.phase == DmbSequentialDuelGame.GamePhase.HUMAN_TURN
	var in_duel := game.phase != DmbSequentialDuelGame.GamePhase.HUMAN_SETUP
	human_attack_section.visible = in_duel
	human_guess_section.visible = in_duel or game.phase == DmbSequentialDuelGame.GamePhase.FINISHED
	for i in range(_guess_slots.size()):
		var slot: PegSlot = _guess_slots[i]
		slot.disabled = not active
		if active:
			var c = game.current_human_guess[i]
			slot.set_colour(c if c != null else -1)
		else:
			slot.set_colour(-1)


func _update_submit_button() -> void:
	submit_button.disabled = not game.can_submit_human_guess()


func _show_result() -> void:
	result_panel.visible = true
	if game.result:
		var r := game.result
		var headline := ""
		if r.outcome == "human_win" and r.human_solved:
			headline = "You broke the enemy pattern in %d attacks." % r.human_guess_count
		elif r.outcome == "bot_win" and r.bot_solved:
			headline = "The enemy wizard broke your pattern in %d attacks." % r.bot_guess_count
		elif r.outcome == "draw" and not r.human_solved and not r.bot_solved:
			var max_attacks := _ruleset.effective_max_attacks()
			headline = "Draw — both wizards used %d attacks without breaking the pattern." % max_attacks
		else:
			match r.outcome:
				"human_win":
					headline = "You win!"
				"bot_win":
					headline = "Enemy wizard wins!"
				_:
					headline = "Draw!"
		var winner := "Draw"
		match r.outcome:
			"human_win":
				winner = "You"
			"bot_win":
				winner = "Enemy wizard"
		result_label.text = (
			"Duel result\n\n"
			+ "%s\n\n" % headline
			+ "Winner: %s\n\n" % winner
			+ "Your attacks used: %d\n" % r.human_guess_count
			+ "Enemy attacks used: %d"
			% r.bot_guess_count
		)
	game_finished.emit()


# --- UI smoke test API (drives same paths as player clicks) ---

func ui_get_lock_button_enabled() -> bool:
	return not lock_button.disabled


func ui_get_visible_bot_guess_count() -> int:
	return _bot_rows.size()


func ui_get_human_guess_row_active() -> bool:
	return not _guess_slots[0].disabled if _guess_slots.size() > 0 else false


func ui_is_result_visible() -> bool:
	return result_panel.visible


func ui_is_picker_open() -> bool:
	return _magic_picker.is_open()


func ui_action_pick_secret_slot(slot: int) -> void:
	_on_secret_slot_pressed(slot)


func ui_action_pick_magic(colour: int) -> void:
	if not _magic_picker.is_open():
		_fail_smoke_picker()
		return
	_on_magic_selected(colour)


func ui_action_pick_colour(colour: int) -> void:
	ui_action_pick_magic(colour)


func ui_action_lock_secret() -> void:
	_on_lock_pressed()


func ui_action_pick_guess_slot(slot: int) -> void:
	_on_guess_slot_pressed(slot)


func ui_action_submit_guess() -> void:
	_on_submit_pressed()


func ui_action_restart() -> void:
	_on_restart_pressed()


func ui_get_visible_human_guess_count() -> int:
	return _human_rows.size()


func ui_get_human_feedback_text() -> String:
	if _human_rows.is_empty():
		return ""
	var row: FeedbackDisplay = _human_rows[_human_rows.size() - 1]
	return row.get_feedback_text()


func ui_get_phase() -> int:
	return game.phase


func ui_is_human_turn() -> bool:
	return game.phase == DmbSequentialDuelGame.GamePhase.HUMAN_TURN


func ui_is_bot_turn() -> bool:
	return game.phase == DmbSequentialDuelGame.GamePhase.BOT_TURN


func ui_get_bot_feedback_count() -> int:
	return _bot_rows.size()


func ui_secret_is_hidden() -> bool:
	if _secret_slots.is_empty():
		return false
	return _secret_slots[0].text == "****"


func ui_get_secret_slot_value(slot: int) -> int:
	if slot < 0 or slot >= _secret_slots.size():
		return -1
	return _secret_slots[slot].get_colour_id()


func ui_get_guess_slot_value(slot: int) -> int:
	if slot < 0 or slot >= _guess_slots.size():
		return -1
	return _guess_slots[slot].get_colour_id()


func ui_get_bot_feedback_text() -> String:
	if _bot_rows.is_empty():
		return ""
	var row: FeedbackDisplay = _bot_rows[_bot_rows.size() - 1]
	return row.get_feedback_text()


func ui_set_difficulty(_level: String) -> void:
	pass


func ui_get_difficulty() -> String:
	return _ruleset.enemy_difficulty


func ui_set_bot_pacing(delay_sec: float, skip_immediately: bool = false) -> void:
	_bot_attack_delay_sec = delay_sec
	_skip_bot_attacks = skip_immediately


func ui_skip_bot_attacks() -> void:
	_skip_bot_attacks = true


func ui_has_wizard_portraits() -> bool:
	return player_wizard.texture != null and enemy_wizard.texture != null


func ui_has_point_headers() -> bool:
	return (
		secret_point_headers.get_child_count() == _ruleset.slot_count
		and human_point_headers.get_child_count() == _ruleset.slot_count
	)


func ui_load_encounter(encounter_id: String) -> void:
	_session().set_encounter(encounter_id)
	_ruleset = _session().get_ruleset()
	_build_board_from_ruleset()
	_apply_encounter_presentation()
	start_new_game(_bot_seed)


func ui_get_slot_count() -> int:
	return _ruleset.slot_count


func ui_get_visible_magic_count() -> int:
	var count := 0
	for i in range(DmbConstants.NUM_COLOURS):
		if _magic_picker._buttons[i].visible:
			count += 1
	return count


func ui_get_enemy_tell_visible() -> bool:
	return enemy_tell_label.visible and enemy_tell_label.text != ""


func ui_has_help_panel() -> bool:
	return how_to_play_button != null and how_feedback_button != null


func _fail_smoke_picker() -> void:
	push_error("Magic picker not open")
