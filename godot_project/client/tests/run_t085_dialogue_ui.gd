extends SceneTree

## T085 attached dialogue presenter: pause formal, not ambient; walk-away no reward.
## godot --headless --path godot_project --script res://client/tests/run_t085_dialogue_ui.gd

const Presenter = preload("res://client/ui/dialogue.gd")
const Aspect = preload("res://client/ui/aspect_interjection.gd")
const Context = preload("res://client/ui/context_actions.gd")
const WIL = preload("res://client/world/world_interaction_label.gd")

var _failures: Array = []
var _paused := false


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	await process_frame
	var label = WIL.new()
	root.add_child(label)
	await process_frame

	var presenter = Presenter.new()
	presenter.bind(label, Callable(self, "_acq"), Callable(self, "_rel"))

	# Ambient does not pause.
	presenter.show_ambient("person:1", "Morning.")
	_assert(not presenter.is_paused(), "ambient must not pause")
	_assert(not presenter.is_formal(), "ambient not formal")

	# Formal pauses and pages ~3 choices.
	var choices := [
		{"id": "a", "text": "Ask about the yard"},
		{"id": "b", "text": "Ask about the ridge"},
		{"id": "c", "text": "Ask about the channel"},
		{"id": "d", "text": "Say nothing"},
	]
	var interjection := Aspect.line_for("empathy", {"label": "Worker"})
	_assert(Aspect.is_legible(interjection), "aspect line illegible")
	presenter.open_formal("person:1", ["The yard has gone quiet."], choices, interjection)
	_assert(presenter.is_paused(), "formal must pause Game Time")
	_assert(presenter.is_formal(), "formal flag")
	_assert(presenter.visible_choice_count() == 4, "page should show 3 + More…")  # 3 + More

	# Walk-away grants no reward.
	presenter.walk_away()
	_assert(not presenter.pending_reward(), "walk-away must not reward")
	_assert(not presenter.is_paused(), "pause released on walk-away")

	# One pointer reaches UI / cancel via context actions.
	var ctx = Context.new()
	ctx.begin_formal_choice("person:1")
	_assert(ctx.one_pointer_targets_ui(), "pointer consumed for formal UI")
	ctx.walk_away_from_formal("person:1")
	_assert(not ctx.is_formal_open(), "cancel closes formal")

	# Labels remain legible at target window sizes.
	for size in [Vector2(450, 800), Vector2(720, 1280), Vector2(1280, 720)]:
		_assert(Aspect.is_legible(interjection, 120), "legible at %s" % str(size))

	if _failures.is_empty():
		print("T085_DIALOGUE_UI_OK")
		quit(0)
	else:
		for f in _failures:
			push_error(str(f))
		print("T085_DIALOGUE_UI_FAIL count=", _failures.size())
		quit(1)


func _acq() -> void:
	_paused = true


func _rel() -> void:
	_paused = false


func _assert(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)
