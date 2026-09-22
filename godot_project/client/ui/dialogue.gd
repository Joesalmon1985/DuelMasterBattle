extends RefCounted
class_name DmbDialoguePresenter

## Attached speech / formal conversation UI (C09 / T085).
## Reuses WorldInteractionLabel; formal choices acquire a pause token.
## Ambient chatter does not pause Game Time. Walk-away grants no reward.

signal formal_opened(speaker_id: String)
signal formal_closed(speaker_id: String, rewarded: bool)
signal choice_made(speaker_id: String, choice_id: String)
signal ambient_spoken(speaker_id: String)

const PAGE_SIZE := 3

var _label  # WorldInteractionLabel
var _speaker_id := ""
var _formal := false
var _pause_held := false
var _acquire_pause: Callable = Callable()
var _release_pause: Callable = Callable()
var _pending_reward := false
var _choices: Array = []
var _choice_page := 0
var _aspect_text := ""


func bind(label, acquire_pause: Callable = Callable(), release_pause: Callable = Callable()) -> void:
	_label = label
	_acquire_pause = acquire_pause
	_release_pause = release_pause
	if _label != null and _label.has_signal("response_chosen"):
		if not _label.response_chosen.is_connected(_on_response_chosen):
			_label.response_chosen.connect(_on_response_chosen)
	if _label != null and _label.has_signal("conversation_dismissed"):
		if not _label.conversation_dismissed.is_connected(_on_dismissed):
			_label.conversation_dismissed.connect(_on_dismissed)


func show_ambient(speaker_id: String, line: String) -> void:
	## Ambient chatter — no pause token, no reward path.
	_speaker_id = speaker_id
	_formal = false
	_pending_reward = false
	_aspect_text = ""
	if _label != null and _label.has_method("begin_speech"):
		_label.begin_speech([line], [])
	ambient_spoken.emit(speaker_id)


func open_formal(speaker_id: String, lines: Array, choices: Array, aspect_interjection: String = "") -> void:
	_speaker_id = speaker_id
	_formal = true
	_pending_reward = false
	_choices = choices.duplicate(true)
	_choice_page = 0
	_aspect_text = aspect_interjection
	_acquire()
	var speech: Array = lines.duplicate(true)
	if aspect_interjection != "":
		speech.append(aspect_interjection)
	var page := _page_choices()
	if _label != null and _label.has_method("begin_speech"):
		_label.begin_speech(speech, page)
	formal_opened.emit(speaker_id)


func page_next() -> Array:
	if _choices.size() <= PAGE_SIZE:
		return _page_choices()
	_choice_page = (_choice_page + 1) % int(ceil(float(_choices.size()) / float(PAGE_SIZE)))
	var page := _page_choices()
	if _label != null and _label.has_method("begin_speech"):
		_label.begin_speech(["…"], page)
	return page


func walk_away() -> void:
	## Cancel without committing unchosen rewards.
	var rewarded := false
	_pending_reward = false
	_release()
	if _label != null and _label.has_method("collapse"):
		_label.collapse()
	var sid := _speaker_id
	_formal = false
	formal_closed.emit(sid, rewarded)


func is_formal() -> bool:
	return _formal


func is_paused() -> bool:
	return _pause_held


func pending_reward() -> bool:
	return _pending_reward


func visible_choice_count() -> int:
	return _page_choices().size()


func _page_choices() -> Array:
	if _choices.is_empty():
		return []
	var start := _choice_page * PAGE_SIZE
	var page: Array = []
	for i in range(start, mini(start + PAGE_SIZE, _choices.size())):
		var raw = _choices[i]
		if typeof(raw) == TYPE_DICTIONARY:
			page.append(str(raw.get("text", raw.get("label", raw.get("id", "")))))
		else:
			page.append(str(raw))
	if _choices.size() > PAGE_SIZE:
		page.append("More…")
	return page


func _on_response_chosen(_key: String, index: int) -> void:
	if not _formal:
		return
	var page := _page_choices()
	if index < 0 or index >= page.size():
		return
	var text := str(page[index])
	if text == "More…":
		page_next()
		return
	var absolute := _choice_page * PAGE_SIZE + index
	var choice_id := ""
	if absolute < _choices.size():
		var raw = _choices[absolute]
		if typeof(raw) == TYPE_DICTIONARY:
			choice_id = str(raw.get("id", absolute))
		else:
			choice_id = str(absolute)
	_pending_reward = true
	choice_made.emit(_speaker_id, choice_id)
	_release()
	_formal = false
	formal_closed.emit(_speaker_id, true)


func _on_dismissed(_key: String) -> void:
	if _formal:
		walk_away()


func _acquire() -> void:
	if _pause_held:
		return
	if _acquire_pause.is_valid():
		_acquire_pause.call()
	_pause_held = true


func _release() -> void:
	if not _pause_held:
		return
	if _release_pause.is_valid():
		_release_pause.call()
	_pause_held = false
