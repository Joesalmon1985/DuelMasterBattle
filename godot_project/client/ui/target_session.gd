extends RefCounted
class_name DmbTargetSession

## One foreground target/action session for NPCs, soldiers and hazards.
## Preserves AttachedChoiceCard appearance; does not own knowledge or dialogue.

const ContextActions = preload("res://client/ui/context_actions.gd")

signal observation_requested(entity_id: String, kind: String)
signal talk_requested(entity_id: String)
signal action_requested(entity_id: String, action_id: String, payload: Dictionary)
signal dismissed(entity_id: String)

var router
var choice_card
var _kind_by_id: Dictionary = {}
var _open := false
var _target_id := ""
var _acquire_pause: Callable = Callable()
var _release_pause: Callable = Callable()
var _stale_direction_guard := false


func setup(card, acquire_pause: Callable = Callable(), release_pause: Callable = Callable()) -> void:
	choice_card = card
	router = ContextActions.new()
	_acquire_pause = acquire_pause
	_release_pause = release_pause
	if choice_card != null:
		if not choice_card.action_chosen.is_connected(_on_card_action):
			choice_card.action_chosen.connect(_on_card_action)
		if not choice_card.closed.is_connected(_on_card_closed):
			choice_card.closed.connect(_on_card_closed)


func register_kind(entity_id: String, kind: String) -> void:
	_kind_by_id[entity_id] = kind


func is_open() -> bool:
	return _open


func target_id() -> String:
	return _target_id


func consume_pointer() -> void:
	if router != null:
		router.consume_pointer()


func handle_target_click(entity_id: String, nearby: bool, kind: String, title: String, follow: Node2D = null) -> String:
	if entity_id == "":
		return ""
	register_kind(entity_id, kind)
	_stale_direction_guard = true
	var route: String = router.route_world_click(nearby, entity_id)
	if route == "observe":
		if _open:
			close(false)
		observation_requested.emit(entity_id, kind)
		return "observe"
	if route == "choice":
		_open_menu(entity_id, kind, title, follow)
		return "choice"
	return ""


func _open_menu(entity_id: String, kind: String, title: String, follow: Node2D) -> void:
	_target_id = entity_id
	_open = true
	if _acquire_pause.is_valid():
		_acquire_pause.call()
	router.begin_formal_choice(entity_id)
	var actions: Array = _actions_for(kind)
	if choice_card != null:
		choice_card.open_for(entity_id, title, actions, follow)


func _actions_for(kind: String) -> Array:
	match kind:
		"person", "npc":
			return [
				{"id": "observe", "label": "Observe"},
				{"id": "talk", "label": "Talk"},
			]
		"hazard":
			return [
				{"id": "observe", "label": "Observe"},
				{"id": "challenge", "label": "Challenge"},
			]
		_:
			# Soldiers / units — approved military menu.
			return [
				{"id": "observe", "label": "Observe"},
				{"id": "buff", "label": "Buff…"},
				{"id": "destroy", "label": "Destroy"},
			]


func _on_card_action(action_id: String, payload: Dictionary) -> void:
	var uid: String = _target_id
	if choice_card != null and str(choice_card.target_id()) != "":
		uid = str(choice_card.target_id())
	var kind: String = str(_kind_by_id.get(uid, "unit"))
	match action_id:
		"observe":
			observation_requested.emit(uid, kind)
			close(false)
		"talk":
			talk_requested.emit(uid)
			close(false)
		"buff":
			if choice_card != null:
				choice_card.open_buff_submenu(uid, "Buff…", null)
		"buff_shield", "buff_frequency", "buff_range":
			action_requested.emit(uid, action_id, payload)
			close(true)
		"destroy", "challenge":
			action_requested.emit(uid, action_id, payload)
			close(true)
		"back":
			_open_menu(uid, kind, str(_kind_by_id.get(uid, uid)), null)
		_:
			action_requested.emit(uid, action_id, payload)
			close(false)


func _on_card_closed() -> void:
	if _open:
		dismissed.emit(_target_id)
	_release_only()


func close(applied: bool) -> void:
	if choice_card != null:
		choice_card.visible = false
	_release_only()
	if not applied:
		dismissed.emit(_target_id)
	_open = false
	router.cancel_choice(_target_id)


func _release_only() -> void:
	_open = false
	if _release_pause.is_valid():
		_release_pause.call()


func notify_movement_intent() -> bool:
	## Returns true if an open session was dismissed.
	if _stale_direction_guard:
		# Ignore direction held before the menu opened for one frame.
		_stale_direction_guard = false
		return false
	if not _open:
		return false
	close(false)
	if choice_card != null and choice_card.has_method("close"):
		choice_card.close()
	return true


func poll_keyboard_movement_intent() -> bool:
	if not _open:
		return false
	var moving := Input.is_action_pressed("ui_left") or Input.is_action_pressed("ui_right") \
		or Input.is_action_pressed("ui_up") or Input.is_action_pressed("ui_down")
	if moving:
		return notify_movement_intent()
	return false
