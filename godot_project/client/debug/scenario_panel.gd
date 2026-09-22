extends Control
class_name DmbScenarioPanel

## Village / quest testing panel (T095). Developer-only.
## Launches the same FX-VILLAGE fixture path as tools/run_scenario.py — no
## separate quest engine. Debug view can show causal facts/effects.

@export var release_mode: bool = false

signal launch_requested(seed: int, fixture: String, quest_id: String, puzzle_id: String)
signal reset_requested()
signal replay_requested(bundle_path: String)
signal export_failure_requested(reason: String)

var _seed_edit: LineEdit
var _fixture_edit: LineEdit
var _quest_edit: LineEdit
var _puzzle_edit: LineEdit
var _debug_facts: RichTextLabel
var _visible_in_dev := true
var _last_outcome: Dictionary = {}
var _debug_facts_visible := false


func _ready() -> void:
	if release_mode:
		visible = false
		_visible_in_dev = false
		return
	_seed_edit = LineEdit.new()
	_seed_edit.text = "507"
	_seed_edit.placeholder_text = "seed"
	add_child(_seed_edit)
	_fixture_edit = LineEdit.new()
	_fixture_edit.text = "FX-VILLAGE"
	_fixture_edit.placeholder_text = "fixture"
	add_child(_fixture_edit)
	_quest_edit = LineEdit.new()
	_quest_edit.text = "quest.factory_shortage"
	_quest_edit.placeholder_text = "quest"
	add_child(_quest_edit)
	_puzzle_edit = LineEdit.new()
	_puzzle_edit.text = "puzzle.sluice"
	_puzzle_edit.placeholder_text = "puzzle"
	add_child(_puzzle_edit)
	_debug_facts = RichTextLabel.new()
	_debug_facts.visible = false
	_debug_facts.fit_content = true
	_debug_facts.text = ""
	add_child(_debug_facts)


func is_developer_controls_visible() -> bool:
	return _visible_in_dev and not release_mode


func selected_seed() -> int:
	return int(_seed_edit.text) if _seed_edit != null and _seed_edit.text.is_valid_int() else 507


func selected_fixture() -> String:
	return str(_fixture_edit.text) if _fixture_edit != null else "FX-VILLAGE"


func selected_quest() -> String:
	return str(_quest_edit.text) if _quest_edit != null else "quest.factory_shortage"


func selected_puzzle() -> String:
	return str(_puzzle_edit.text) if _puzzle_edit != null else "puzzle.sluice"


func request_launch() -> void:
	launch_requested.emit(selected_seed(), selected_fixture(), selected_quest(), selected_puzzle())


func request_reset() -> void:
	_last_outcome.clear()
	if _debug_facts != null:
		_debug_facts.text = ""
	reset_requested.emit()


func request_replay(bundle_path: String) -> void:
	replay_requested.emit(bundle_path)


func request_export_failure(reason: String) -> void:
	export_failure_requested.emit(reason)


func apply_sandbox_outcome(outcome: Dictionary) -> void:
	## Same outcome dictionary shape the Python scenario runner records.
	_last_outcome = outcome.duplicate(true)


func last_outcome() -> Dictionary:
	return _last_outcome.duplicate(true)


func set_debug_facts_visible(show: bool) -> void:
	_debug_facts_visible = show
	if _debug_facts != null:
		_debug_facts.visible = show and not release_mode


func show_causal_debug(facts: Array, effects: Array) -> void:
	## Causal facts/effects only appear in debug view.
	if not _debug_facts_visible or _debug_facts == null:
		return
	var lines: PackedStringArray = PackedStringArray()
	lines.append("[debug facts]")
	for fact in facts:
		lines.append("- %s" % str(fact))
	lines.append("[debug effects]")
	for effect in effects:
		lines.append("- %s" % str(effect))
	_debug_facts.text = "\n".join(lines)
