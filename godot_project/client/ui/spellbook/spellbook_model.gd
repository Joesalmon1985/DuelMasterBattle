extends RefCounted
class_name SpellbookModel

## Presentation data + action lifecycle. Does not own simulation state.

enum ConnState { LOADING, READY, DISCONNECTED, ERROR }
enum ResultKind { NONE, PENDING, SUCCESS, REJECTED, TIMEOUT, DISCONNECTED, CANCELLED }
enum HostMode { COMPACT, OPEN, TARGETING }

signal changed
signal action_requested(action_id: String, payload: Dictionary, token: String)
signal targeting_cancelled(action_id: String)
signal close_requested
signal exit_menu_requested
signal classic_hud_toggled(enabled: bool)
signal page_changed(page_id: String)

var session_id: String = ""
var conn_state: int = ConnState.LOADING
var host_mode: int = HostMode.COMPACT
var classic_hud: bool = false
var title: String = "Spellbook"
var status_line: String = ""
var counters_line: String = ""
var prompt_line: String = ""
var paused_badge: bool = false
var pages: Array = []  # Array of {id, title, body, actions, kind}
var page_index: int = 0
var log_lines: PackedStringArray = PackedStringArray()
var result_kind: int = ResultKind.NONE
var result_text: String = ""
var result_token: String = ""
var result_action_id: String = ""
var pending_token: String = ""
var pending_action_id: String = ""
var pending_started_msec: int = 0
var targeting: Dictionary = {}  # action_id, label, guidance, payload
var confirm_pending: Dictionary = {}  # action_id, label, payload
var text_scale_note: String = ""
var empty_reason: String = ""
var error_reason: String = ""

var _token_seq: int = 0
var _seen_tokens: Dictionary = {}  # token -> true (completed)
var _ignore_world_until_msec: int = 0


func begin_session(id: String) -> void:
	session_id = id
	_token_seq = 0
	_seen_tokens.clear()
	clear_result()
	pending_token = ""
	pending_action_id = ""
	targeting.clear()
	confirm_pending.clear()
	host_mode = HostMode.COMPACT
	emit_signal("changed")


func set_connection(state: int, reason: String = "") -> void:
	conn_state = state
	error_reason = reason if state == ConnState.ERROR else ""
	if state == ConnState.DISCONNECTED:
		_fail_pending(ResultKind.DISCONNECTED, "Disconnected — command not acknowledged")
	emit_signal("changed")


func set_live(status: String, counters: String, prompt: String, paused: bool) -> void:
	status_line = status
	counters_line = counters
	prompt_line = prompt
	paused_badge = paused
	emit_signal("changed")


func set_pages(new_pages: Array, prefer_id: String = "") -> void:
	pages = new_pages
	if prefer_id != "":
		for i in pages.size():
			if str(pages[i].get("id", "")) == prefer_id:
				page_index = i
				emit_signal("changed")
				return
	page_index = clampi(page_index, 0, max(0, pages.size() - 1))
	emit_signal("changed")


func current_page() -> Dictionary:
	if pages.is_empty():
		return {}
	return pages[page_index]


func goto_page(index: int) -> void:
	if pages.is_empty():
		return
	page_index = clampi(index, 0, pages.size() - 1)
	emit_signal("page_changed", str(current_page().get("id", "")))
	emit_signal("changed")


func next_page() -> void:
	goto_page(page_index + 1)


func prev_page() -> void:
	goto_page(page_index - 1)


func append_log(line: String) -> void:
	log_lines.append(line)
	if log_lines.size() > 200:
		log_lines = log_lines.slice(log_lines.size() - 200)
	emit_signal("changed")


func clear_result() -> void:
	result_kind = ResultKind.NONE
	result_text = ""
	result_token = ""
	result_action_id = ""


func mint_token(action_id: String) -> String:
	_token_seq += 1
	return "%s:%s:%d:%d" % [session_id, action_id, _token_seq, Time.get_ticks_msec()]


func request_action(action_id: String, payload: Dictionary = {}, opts: Dictionary = {}) -> void:
	if pending_token != "":
		append_log("ignored overlapping action while pending: %s" % action_id)
		return
	if bool(opts.get("needs_confirm", false)):
		confirm_pending = {
			"action_id": action_id,
			"label": str(opts.get("confirm_label", action_id)),
			"payload": payload.duplicate(true),
			"body": str(opts.get("confirm_body", "Are you sure?")),
		}
		emit_signal("changed")
		return
	if bool(opts.get("needs_target", false)):
		begin_targeting(action_id, payload, opts)
		return
	_dispatch(action_id, payload)


func confirm_yes() -> void:
	if confirm_pending.is_empty():
		return
	var a := str(confirm_pending.get("action_id", ""))
	var p: Dictionary = confirm_pending.get("payload", {})
	confirm_pending.clear()
	_dispatch(a, p)


func confirm_no() -> void:
	confirm_pending.clear()
	_set_result(ResultKind.CANCELLED, "", "Confirmation cancelled", "")
	emit_signal("changed")


func begin_targeting(action_id: String, payload: Dictionary, opts: Dictionary = {}) -> void:
	host_mode = HostMode.TARGETING
	targeting = {
		"action_id": action_id,
		"label": str(opts.get("target_label", action_id)),
		"guidance": str(opts.get("target_guidance", "Select a valid target in the world.")),
		"payload": payload.duplicate(true),
	}
	# Swallow the selecting press so it cannot also pick a world target.
	_ignore_world_until_msec = Time.get_ticks_msec() + 220
	emit_signal("changed")


func world_input_blocked_for_select() -> bool:
	return Time.get_ticks_msec() < _ignore_world_until_msec


func cancel_targeting() -> void:
	var aid := str(targeting.get("action_id", ""))
	targeting.clear()
	host_mode = HostMode.COMPACT
	_set_result(ResultKind.CANCELLED, aid, "Targeting cancelled — no effect", "")
	emit_signal("targeting_cancelled", aid)
	emit_signal("changed")


func complete_targeting(target_id: String, extra: Dictionary = {}) -> void:
	if targeting.is_empty():
		return
	if world_input_blocked_for_select():
		return
	var aid := str(targeting.get("action_id", ""))
	var payload: Dictionary = targeting.get("payload", {}).duplicate(true)
	payload["target_id"] = target_id
	for k in extra.keys():
		payload[k] = extra[k]
	targeting.clear()
	host_mode = HostMode.COMPACT
	_dispatch(aid, payload)


func open_book() -> void:
	if host_mode == HostMode.TARGETING:
		return
	host_mode = HostMode.OPEN
	emit_signal("changed")


func close_book() -> void:
	# Early-return when already compact so close_requested handlers cannot recurse.
	if host_mode == HostMode.COMPACT:
		return
	if host_mode == HostMode.TARGETING:
		cancel_targeting()
		return
	host_mode = HostMode.COMPACT
	confirm_pending.clear()
	emit_signal("close_requested")
	emit_signal("changed")


func request_exit_menu() -> void:
	emit_signal("exit_menu_requested")


func toggle_classic_hud() -> void:
	classic_hud = not classic_hud
	emit_signal("classic_hud_toggled", classic_hud)
	emit_signal("changed")


func ack_result(token: String, kind: int, text: String, action_id: String = "") -> void:
	if token == "":
		return
	if _seen_tokens.has(token):
		return
	if pending_token != "" and token != pending_token:
		# Stale reply from an earlier action — log but do not overwrite current result.
		append_log("stale reply ignored for token %s" % token)
		return
	_seen_tokens[token] = true
	pending_token = ""
	pending_action_id = ""
	pending_started_msec = 0
	_set_result(kind, action_id, text, token)
	emit_signal("changed")


func tick_timeout(timeout_ms: int = 8000) -> void:
	if pending_token == "":
		return
	if Time.get_ticks_msec() - pending_started_msec < timeout_ms:
		return
	var tok := pending_token
	var aid := pending_action_id
	pending_token = ""
	pending_action_id = ""
	_set_result(ResultKind.TIMEOUT, aid, "Timed out waiting for acknowledgement", tok)
	_seen_tokens[tok] = true
	emit_signal("changed")


func result_label() -> String:
	match result_kind:
		ResultKind.PENDING:
			return "Pending"
		ResultKind.SUCCESS:
			return "Success"
		ResultKind.REJECTED:
			return "Rejected"
		ResultKind.TIMEOUT:
			return "Timeout"
		ResultKind.DISCONNECTED:
			return "Disconnected"
		ResultKind.CANCELLED:
			return "Cancelled"
		_:
			return ""


func conn_label() -> String:
	match conn_state:
		ConnState.LOADING:
			return "Loading…"
		ConnState.READY:
			return "Connected"
		ConnState.DISCONNECTED:
			return "Disconnected"
		ConnState.ERROR:
			return "Error"
		_:
			return "?"


func _dispatch(action_id: String, payload: Dictionary) -> void:
	var token := mint_token(action_id)
	pending_token = token
	pending_action_id = action_id
	pending_started_msec = Time.get_ticks_msec()
	_set_result(ResultKind.PENDING, action_id, "Waiting for acknowledgement…", token)
	emit_signal("changed")
	emit_signal("action_requested", action_id, payload, token)


func _fail_pending(kind: int, text: String) -> void:
	if pending_token == "":
		return
	var tok := pending_token
	var aid := pending_action_id
	pending_token = ""
	pending_action_id = ""
	_seen_tokens[tok] = true
	_set_result(kind, aid, text, tok)


func _set_result(kind: int, action_id: String, text: String, token: String) -> void:
	result_kind = kind
	result_action_id = action_id
	result_text = text
	result_token = token
