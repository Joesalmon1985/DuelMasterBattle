extends RefCounted
class_name SpellbookReviewBinder

## G05 playtest review spellbook — read-only diagnostics + safe review controls.
## Gate fixture mutators (Clear hazard, Set health 25%, Strike, Start delivery) are intentionally absent.
##
## Explicit review projection schema (privileged; only when DMB_PLAYTEST_REVIEW=1):
##   place | industry | economy | factions | conflict | history | evidence
## Distinguishes zero / no event yet / unavailable / loading. Never prints '?' when
## authoritative data exists. Normal Play Latest uses bind_player_safe only.

const ModelScript = preload("res://client/ui/spellbook/spellbook_model.gd")
const InfoBinder = preload("res://client/ui/spellbook/spellbook_info_binder.gd")

const CHAPTERS_RES := "res://content/polish/visual_review_chapters.json"
const REVIEW_SCHEMA_VERSION := 1

var model = null
var _handlers: Dictionary = {}
var _chapters: Array = []
var _chapter_index := 0
var _review_started := false
var _feedback := ""
var _feedback_note := ""
var _diag: Dictionary = {}
var _detail_open: Dictionary = {}


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
	_diag["industry"] = _format_industry(player_view, economy_view)
	_diag["economy"] = _format_economy(player_view, economy_view)
	_diag["factions"] = _format_factions(player_view, economy_view)
	_diag["conflict"] = _format_conflict(player_view)
	_diag["history"] = _format_history(player_view)
	_diag["evidence"] = _format_evidence(player_view)
	_apply_diag_to_pages()


func handle_action(action_id: String, payload: Dictionary, token: String) -> void:
	if action_id.begins_with("detail_"):
		var key := action_id.substr(7)
		_detail_open[key] = not bool(_detail_open.get(key, false))
		_apply_diag_to_pages()
		model.ack_result(token, ModelScript.ResultKind.SUCCESS, "Detail toggled", action_id)
		model.emit_signal("changed")
		return
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
		{"id": "place", "title": "Here", "kind": "info", "body": _diag.get("place", "Loading…"), "actions": []},
		{"id": "industry", "title": "Industry", "kind": "info", "body": _diag.get("industry", "Loading…"), "actions": []},
		{"id": "economy", "title": "Economy", "kind": "info", "body": _diag.get("economy", "Loading…"), "actions": []},
		{"id": "factions", "title": "Factions", "kind": "info", "body": _diag.get("factions", "Loading…"), "actions": []},
		{"id": "conflict", "title": "Conflict", "kind": "info", "body": _diag.get("conflict", "Loading…"), "actions": []},
		{"id": "history", "title": "History", "kind": "info", "body": _diag.get("history", "Loading…"), "actions": []},
		{
			"id": "evidence",
			"title": "Evidence",
			"kind": "actions",
			"body": _diag.get("evidence", "Loading…"),
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
			if pid != "review" and pid != "evidence":
				p["actions"] = [
					{
						"id": "detail_%s" % pid,
						"label": "Less detail" if bool(_detail_open.get(pid, false)) else "More detail",
					}
				]
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
	lines.append("Guided visual playtest (schema v%d)." % REVIEW_SCHEMA_VERSION)
	lines.append("Session flag: DMB_PLAYTEST_REVIEW=1")
	if not _review_started:
		lines.append("")
		lines.append("Tap Start review to begin chapter 1.")
	else:
		lines.append("")
		lines.append(
			"Chapter %d/%d — %s (%s min)"
			% [_chapter_index + 1, max(1, _chapters.size()), str(ch.get("title", "—")), str(ch.get("minutes", "—"))]
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
		"review_schema_version": REVIEW_SCHEMA_VERSION,
		"diagnostics": _diag.duplicate(true),
	}


func _format_place(view: Dictionary) -> String:
	var player: Dictionary = _dict(view.get("player"))
	var clock: Dictionary = _dict(view.get("clock"))
	var area: Dictionary = _dict(view.get("overworld_area"))
	var lines: PackedStringArray = PackedStringArray()
	lines.append("Turn %s · game time %s ms" % [_val(clock, "turn"), _val(clock, "game_ms")])
	lines.append("Place: %s" % _val(player, "node_id", "no event yet"))
	lines.append("Area: %s" % _val(area, "name", _val(player, "area_id", "unavailable")))
	var people: Dictionary = _dict(view.get("people"))
	if people.is_empty():
		lines.append("People: none in view yet")
	else:
		lines.append("People tracked: %d" % people.size())
		if bool(_detail_open.get("place", false)):
			var n := 0
			for pid in people.keys():
				if n >= 8:
					break
				var rec: Dictionary = _dict(people[pid])
				lines.append("  %s — %s" % [str(pid), _val(rec, "name", _val(rec, "role", "person"))])
				n += 1
	var knowledge = view.get("knowledge", null)
	if knowledge == null:
		lines.append("Learned facts: unavailable in this view")
	elif typeof(knowledge) == TYPE_ARRAY and knowledge.is_empty():
		lines.append("Learned facts: none yet")
	elif typeof(knowledge) == TYPE_ARRAY:
		lines.append("Learned facts: %d" % knowledge.size())
	return "\n".join(lines)


func _format_industry(player_view: Dictionary, economy_view: Dictionary) -> String:
	var view: Dictionary = economy_view if not economy_view.is_empty() else player_view
	var factories = view.get("industry_factories", null)
	var lines: PackedStringArray = PackedStringArray()
	if factories == null:
		lines.append("Factories: unavailable")
		return "\n".join(lines)
	if typeof(factories) == TYPE_ARRAY and factories.is_empty():
		lines.append("Factories: none yet")
	elif typeof(factories) == TYPE_DICTIONARY and factories.is_empty():
		lines.append("Factories: none yet")
	else:
		var rows: Array = factories if typeof(factories) == TYPE_ARRAY else factories.values()
		lines.append("Factories: %d" % rows.size())
		for raw in rows:
			if typeof(raw) != TYPE_DICTIONARY:
				continue
			var f: Dictionary = raw
			lines.append(
				"  %s → %s"
				% [_val(f, "name", _val(f, "building_id", "factory")), _val(f, "output", _val(f, "produces", "—"))]
			)
			lines.append(
				"    rate %s · progress %s · last → %s"
				% [
					_val(f, "rate", _val(f, "cycle_ms", "—")),
					_val(f, "progress", _val(f, "progress_ms", "0")),
					_val(f, "last_output_to", _val(f, "last_person_id", "no event yet")),
				]
			)
			if bool(_detail_open.get("industry", false)):
				lines.append("    person=%s unit=%s formation=%s" % [
					_val(f, "person_id", "—"),
					_val(f, "unit_id", "—"),
					_val(f, "formation_id", "—"),
				])
				lines.append("    inputs: %s" % _short(f.get("inputs", f.get("recipe", "—"))))
	var workers = view.get("industry_workers", null)
	if workers == null:
		lines.append("Workers: unavailable")
	elif typeof(workers) == TYPE_ARRAY:
		lines.append("Workers: %d" % workers.size())
	elif typeof(workers) == TYPE_DICTIONARY:
		lines.append("Workers: %d" % workers.size())
	return "\n".join(lines)


func _format_economy(player_view: Dictionary, economy_view: Dictionary) -> String:
	var view: Dictionary = economy_view if not economy_view.is_empty() else player_view
	var stocks = view.get("stocks", null)
	var carts = view.get("carts", null)
	var orders = view.get("orders", null)
	var lines: PackedStringArray = PackedStringArray()
	if stocks == null:
		lines.append("Stocks: unavailable")
	elif typeof(stocks) == TYPE_DICTIONARY and stocks.is_empty():
		lines.append("Stocks: empty (zero)")
	elif typeof(stocks) == TYPE_DICTIONARY:
		lines.append("Stock keys: %d" % stocks.size())
		var shown := 0
		for k in stocks.keys():
			if str(k).begins_with("_"):
				continue
			if shown >= 8 and not bool(_detail_open.get("economy", false)):
				break
			lines.append("  %s: %s" % [str(k), _format_stock_entry(stocks[k])])
			shown += 1
	if carts == null:
		lines.append("Carts: unavailable")
	elif typeof(carts) == TYPE_DICTIONARY and carts.is_empty():
		lines.append("Carts: none yet")
	elif typeof(carts) == TYPE_DICTIONARY:
		lines.append("Carts: %d" % carts.size())
		for cid in carts.keys():
			var c: Dictionary = _dict(carts[cid])
			var cargo = c.get("cargo_lots", c.get("cargo", c.get("load", null)))
			var node_id = c.get("current_node", c.get("node_id", null))
			var status := str(c.get("status", "idle"))
			lines.append(
				"  %s @ %s — %s · cargo %s"
				% [str(cid), _present(node_id), status, _present(cargo)]
			)
			if bool(_detail_open.get("economy", false)):
				lines.append("    route=%s reserved=%s" % [_short(c.get("route", "—")), _short(c.get("reservation_id", "—"))])
	if orders == null:
		lines.append("Orders: unavailable")
	elif typeof(orders) == TYPE_DICTIONARY:
		lines.append("Open orders: %d" % orders.size())
		if bool(_detail_open.get("economy", false)):
			var n := 0
			for oid in orders.keys():
				if n >= 6:
					break
				var o: Dictionary = _dict(orders[oid])
				lines.append("  %s status=%s" % [str(oid), _val(o, "status", "—")])
				n += 1
	return "\n".join(lines)


func _format_factions(player_view: Dictionary, economy_view: Dictionary) -> String:
	var view: Dictionary = economy_view if not economy_view.is_empty() else player_view
	var lines: PackedStringArray = PackedStringArray()
	var factions = view.get("factions", null)
	var research = view.get("research", null)
	var draft = view.get("tech_draft", view.get("draft", null))
	var diplomacy = view.get("diplomacy", null)
	var clock: Dictionary = _dict(view.get("clock"))
	lines.append("Seat / turn %s · round %s" % [_val(clock, "turn"), _val(clock, "round", _val(clock, "draft_round", "—"))])
	if factions == null:
		lines.append("Factions: unavailable")
	elif typeof(factions) == TYPE_DICTIONARY and factions.is_empty():
		lines.append("Factions: none yet")
	elif typeof(factions) == TYPE_DICTIONARY:
		lines.append("Factions: %d" % factions.size())
		for fid in factions.keys():
			var f: Dictionary = _dict(factions[fid])
			var policy: Dictionary = _dict(f.get("policy"))
			var brain := _val(policy, "brain", _val(policy, "policy_id", "unassigned"))
			var source := _val(policy, "effective_source", "no event yet")
			var fallback := _val(policy, "fallback_reason", "")
			var hand = f.get("hand", f.get("cards", null))
			var hand_n := "—"
			if typeof(hand) == TYPE_ARRAY:
				hand_n = str(hand.size())
			elif typeof(hand) == TYPE_DICTIONARY:
				hand_n = str(hand.size())
			lines.append("  %s — policy %s · source %s · hand %s" % [str(fid), brain, source, hand_n])
			if fallback != "" and fallback != "—":
				lines.append("    fallback: %s" % fallback)
			var selections: Array = policy.get("selections", [])
			if selections.is_empty():
				lines.append("    last card: no event yet")
			else:
				var last: Dictionary = _dict(selections[selections.size() - 1])
				lines.append(
					"    last pick %s · source %s"
					% [_val(last, "primary_id", "—"), _val(last, "source", source)]
				)
				if bool(_detail_open.get("factions", false)):
					lines.append("    applied: %s" % _short(last.get("applied", "—"), 220))
	if research == null:
		lines.append("Research: unavailable")
	elif typeof(research) == TYPE_DICTIONARY and research.is_empty():
		lines.append("Research: none yet")
	else:
		lines.append("Research: %s" % _short(research, 200 if bool(_detail_open.get("factions", false)) else 120))
	if draft == null:
		lines.append("Tech draft: unavailable")
	elif typeof(draft) == TYPE_DICTIONARY and draft.is_empty():
		lines.append("Tech draft: no event yet")
	else:
		lines.append("Tech draft: %s" % _short(draft, 200 if bool(_detail_open.get("factions", false)) else 120))
	if diplomacy == null:
		lines.append("Diplomacy: unavailable")
	elif typeof(diplomacy) == TYPE_DICTIONARY and diplomacy.is_empty():
		lines.append("Diplomacy: none yet")
	else:
		lines.append("Diplomacy: %s" % _short(diplomacy))
	return "\n".join(lines)


func _format_conflict(view: Dictionary) -> String:
	var lines: PackedStringArray = PackedStringArray()
	var hazards = view.get("hazards", null)
	var fx_h: Dictionary = _dict(view.get("fx_hazard"))
	var units = view.get("units", null)
	var battles = view.get("battles", null)
	if hazards == null:
		lines.append("Hazards: unavailable")
	elif typeof(hazards) == TYPE_DICTIONARY and hazards.is_empty():
		lines.append("Hazards: none on board")
	elif typeof(hazards) == TYPE_DICTIONARY:
		lines.append("Hazards: %d" % hazards.size())
		for hid in hazards.keys():
			var h: Dictionary = _dict(hazards[hid])
			lines.append(
				"  %s type=%s @ %s"
				% [str(hid), _val(h, "type", _val(h, "hazard_type", "—")), _val(h, "node_id", _val(h, "hex_id", "—"))]
			)
	if not fx_h.is_empty():
		lines.append("Last faction treatment: %s" % _short(fx_h, 200 if bool(_detail_open.get("conflict", false)) else 140))
		lines.append("(Faction treatment ≠ wizard Ward Duel.)")
	else:
		lines.append("Last faction treatment: no event yet")
	if units == null:
		lines.append("Units: unavailable")
	elif typeof(units) == TYPE_DICTIONARY:
		lines.append("Units: %d" % units.size())
		if bool(_detail_open.get("conflict", false)):
			var n := 0
			for uid in units.keys():
				if n >= 8:
					break
				var u: Dictionary = _dict(units[uid])
				lines.append(
					"  %s person=%s formation=%s @ %s"
					% [str(uid), _val(u, "person_id", "—"), _val(u, "formation_id", "—"), _val(u, "node_id", "—")]
				)
				n += 1
	if battles == null:
		lines.append("Battles: unavailable")
	elif typeof(battles) == TYPE_DICTIONARY and battles.is_empty():
		lines.append("Battles: none yet")
	elif typeof(battles) == TYPE_DICTIONARY:
		lines.append("Battles: %s" % _short(battles))
	return "\n".join(lines)


func _format_history(view: Dictionary) -> String:
	var lines: PackedStringArray = PackedStringArray()
	var era = view.get("fx_era", view.get("era", null))
	var clock: Dictionary = _dict(view.get("clock"))
	var factions: Dictionary = _dict(view.get("factions"))
	lines.append("Era: %s" % _present(era if era != null else "unavailable"))
	lines.append("Turn %s · game_ms %s" % [_val(clock, "turn"), _val(clock, "game_ms")])
	if factions.is_empty():
		lines.append("Faction scores: unavailable in this view")
	else:
		for fid in factions.keys():
			var f: Dictionary = _dict(factions[fid])
			lines.append("  %s VP %s" % [str(fid), _val(f, "vp", _val(f, "score", "0"))])
	lines.append("Era requires 10 VP (genuine scoring — not an arbitrary Wait count).")
	if era != null and typeof(era) == TYPE_DICTIONARY:
		lines.append("Transition: %s" % _val(era, "status", _val(era, "phase", "no event yet")))
		if bool(_detail_open.get("history", false)):
			lines.append("Detail: %s" % _short(era, 240))
	var chronicle = view.get("chronicle", null)
	if chronicle == null:
		lines.append("Chronicle: unavailable")
	elif typeof(chronicle) != TYPE_ARRAY or chronicle.is_empty():
		lines.append("Chronicle: no event yet")
	else:
		var n := mini(chronicle.size(), 8 if bool(_detail_open.get("history", false)) else 5)
		lines.append("Last history:")
		for i in range(n):
			lines.append("- %s" % _short(chronicle[i]))
		if chronicle.size() > n:
			lines.append("… %d more" % (chronicle.size() - n))
	return "\n".join(lines)


func _format_evidence(view: Dictionary) -> String:
	var clock: Dictionary = _dict(view.get("clock"))
	var lines: PackedStringArray = PackedStringArray()
	lines.append("Read-only evidence export uses production view snapshots.")
	lines.append("Review schema v%d" % REVIEW_SCHEMA_VERSION)
	lines.append("Turn %s · seq %s" % [_val(clock, "turn"), _val(clock, "clock_sequence")])
	lines.append("Capture writes PNG + state/receipt/checkpoint context under logs/polish_review/.")
	return "\n".join(lines)


func _format_stock_entry(value) -> String:
	if typeof(value) != TYPE_DICTIONARY:
		return _present(value)
	var d: Dictionary = value
	if d.has("available") or d.has("reserved"):
		return "avail %s / reserved %s" % [_val(d, "available", "0"), _val(d, "reserved", "0")]
	return _short(d, 80)


func _dict(value) -> Dictionary:
	return value if typeof(value) == TYPE_DICTIONARY else {}


func _val(d: Dictionary, key: String, fallback: String = "—") -> String:
	if not d.has(key) or d[key] == null:
		return fallback
	return str(d[key])


func _present(value) -> String:
	if value == null:
		return "unavailable"
	if typeof(value) == TYPE_ARRAY and value.is_empty():
		return "none yet"
	if typeof(value) == TYPE_DICTIONARY and value.is_empty():
		return "none yet"
	if typeof(value) == TYPE_STRING and value == "":
		return "none yet"
	return _short(value)


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
