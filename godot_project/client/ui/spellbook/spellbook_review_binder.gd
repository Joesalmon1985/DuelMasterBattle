extends RefCounted
class_name SpellbookReviewBinder

## G05 playtest review spellbook — read-only diagnostics + safe review controls.
## Gate fixture mutators (Clear hazard, Set health 25%, Strike, Start delivery) are intentionally absent.

const ModelScript = preload("res://client/ui/spellbook/spellbook_model.gd")
const InfoBinder = preload("res://client/ui/spellbook/spellbook_info_binder.gd")

const CHAPTERS_RES := "res://content/polish/visual_review_chapters.json"

var model = null
var _handlers: Dictionary = {}
var _chapters: Array = []
var _chapter_index := 0
var _review_started := false
var _feedback := ""
var _feedback_note := ""
var _diag: Dictionary = {}


static func review_enabled() -> bool:
	return OS.get_environment("DMB_PLAYTEST_REVIEW") == "1"


func setup(m, session_id: String) -> void:
	model = m
	model.begin_session(session_id)
	_load_chapters()
	if review_enabled():
		model.title = "Playtest / Debug"
		_build_review_pages()
	else:
		model.title = "Spellbook"


func register(action_id: String, handler: Callable) -> void:
	_handlers[action_id] = handler


func set_ready() -> void:
	model.set_connection(ModelScript.ConnState.READY)


func set_disconnected(reason: String = "") -> void:
	model.set_connection(ModelScript.ConnState.DISCONNECTED, reason)


func sync_live(status: String, counters: String, prompt: String, paused: bool) -> void:
	model.set_live(status, counters, prompt, paused)


func append_log(line: String) -> void:
	model.append_log(line)


func bind_player_safe(info: Dictionary) -> void:
	if review_enabled():
		return
	InfoBinder.bind_player_info(model, info)


func refresh_diagnostics(player_view: Dictionary, economy_view: Dictionary) -> void:
	if not review_enabled():
		return
	_diag["place"] = _format_place(player_view)
	_diag["economy"] = _format_economy(player_view, economy_view)
	_diag["factions"] = _format_factions(player_view)
	_diag["conflict"] = _format_conflict(player_view)
	_diag["history"] = _format_history(player_view)
	_diag["evidence"] = _format_evidence(player_view)
	_apply_diag_to_pages()


func handle_action(action_id: String, payload: Dictionary, token: String) -> void:
	if not _handlers.has(action_id):
		model.ack_result(token, ModelScript.ResultKind.REJECTED, "No handler for %s" % action_id, action_id)
		return
	var cb: Callable = _handlers[action_id]
	var reply = cb.call(payload)
	_ack_from_reply(action_id, token, reply)


func current_chapter() -> Dictionary:
	if _chapters.is_empty():
		return {}
	return _chapters[_chapter_index]


func chapter_count() -> int:
	return _chapters.size()


func chapter_index() -> int:
	return _chapter_index


func set_chapter_index(idx: int) -> void:
	if _chapters.is_empty():
		return
	_chapter_index = clampi(idx, 0, _chapters.size() - 1)
	_rebuild_review_page()
	model.emit_signal("changed")


func feedback_label() -> String:
	return _feedback


func _load_chapters() -> void:
	_chapters = []
	if not FileAccess.file_exists(CHAPTERS_RES):
		append_log("missing chapters file: %s" % CHAPTERS_RES)
		return
	var text := FileAccess.get_file_as_string(CHAPTERS_RES)
	var parsed = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		append_log("invalid chapters JSON")
		return
	var arr: Array = parsed.get("chapters", [])
	for entry in arr:
		if typeof(entry) == TYPE_DICTIONARY:
			_chapters.append(entry)


func _build_review_pages() -> void:
	var pages: Array = [
		{
			"id": "review",
			"title": "Review",
			"kind": "actions",
			"body": _review_body(),
			"actions": _review_actions(),
		},
		{"id": "place", "title": "This place", "kind": "info", "body": _diag.get("place", ""), "actions": []},
		{"id": "economy", "title": "Economy", "kind": "info", "body": _diag.get("economy", ""), "actions": []},
		{"id": "factions", "title": "Factions/tech", "kind": "info", "body": _diag.get("factions", ""), "actions": []},
		{
			"id": "conflict",
			"title": "Conflict/hazards",
			"kind": "info",
			"body": _diag.get("conflict", ""),
			"actions": [],
		},
		{"id": "history", "title": "History", "kind": "info", "body": _diag.get("history", ""), "actions": []},
		{
			"id": "evidence",
			"title": "Evidence",
			"kind": "actions",
			"body": _diag.get("evidence", ""),
			"actions": [{"id": "capture_issue", "label": "Capture issue"}],
		},
	]
	model.set_pages(pages, "review")


func _apply_diag_to_pages() -> void:
	if model == null or model.pages.is_empty():
		return
	for i in model.pages.size():
		var p: Dictionary = model.pages[i]
		var pid := str(p.get("id", ""))
		if _diag.has(pid):
			p["body"] = _diag[pid]
			model.pages[i] = p
	_rebuild_review_page()


func _rebuild_review_page() -> void:
	if model == null or model.pages.is_empty():
		return
	for i in model.pages.size():
		if str(model.pages[i].get("id", "")) == "review":
			var p: Dictionary = model.pages[i]
			p["body"] = _review_body()
			p["actions"] = _review_actions()
			model.pages[i] = p
			break


func _review_body() -> String:
	var ch: Dictionary = current_chapter()
	var lines: PackedStringArray = PackedStringArray()
	if not review_enabled():
		lines.append("Review mode is off.")
		return "\n".join(lines)
	lines.append("Guided visual playtest (read-only diagnostics).")
	lines.append("Session flag: DMB_PLAYTEST_REVIEW=1")
	if not _review_started:
		lines.append("")
		lines.append("Tap Start review to begin chapter 1.")
	else:
		lines.append("")
		lines.append(
			"Chapter %d/%d — %s (%s min)"
			% [_chapter_index + 1, max(1, _chapters.size()), str(ch.get("title", "?")), str(ch.get("minutes", "?"))]
		)
		lines.append(str(ch.get("task", "")))
		var cp := str(ch.get("checkpoint_id", ""))
		if cp != "":
			lines.append("Checkpoint: %s" % cp)
	if _feedback != "":
		lines.append("")
		lines.append("Your rating: %s" % _feedback)
		if _feedback_note != "":
			lines.append(_feedback_note)
	return "\n".join(lines)


func _review_actions() -> Array:
	var load_disabled := str(current_chapter().get("checkpoint_slot", "")) == ""
	return [
		{"id": "review_start", "label": "Start review", "disabled": _review_started},
		{
			"id": "review_load_chapter",
			"label": "Load chapter checkpoint",
			"needs_confirm": true,
			"confirm_label": "Load chapter checkpoint",
			"confirm_body": "Load this chapter's verified save slot? Uses production Load only.",
			"disabled": load_disabled,
			"disabled_reason": "Checkpoint slot not configured yet.",
		},
		{"id": "review_wait", "label": "Wait once"},
		{"id": "review_close_watch", "label": "Close and watch"},
		{"id": "review_feedback_clear", "label": "Mark Clear"},
		{"id": "review_feedback_unclear", "label": "Mark Unclear"},
		{"id": "review_feedback_broken", "label": "Mark Broken"},
		{"id": "review_replay", "label": "Replay chapter"},
		{"id": "review_next", "label": "Next chapter"},
		{"id": "capture_issue", "label": "Capture issue"},
	]


func mark_review_started() -> void:
	_review_started = true
	_rebuild_review_page()
	model.emit_signal("changed")


func set_feedback(kind: String, note: String = "") -> void:
	_feedback = kind
	_feedback_note = note
	_rebuild_review_page()
	model.emit_signal("changed")


func export_issue_context() -> Dictionary:
	var ch: Dictionary = current_chapter()
	return {
		"chapter_id": str(ch.get("id", "")),
		"chapter_index": _chapter_index,
		"feedback": _feedback,
		"feedback_note": _feedback_note,
		"checkpoint_id": str(ch.get("checkpoint_id", "")),
		"diagnostics": _diag.duplicate(true),
	}


func _format_place(view: Dictionary) -> String:
	var player: Dictionary = _dict(view.get("player"))
	var clock: Dictionary = _dict(view.get("clock"))
	var area: Dictionary = _dict(view.get("overworld_area"))
	var lines: PackedStringArray = PackedStringArray()
	lines.append("Turn %s · game_ms %s" % [str(clock.get("turn", "?")), str(clock.get("game_ms", "?"))])
	lines.append("Player node: %s · area: %s" % [str(player.get("node_id", "?")), str(player.get("area_id", "?"))])
	if not area.is_empty():
		lines.append("Area name: %s" % str(area.get("name", area.get("id", "?"))))
	var people: Dictionary = _dict(view.get("people"))
	if not people.is_empty():
		lines.append("People tracked: %d" % people.size())
	return "\n".join(lines)


func _format_economy(player_view: Dictionary, economy_view: Dictionary) -> String:
	var view: Dictionary = economy_view if not economy_view.is_empty() else player_view
	var stocks: Dictionary = _dict(view.get("stocks"))
	var carts: Dictionary = _dict(view.get("carts"))
	var orders: Dictionary = _dict(view.get("orders"))
	var lines: PackedStringArray = PackedStringArray()
	if stocks.is_empty():
		lines.append("No stock snapshot in view.")
	else:
		lines.append("Stock keys: %d" % stocks.size())
		var shown := 0
		for k in stocks.keys():
			if shown >= 6:
				break
			lines.append("  %s: %s" % [str(k), _short(stocks[k])])
			shown += 1
	if carts.is_empty():
		lines.append("No carts in view.")
	else:
		lines.append("Carts: %d" % carts.size())
		for cid in carts.keys():
			var c: Dictionary = _dict(carts[cid])
			lines.append(
				"  %s cargo=%s node=%s"
				% [str(cid), _short(c.get("cargo", c.get("load", "?"))), str(c.get("node_id", "?"))]
			)
	if not orders.is_empty():
		lines.append("Open orders: %d" % orders.size())
	return "\n".join(lines)


func _format_factions(view: Dictionary) -> String:
	var lines: PackedStringArray = PackedStringArray()
	var research = view.get("research", null)
	var draft = view.get("draft", null)
	var diplomacy = view.get("diplomacy", null)
	var policies = view.get("policies", null)
	if research == null and draft == null and diplomacy == null and policies == null:
		lines.append("No faction/technology fields in current player view.")
		lines.append("(Request scopes may expand as checkpoints land.)")
	else:
		if research != null:
			lines.append("Research: %s" % _short(research))
		if draft != null:
			lines.append("Draft: %s" % _short(draft))
		if diplomacy != null:
			lines.append("Diplomacy: %s" % _short(diplomacy))
		if policies != null:
			lines.append("Policies: %s" % _short(policies))
	var battles: Dictionary = _dict(view.get("battles"))
	if not battles.is_empty():
		lines.append("Battles entries: %d" % battles.size())
	return "\n".join(lines)


func _format_conflict(view: Dictionary) -> String:
	var lines: PackedStringArray = PackedStringArray()
	var hazards: Dictionary = _dict(view.get("hazards"))
	var fx_h: Dictionary = _dict(view.get("fx_hazard"))
	if hazards.is_empty() and fx_h.is_empty():
		lines.append("No hazard payload in view.")
	else:
		if not hazards.is_empty():
			lines.append("Hazards: %s" % _short(hazards))
		if not fx_h.is_empty():
			lines.append("FX hazard: %s" % _short(fx_h))
	var units: Dictionary = _dict(view.get("units"))
	if not units.is_empty():
		lines.append("Units: %d" % units.size())
	var battles: Dictionary = _dict(view.get("battles"))
	if not battles.is_empty():
		lines.append("Battles: %s" % _short(battles))
	return "\n".join(lines)


func _format_history(view: Dictionary) -> String:
	var chronicle = view.get("chronicle", [])
	var lines: PackedStringArray = PackedStringArray()
	if typeof(chronicle) != TYPE_ARRAY or chronicle.is_empty():
		lines.append("Chronicle empty or unavailable.")
	else:
		var n := mini(chronicle.size(), 12)
		for i in range(n):
			lines.append("- %s" % _short(chronicle[i]))
		if chronicle.size() > n:
			lines.append("… %d more" % (chronicle.size() - n))
	var era = view.get("fx_era", view.get("era", null))
	if era != null:
		lines.append("Era: %s" % _short(era))
	return "\n".join(lines)


func _format_evidence(view: Dictionary) -> String:
	var clock: Dictionary = _dict(view.get("clock"))
	var lines: PackedStringArray = PackedStringArray()
	lines.append("Read-only evidence export uses production view snapshots.")
	lines.append("Turn %s · seq %s" % [str(clock.get("turn", "?")), str(clock.get("clock_sequence", "?"))])
	lines.append("Use Capture issue to write a report under logs/polish_review/.")
	return "\n".join(lines)


func _dict(value) -> Dictionary:
	return value if typeof(value) == TYPE_DICTIONARY else {}


func _short(value, limit: int = 160) -> String:
	var s := str(value)
	if s.length() <= limit:
		return s
	return s.substr(0, limit - 1) + "…"


func _ack_from_reply(action_id: String, token: String, reply) -> void:
	if reply == null:
		model.ack_result(token, ModelScript.ResultKind.SUCCESS, "Done", action_id)
		return
	if typeof(reply) != TYPE_DICTIONARY:
		model.ack_result(token, ModelScript.ResultKind.SUCCESS, str(reply), action_id)
		return
	var status := str(reply.get("status", ""))
	var text := str(reply.get("public_feedback", reply.get("code", reply.get("message", status))))
	if status == "REJECTED":
		model.ack_result(token, ModelScript.ResultKind.REJECTED, text if text != "" else "Rejected", action_id)
		return
	if status == "ACCEPTED" or status == "OK" or status == "" or not reply.has("status"):
		model.ack_result(token, ModelScript.ResultKind.SUCCESS, text if text != "" else "Accepted", action_id)
		return
	model.ack_result(token, ModelScript.ResultKind.SUCCESS, text if text != "" else status, action_id)
