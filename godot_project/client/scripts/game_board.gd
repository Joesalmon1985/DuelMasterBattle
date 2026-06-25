extends Control
class_name GameBoard

const _MagicPickerScript = preload("res://client/components/magic_picker.gd")
const _Art = preload("res://client/scripts/art.gd")

const HOW_TO_PLAY_TEXT := (
	"How to play:\n"
	+ "• Pick a magic type for each point: Shield, Body, Staff, Mind.\n"
	+ "• Cast pattern to lock your secret; the enemy wizard attacks first.\n"
	+ "• Hit = right magic, right point.\n"
	+ "• Weakness = right magic, wrong point.\n"
	+ "• Use enemy attack feedback to deduce their hidden pattern, then Attack."
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
@onready var human_guess_section: VBoxContainer = $VBox/HumanGuessSection
@onready var human_guess_row: HBoxContainer = $VBox/HumanGuessSection/HumanGuessRow
@onready var submit_button: Button = $VBox/HumanGuessSection/HumanGuessRow/SubmitButton
@onready var skip_button: Button = $VBox/SkipButton
@onready var result_panel: PanelContainer = $VBox/ResultPanel
@onready var result_label: Label = $VBox/ResultPanel/ResultLabel
@onready var restart_button: Button = $VBox/RestartButton
@onready var difficulty_option: OptionButton = $VBox/DifficultyRow/DifficultyOption
@onready var player_wizard: TextureRect = $VBox/DuelPanel/PlayerColumn/PlayerWizardRow/PlayerWizard
@onready var enemy_wizard: TextureRect = $VBox/DuelPanel/EnemyColumn/EnemyWizardRow/EnemyWizard
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
var _active_mode: String = ""
var _active_slot: int = -1
var _bot_seed: int = 42
var _difficulty: String = "expert"
var _bot_attack_delay_sec: float = 0.75
var _skip_bot_attacks: bool = false
var _help_mode: String = ""


func _ready() -> void:
	_secret_slots = _collect_peg_slots(secret_row)
	_guess_slots = _collect_peg_slots(human_guess_row)
	for slot in _secret_slots:
		slot.slot_pressed.connect(_on_secret_slot_pressed)
	for slot in _guess_slots:
		slot.slot_pressed.connect(_on_guess_slot_pressed)
	_setup_difficulty_options()
	_setup_art()
	_setup_point_headers(secret_point_headers, _secret_slots)
	_setup_point_headers(human_point_headers, _guess_slots)
	_configure_bot_pacing_for_environment()
	_magic_picker = _MagicPickerScript.new()
	_magic_picker.name = "MagicPicker"
	add_child(_magic_picker)
	_magic_picker.magic_selected.connect(_on_magic_selected)
	lock_button.pressed.connect(_on_lock_pressed)
	submit_button.pressed.connect(_on_submit_pressed)
	restart_button.pressed.connect(_on_restart_pressed)
	skip_button.pressed.connect(_on_skip_pressed)
	difficulty_option.item_selected.connect(_on_difficulty_changed)
	how_to_play_button.pressed.connect(_on_how_to_play_pressed)
	how_feedback_button.pressed.connect(_on_how_feedback_pressed)
	start_new_game(_bot_seed)


func _configure_bot_pacing_for_environment() -> void:
	if DisplayServer.get_name() == "headless":
		_bot_attack_delay_sec = 0.0


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


func _setup_point_headers(container: HBoxContainer, slots: Array) -> void:
	for i in range(DmbColourData.POINT_NAMES.size()):
		var cell := _make_point_header_cell(i)
		container.add_child(cell)
		if i < slots.size():
			slots[i].point_label = DmbColourData.POINT_NAMES[i]


func _make_point_header_cell(point_index: int) -> VBoxContainer:
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
	lbl.text = DmbColourData.POINT_NAMES[point_index]
	lbl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	cell.add_child(lbl)
	return cell


func _setup_difficulty_options() -> void:
	difficulty_option.clear()
	difficulty_option.add_item("Easy", 0)
	difficulty_option.add_item("Normal", 1)
	difficulty_option.add_item("Hard", 2)
	difficulty_option.add_item("Expert", 3)
	difficulty_option.select(3)


func _on_difficulty_changed(index: int) -> void:
	var levels := ["easy", "normal", "hard", "expert"]
	_difficulty = levels[index]
	start_new_game(_bot_seed)


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
	game = DmbSequentialDuelGame.new(bot_seed, _difficulty)
	_active_mode = ""
	_active_slot = -1
	_skip_bot_attacks = false
	skip_button.visible = false
	_magic_picker.close()
	result_panel.visible = false
	help_content.visible = false
	_help_mode = ""
	_clear_bot_rows()
	_refresh_all()


func _collect_peg_slots(row: HBoxContainer) -> Array:
	var slots: Array = []
	for child in row.get_children():
		if child is PegSlot:
			slots.append(child)
	return slots


func _on_secret_slot_pressed(slot: int) -> void:
	if game.phase != DmbSequentialDuelGame.GamePhase.HUMAN_SETUP:
		return
	_active_mode = "secret"
	_active_slot = slot
	_open_picker_for_slot(_secret_slots[slot])


func _on_guess_slot_pressed(slot: int) -> void:
	if game.phase != DmbSequentialDuelGame.GamePhase.HUMAN_GUESSING:
		return
	_active_mode = "guess"
	_active_slot = slot
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
	_run_bot_guesses_stepwise.call_deferred()


func _on_skip_pressed() -> void:
	_skip_bot_attacks = true


func _run_bot_guesses_stepwise() -> void:
	_skip_bot_attacks = false
	skip_button.visible = true
	while game.phase == DmbSequentialDuelGame.GamePhase.BOT_GUESSING:
		var rec := game.bot_make_guess()
		if rec == null:
			break
		_add_bot_row(rec)
		_highlight_latest_bot_row()
		_scroll_bot_board_to_end()
		_refresh_all()
		if _skip_bot_attacks or _bot_attack_delay_sec <= 0.0:
			continue
		await get_tree().create_timer(_bot_attack_delay_sec).timeout
	skip_button.visible = false
	_refresh_all()


func _on_submit_pressed() -> void:
	if not game.can_submit_human_guess():
		return
	game.submit_human_guess()
	_refresh_all()
	if game.phase == DmbSequentialDuelGame.GamePhase.FINISHED:
		_show_result()


func _on_restart_pressed() -> void:
	start_new_game(_bot_seed)


func _add_bot_row(rec: DmbGuessRecord) -> void:
	if _bot_rows.size() > 0:
		var prev: FeedbackDisplay = _bot_rows[_bot_rows.size() - 1]
		prev.set_highlighted(false)
	var row := FeedbackDisplay.new()
	row.name = "BotRow%d" % _bot_rows.size()
	bot_board.add_child(row)
	row.show_guess(rec.guess, rec.exact, rec.colour_only)
	_bot_rows.append(row)


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
		DmbSequentialDuelGame.GamePhase.BOT_GUESSING:
			status_label.text = "Enemy wizard is attacking"
		DmbSequentialDuelGame.GamePhase.HUMAN_GUESSING:
			var bot_msg := ""
			if game.bot_guesses.size() > 0:
				var last: DmbGuessRecord = game.bot_guesses[game.bot_guesses.size() - 1]
				if last.exact == DmbConstants.CODE_LENGTH:
					bot_msg = "Enemy SOLVED your pattern in %d attacks! " % game.bot_guesses.size()
				else:
					bot_msg = "Enemy FAILED after %d attacks. "
			status_label.text = "%sEnemy pattern hidden — Your turn to attack (%d left)" % [
				bot_msg, game.human_guesses_remaining()
			]
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
		or game.phase == DmbSequentialDuelGame.GamePhase.HUMAN_GUESSING
	_magic_picker.set_interactive(active)
	if not active:
		_magic_picker.close()


func _update_human_guess_row() -> void:
	var active := game.phase == DmbSequentialDuelGame.GamePhase.HUMAN_GUESSING
	var show_section := active or game.phase == DmbSequentialDuelGame.GamePhase.FINISHED
	human_guess_section.visible = show_section
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
		var winner := "Draw"
		match r.outcome:
			"human_win":
				winner = "You"
			"bot_win":
				winner = "Enemy wizard"
		result_label.text = (
			"Duel result\n\n"
			+ "Winner: %s\n\n" % winner
			+ "You: %s — %d attacks\n" % ["solved" if r.human_solved else "failed", r.human_guess_count]
			+ "Enemy: %s — %d attacks"
			% ["solved" if r.bot_solved else "failed", r.bot_guess_count]
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


func ui_set_difficulty(level: String) -> void:
	var levels := {"easy": 0, "normal": 1, "hard": 2, "expert": 3}
	if levels.has(level):
		_difficulty = level
		difficulty_option.select(levels[level])
		start_new_game(_bot_seed)


func ui_get_difficulty() -> String:
	return _difficulty


func ui_set_bot_pacing(delay_sec: float, skip_immediately: bool = false) -> void:
	_bot_attack_delay_sec = delay_sec
	_skip_bot_attacks = skip_immediately


func ui_skip_bot_attacks() -> void:
	_skip_bot_attacks = true


func ui_has_wizard_portraits() -> bool:
	return player_wizard.texture != null and enemy_wizard.texture != null


func ui_has_point_headers() -> bool:
	return secret_point_headers.get_child_count() == 4 and human_point_headers.get_child_count() == 4


func ui_has_help_panel() -> bool:
	return how_to_play_button != null and how_feedback_button != null


func _fail_smoke_picker() -> void:
	push_error("Magic picker not open")
