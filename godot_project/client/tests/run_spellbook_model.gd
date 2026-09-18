extends SceneTree

## Headless SpellbookModel lifecycle checks (no sidecar).

const Model = preload("res://client/ui/spellbook/spellbook_model.gd")
const Binder = preload("res://client/ui/spellbook/spellbook_gate_binder.gd")


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var failures: PackedStringArray = PackedStringArray()
	_check_lifecycle(failures)
	_check_stale_token(failures)
	_check_targeting_cancel(failures)
	_check_close_vs_menu(failures)
	_check_no_auto_retry(failures)
	if failures.is_empty():
		print("SPELLBOOK_MODEL_OK")
		quit(0)
	else:
		for f in failures:
			printerr("FAIL: ", f)
		quit(1)


func _check_lifecycle(failures: PackedStringArray) -> void:
	var m = Model.new()
	m.begin_session("test")
	var seen: Array = []
	m.action_requested.connect(func(a, _p, t): seen.append([a, t]))
	m.request_action("wait", {})
	if m.result_kind != Model.ResultKind.PENDING:
		failures.append("expected PENDING after request")
	if seen.size() != 1:
		failures.append("expected one action_requested")
	var token: String = seen[0][1]
	m.ack_result(token, Model.ResultKind.SUCCESS, "Wait accepted", "wait")
	if m.result_kind != Model.ResultKind.SUCCESS:
		failures.append("expected SUCCESS after ack")
	if m.pending_token != "":
		failures.append("pending should clear after ack")


func _check_stale_token(failures: PackedStringArray) -> void:
	var m = Model.new()
	m.begin_session("stale")
	var tokens: Array = []
	m.action_requested.connect(func(_a, _p, t): tokens.append(t))
	m.request_action("save", {})
	var t1: String = tokens[0]
	# Simulate reopen: clear pending without completing, then new action
	# Closing must not resend — we only mint on request_action.
	m.ack_result(t1, Model.ResultKind.SUCCESS, "Saved", "save")
	m.request_action("load", {})
	var t2: String = tokens[1]
	m.ack_result(t1, Model.ResultKind.SUCCESS, "old save", "save")
	if m.result_action_id != "load" and m.pending_token == t2:
		pass  # still pending load
	if m.result_kind == Model.ResultKind.SUCCESS and m.result_action_id == "save" and m.pending_token == t2:
		failures.append("stale save ack overwrote pending load result")
	# Complete load
	m.ack_result(t2, Model.ResultKind.SUCCESS, "Loaded", "load")
	if m.result_action_id != "load":
		failures.append("load result missing after valid ack")


func _check_targeting_cancel(failures: PackedStringArray) -> void:
	var m = Model.new()
	m.begin_session("tgt")
	var cancelled := [false]
	m.targeting_cancelled.connect(func(_a): cancelled[0] = true)
	m.begin_targeting("spell_destroy", {}, {"target_label": "Destroy", "target_guidance": "tap unit"})
	if m.host_mode != Model.HostMode.TARGETING:
		failures.append("expected TARGETING mode")
	if not m.world_input_blocked_for_select():
		failures.append("expected world select guard after entering targeting")
	m.cancel_targeting()
	if not cancelled[0]:
		failures.append("cancel should emit targeting_cancelled")
	if m.result_kind != Model.ResultKind.CANCELLED:
		failures.append("cancel should set CANCELLED result")
	if m.host_mode != Model.HostMode.COMPACT:
		failures.append("cancel should return to COMPACT")


func _check_close_vs_menu(failures: PackedStringArray) -> void:
	var m = Model.new()
	m.begin_session("nav")
	var closes := [0]
	var exits := [0]
	m.close_requested.connect(func(): closes[0] += 1)
	m.exit_menu_requested.connect(func(): exits[0] += 1)
	m.open_book()
	m.close_book()
	m.close_book()  # already COMPACT — must not recurse / re-emit
	m.request_exit_menu()
	if closes[0] != 1:
		failures.append("Close book should emit close_requested once (got %d)" % closes[0])
	if exits[0] != 1:
		failures.append("Exit to menu must be a separate signal")


func _check_no_auto_retry(failures: PackedStringArray) -> void:
	var m = Model.new()
	m.begin_session("retry")
	var count := [0]
	m.action_requested.connect(func(_a, _p, _t): count[0] += 1)
	m.request_action("wait", {})
	m.open_book()
	m.close_book()
	m.open_book()
	if count[0] != 1:
		failures.append("open/close must not resend state-changing commands (got %d)" % count[0])
