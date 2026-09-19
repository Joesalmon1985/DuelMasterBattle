extends RefCounted
class_name SpellbookGateBinder

## Builds SpellbookModel pages for gate shells and maps action ids to shell callables.

const ModelScript = preload("res://client/ui/spellbook/spellbook_model.gd")

var model = null
var _handlers: Dictionary = {}  # action_id -> Callable


func setup(m, session: String, title: String) -> void:
	model = m
	model.begin_session(session)
	model.title = title
	model.set_connection(ModelScript.ConnState.LOADING)


func register(action_id: String, handler: Callable) -> void:
	_handlers[action_id] = handler


func set_ready() -> void:
	model.set_connection(ModelScript.ConnState.READY)


func set_error(reason: String) -> void:
	model.set_connection(ModelScript.ConnState.ERROR, reason)


func set_disconnected(reason: String = "") -> void:
	model.set_connection(ModelScript.ConnState.DISCONNECTED, reason)


func sync_live(status: String, counters: String, prompt: String, paused: bool) -> void:
	model.set_live(status, counters, prompt, paused)


func append_log(line: String) -> void:
	model.append_log(line)


func build_g01_pages() -> void:
	var pages: Array = [
		{
			"id": "status",
			"title": "Status",
			"kind": "info",
			"body": "Live Python-backed FX-CLOCK state. Viewing only — use Actions to change state.",
			"actions": [],
		},
		{
			"id": "actions",
			"title": "Actions",
			"kind": "actions",
			"body": "Commands run through the existing WorldClient path. Results appear only after acknowledgement.",
			"actions": [
				{"id": "wait", "label": "Wait"},
				{"id": "invalid_exit", "label": "Invalid exit"},
				{"id": "pause", "label": "Pause"},
				{"id": "resume", "label": "Resume"},
				{"id": "save", "label": "Save"},
				{"id": "load", "label": "Load", "needs_confirm": true, "confirm_label": "Load save",
					"confirm_body": "Load slot and replace the current world state?"},
			],
		},
		{
			"id": "troubleshoot",
			"title": "Troubleshoot",
			"kind": "actions",
			"body": "Destructive or recovery tools. Classic HUD restores the original bottom action bar.",
			"actions": [
				{"id": "bridge_fail", "label": "Bridge fail", "destructive": true, "needs_confirm": true,
					"confirm_label": "Simulate bridge failure",
					"confirm_body": "Kill the sidecar and attempt checkpoint recovery?"},
				{"id": "toggle_classic", "label": "Toggle Classic HUD"},
				{"id": "toggle_diag", "label": "Toggle Dev log panel"},
			],
		},
		{
			"id": "log",
			"title": "Log",
			"kind": "log",
			"body": "",
			"actions": [],
		},
	]
	model.set_pages(pages, "status")


func build_g02_pages() -> void:
	build_g01_pages()
	var pages: Array = model.pages.duplicate(true)
	pages.insert(2, {
		"id": "economy",
		"title": "Economy",
		"kind": "actions",
		"body": "Cargo route controls. Viewing stock/cart uses world Interact; route tools mutate simulation.",
		"actions": [
			{"id": "eco_start", "label": "Start delivery"},
			{"id": "eco_block", "label": "Block route"},
			{"id": "eco_clear", "label": "Clear hazard"},
		],
	})
	model.set_pages(pages, "economy")


func build_g03_pages() -> void:
	build_g01_pages()
	var pages: Array = model.pages.duplicate(true)
	pages.insert(2, {
		"id": "industry",
		"title": "Industry",
		"kind": "actions",
		"body": "Industry inspector actions. Path block is presentation-only.",
		"actions": [
			{"id": "ind_damage", "label": "Set health to 25%", "destructive": true, "needs_confirm": true,
				"confirm_label": "Damage industry", "confirm_body": "Set focused processor health to 25%?"},
			{"id": "ind_strike", "label": "Strike"},
			{"id": "ind_clear_strike", "label": "Clear strike"},
			{"id": "ind_repair", "label": "Paid repair"},
			{"id": "ind_path_block", "label": "Toggle path block (presentation)"},
		],
	})
	model.set_pages(pages, "industry")


func build_g04_battle_pages() -> void:
	build_g01_pages()
	var pages: Array = model.pages.duplicate(true)
	pages.insert(2, {
		"id": "spells",
		"title": "Spells",
		"kind": "actions",
		"presentation": "battle_spells",
		"body": "Destroy · Shield · Attack Speed · Range — tap a spell, then a unit.",
		"actions": [
			{"id": "spell_destroy", "label": "Destroy", "needs_target": true,
				"target_label": "Destroy", "target_guidance": "Tap a unit in the battle to destroy it. Cancel applies no effect."},
			{"id": "spell_shield", "label": "Shield", "needs_target": true,
				"target_label": "Shield", "target_guidance": "Tap a unit to apply Shield."},
			{"id": "spell_frequency", "label": "Attack Speed", "needs_target": true,
				"target_label": "Attack Speed", "target_guidance": "Tap a unit to buff attack speed."},
			{"id": "spell_range", "label": "Range", "needs_target": true,
				"target_label": "Range", "target_guidance": "Tap a unit to buff range."},
		],
	})
	model.set_pages(pages, "spells")


func build_g04_hazard_pages() -> void:
	build_g01_pages()
	var pages: Array = model.pages.duplicate(true)
	pages.insert(2, {
		"id": "hazard",
		"title": "Hazard",
		"kind": "actions",
		"body": "Catastrophe treatment. Treat needs a world hazard target; Channel/Falter run during an open duel.",
		"actions": [
			{"id": "hazard_treat", "label": "Treat (duel)", "needs_target": true,
				"target_label": "Treat", "target_guidance": "Tap a treatable hazard hex. World time freezes for the duel."},
			{"id": "hazard_channel", "label": "Channel"},
			{"id": "hazard_falter", "label": "Falter", "destructive": true, "needs_confirm": true,
				"confirm_label": "Falter", "confirm_body": "Falter can fail the duel. Continue?"},
		],
	})
	model.set_pages(pages, "hazard")


func handle_action(action_id: String, payload: Dictionary, token: String) -> void:
	if not _handlers.has(action_id):
		model.ack_result(token, ModelScript.ResultKind.REJECTED, "No handler for %s" % action_id, action_id)
		return
	if action_id == "toggle_classic":
		model.toggle_classic_hud()
		model.ack_result(token, ModelScript.ResultKind.SUCCESS, "Classic HUD %s" % ("shown" if model.classic_hud else "hidden"), action_id)
		return
	var cb: Callable = _handlers[action_id]
	var reply = cb.call(payload)
	_ack_from_reply(action_id, token, reply)


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
