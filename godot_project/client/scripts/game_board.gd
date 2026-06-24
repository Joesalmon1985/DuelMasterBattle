extends Control
class_name GameBoard

const _MagicPickerScript = preload("res://client/components/magic_picker.gd")

signal game_finished

@onready var status_label: Label = $VBox/StatusLabel
@onready var secret_row: HBoxContainer = $VBox/SecretRow
@onready var lock_button: Button = $VBox/SecretRow/LockButton
@onready var bot_board: VBoxContainer = $VBox/BotBoard
@onready var human_guess_row: HBoxContainer = $VBox/HumanGuessRow
@onready var submit_button: Button = $VBox/HumanGuessRow/SubmitButton
@onready var result_panel: PanelContainer = $VBox/ResultPanel
@onready var result_label: Label = $VBox/ResultPanel/ResultLabel
@onready var restart_button: Button = $VBox/RestartButton
@onready var difficulty_option: OptionButton = $VBox/DifficultyRow/DifficultyOption

var game: DmbSequentialDuelGame
var _magic_picker: PanelContainer
var _secret_slots: Array = []
var _guess_slots: Array = []
var _bot_rows: Array = []
var _active_mode: String = ""  # "secret" | "guess"
var _active_slot: int = -1
var _bot_seed: int = 42
var _difficulty: String = "expert"


func _ready() -> void:
	_secret_slots = _collect_peg_slots(secret_row)
	_guess_slots = _collect_peg_slots(human_guess_row)
	for slot in _secret_slots:
		slot.slot_pressed.connect(_on_secret_slot_pressed)
	for slot in _guess_slots:
		slot.slot_pressed.connect(_on_guess_slot_pressed)
	_setup_difficulty_options()
	_magic_picker = _MagicPickerScript.new()
	_magic_picker.name = "MagicPicker"
	add_child(_magic_picker)
	_magic_picker.magic_selected.connect(_on_magic_selected)
	lock_button.pressed.connect(_on_lock_pressed)
	submit_button.pressed.connect(_on_submit_pressed)
	restart_button.pressed.connect(_on_restart_pressed)
	difficulty_option.item_selected.connect(_on_difficulty_changed)
	start_new_game(_bot_seed)


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


func start_new_game(bot_seed: int = 42) -> void:
	_bot_seed = bot_seed
	game = DmbSequentialDuelGame.new(bot_seed, _difficulty)
	_active_mode = ""
	_active_slot = -1
	_magic_picker.close()
	result_panel.visible = false
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


func _run_bot_guesses_stepwise() -> void:
	while game.phase == DmbSequentialDuelGame.GamePhase.BOT_GUESSING:
		var rec := game.bot_make_guess()
		if rec == null:
			break
		_add_bot_row(rec)
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
	var row := FeedbackDisplay.new()
	row.name = "BotRow%d" % _bot_rows.size()
	bot_board.add_child(row)
	row.show_guess(rec.guess, rec.exact, rec.colour_only)
	_bot_rows.append(row)


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
			status_label.text = "Set your four magical points (Shield, Body, Staff, Mind) — click each slot"
		DmbSequentialDuelGame.GamePhase.BOT_GUESSING:
			status_label.text = "Enemy wizard is attacking your pattern..."
		DmbSequentialDuelGame.GamePhase.HUMAN_GUESSING:
			var bot_msg := ""
			if game.bot_guesses.size() > 0:
				var last: DmbGuessRecord = game.bot_guesses[game.bot_guesses.size() - 1]
				if last.exact == DmbConstants.CODE_LENGTH:
					bot_msg = "Enemy SOLVED your pattern in %d attacks! " % game.bot_guesses.size()
				else:
					bot_msg = "Enemy FAILED after %d attacks. " % game.bot_guesses.size()
			status_label.text = "%sAttack the enemy pattern (%d left)" % [bot_msg, game.human_guesses_remaining()]
		DmbSequentialDuelGame.GamePhase.FINISHED:
			status_label.text = "Duel over"


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
	human_guess_row.visible = active or game.phase == DmbSequentialDuelGame.GamePhase.FINISHED
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
		result_label.text = "%s\n\nYou solved: %s (%d attacks)\nEnemy solved: %s (%d attacks)" % [
			r.message,
			"yes" if r.human_solved else "no", r.human_guess_count,
			"yes" if r.bot_solved else "no", r.bot_guess_count,
		]
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
	return row.get_node("FeedbackLabel").text


func ui_set_difficulty(level: String) -> void:
	var levels := {"easy": 0, "normal": 1, "hard": 2, "expert": 3}
	if levels.has(level):
		_difficulty = level
		difficulty_option.select(levels[level])
		start_new_game(_bot_seed)


func ui_get_difficulty() -> String:
	return _difficulty


func _fail_smoke_picker() -> void:
	push_error("Magic picker not open")
