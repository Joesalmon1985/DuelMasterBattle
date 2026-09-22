extends SceneTree

## T095 village scenario panel smoke.
## godot --headless --path godot_project --script res://client/tests/run_t095_panel.gd

const ScenarioUI = preload("res://client/debug/scenario_panel.gd")

var _failures: Array = []
var _launched: Array = []


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	await process_frame
	var ui = ScenarioUI.new()
	root.add_child(ui)
	await process_frame
	ui.launch_requested.connect(func(seed, fixture, quest, puzzle): _launched.append([seed, fixture, quest, puzzle]))
	_assert(ui.is_developer_controls_visible(), "dev visible")
	_assert(ui.selected_fixture() == "FX-VILLAGE", "fixture")
	_assert(ui.selected_quest() == "quest.factory_shortage", "quest")
	ui.request_launch()
	_assert(_launched.size() == 1, "launch signal")
	ui.apply_sandbox_outcome({"status": "PASS", "seed": 507, "quest_id": "quest.factory_shortage"})
	_assert(str(ui.last_outcome().get("status", "")) == "PASS", "outcome parity shape")
	ui.set_debug_facts_visible(true)
	ui.show_causal_debug(["cause.factory_shortage"], ["effect.remove_sluice_sabotage"])
	_assert(ui._debug_facts.visible, "debug visible")
	_assert(ui._debug_facts.text.find("cause.factory_shortage") >= 0, "debug facts")
	if _failures.is_empty():
		print("T095_PANEL_OK")
		quit(0)
	else:
		for f in _failures:
			push_error(str(f))
		print("T095_PANEL_FAIL")
		quit(1)


func _assert(cond: bool, msg: String) -> void:
	if not cond:
		_failures.append(msg)
