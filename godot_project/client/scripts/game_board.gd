extends Control
class_name GameBoard

signal game_finished

@onready var status_label: Label = $VBox/StatusLabel
@onready var secret_row: HBoxContainer = $VBox/SecretRow
@onready var lock_button: Button = $VBox/SecretRow/LockButton
@onready var colour_picker: ColourPicker = $VBox/ColourPicker
@onready var bot_board: VBoxContainer = $VBox/BotBoard
@onready var human_guess_row: HBoxContainer = $VBox/HumanGuessRow
@onready var submit_button: Button = $VBox/HumanGuessRow/SubmitButton
@onready var result_panel: PanelContainer = $VBox/ResultPanel
@onready var result_label: Label = $VBox/ResultPanel/ResultLabel
@onready var restart_button: Button = $VBox/RestartButton

var game: DmbSequentialDuelGame
var _secret_slots: Array = []
var _guess_slots: Array = []
var _bot_rows: Array = []
var _active_mode: String = ""  # "secret" | "guess"
var _active_slot: int = -1
var _bot_seed: int = 42


func _ready() -> void:
	_secret_slots = _collect_peg_slots(secret_row)
	_guess_slots = _collect_peg_slots(human_guess_row)
	for slot in _secret_slots:
		slot.slot_pressed.connect(_on_secret_slot_pressed)
	for slot in _guess_slots:
		slot.slot_pressed.connect(_on_guess_slot_pressed)
	colour_picker.colour_selected.connect(_on_colour_selected)
	lock_button.pressed.connect(_on_lock_pressed)
	submit_button.pressed.connect(_on_submit_pressed)
	restart_button.pressed.connect(_on_restart_pressed)
	start_new_game(_bot_seed)


func start_new_game(bot_seed: int = 42) -> void:
	_bot_seed = bot_seed
	game = DmbSequentialDuelGame.new(bot_seed)
	_active_mode = ""
	_active_slot = -1
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


func _on_guess_slot_pressed(slot: int) -> void:
	if game.phase != DmbSequentialDuelGame.GamePhase.HUMAN_GUESSING:
		return
	_active_mode = "guess"
	_active_slot = slot


func _on_colour_selected(colour: int) -> void:
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
	_run_bot_guesses_stepwise()


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
	_update_colour_picker()
	_update_human_guess_row()
	_update_submit_button()


func _update_status() -> void:
	match game.phase:
		DmbSequentialDuelGame.GamePhase.HUMAN_SETUP:
			status_label.text = "Set your secret code (click pegs, pick colours, then Lock)"
		DmbSequentialDuelGame.GamePhase.BOT_GUESSING:
			status_label.text = "Bot is guessing your code..."
		DmbSequentialDuelGame.GamePhase.HUMAN_GUESSING:
			status_label.text = "Guess the bot's code (%d guesses left)" % game.human_guesses_remaining()
		DmbSequentialDuelGame.GamePhase.FINISHED:
			status_label.text = "Game over"


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
	lock_button.visible = setup or game.phase == DmbSequentialDuelGame.GamePhase.HUMAN_SETUP


func _update_lock_button() -> void:
	lock_button.disabled = not game.can_lock_human_secret()


func _update_colour_picker() -> void:
	var active := game.phase == DmbSequentialDuelGame.GamePhase.HUMAN_SETUP \
		or game.phase == DmbSequentialDuelGame.GamePhase.HUMAN_GUESSING
	colour_picker.set_interactive(active)


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
		result_label.text = "%s\n\nHuman solved: %s (%d guesses)\nBot solved: %s (%d guesses)" % [
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


func ui_action_pick_secret_slot(slot: int) -> void:
	_on_secret_slot_pressed(slot)


func ui_action_pick_colour(colour: int) -> void:
	_on_colour_selected(colour)


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
