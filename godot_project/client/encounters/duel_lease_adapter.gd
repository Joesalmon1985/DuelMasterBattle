extends RefCounted
class_name DmbDuelLeaseAdapter

## Hosts retained game_board.tscn + DmbBattleSim under a Python hazard lease.
## Configures the board BEFORE add_child so startup uses lease combatants.
## Does not touch quick-duel or Adventure pending_battle entry points.

const GAME_BOARD_SCENE := preload("res://client/scenes/game_board.tscn")

signal finished(outcome: String, payload: Dictionary)

var _board: Node = null
var _parent: Node = null
var _duel_id: String = ""
var _cmd: Callable = Callable()
var _resolved := false
var resolve_submit_count := 0
var finished_emit_count := 0


func begin_from_start_reply(parent: Node, reply: Dictionary, cmd: Callable) -> bool:
	_parent = parent
	_cmd = cmd
	_resolved = false
	var payload: Dictionary = reply.get("payload", {})
	var public: Dictionary = payload.get("public", {})
	var duel: Dictionary = payload.get("duel", {})
	_duel_id = str(public.get("duel_id", duel.get("id", "")))
	if _duel_id == "":
		return false
	var request: Dictionary = {
		"lease_id": _duel_id,
		"duel_id": _duel_id,
		"cube_id": str(duel.get("cube_id", public.get("cube_id", ""))),
		"kind": str(duel.get("kind", "hazard_ward_duel")),
		"encounter": public.get("encounter", duel.get("encounter", {})),
		"bot_seed": int(public.get("bot_seed", duel.get("bot_seed", 42))),
		"checkpoint": duel.get("checkpoint", {}),
		"forced_defeat_by_cast": 0,
	}
	# Instantiate, configure BEFORE entering the tree, then add_child.
	_board = GAME_BOARD_SCENE.instantiate()
	if _board.has_method("configure_from_lease"):
		_board.configure_from_lease(request, Callable(self, "_on_board_finished"))
	else:
		push_error("GameBoard missing configure_from_lease — cannot host leased duel")
		_board.queue_free()
		_board = null
		return false
	_parent.add_child(_board)
	if _board is Control:
		var board_ctrl: Control = _board
		board_ctrl.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
		board_ctrl.mouse_filter = Control.MOUSE_FILTER_STOP
		if _parent is Control:
			var host_ctrl: Control = _parent
			var host_size: Vector2 = host_ctrl.size
			if host_size == Vector2.ZERO and host_ctrl.get_viewport() != null:
				host_size = host_ctrl.get_viewport().get_visible_rect().size
			if host_size != Vector2.ZERO:
				board_ctrl.set_deferred("size", host_size)
	return true


func is_active() -> bool:
	return _board != null and is_instance_valid(_board)


func _on_board_finished(outcome: String, details: Dictionary = {}) -> void:
	if _resolved:
		return
	_resolved = true
	var success := outcome in ["win", "victory", "success"]
	var resolve_payload := {"duel_id": _duel_id, "success": success, "outcome": outcome}
	resolve_payload.merge(details, true)
	var reply: Dictionary = {}
	if _cmd.is_valid():
		resolve_submit_count += 1
		reply = _cmd.call("ResolveHazardDuel", resolve_payload)
		# Python resolve is idempotent; a duplicate submit must not mutate again.
	finished_emit_count += 1
	finished.emit(outcome, reply if typeof(reply) == TYPE_DICTIONARY else {})
	_teardown()


func submit_checkpoint(checkpoint: Dictionary) -> Dictionary:
	if not _cmd.is_valid() or _duel_id == "":
		return {}
	return _cmd.call("HazardDuelCheckpoint", {
		"duel_id": _duel_id,
		"checkpoint": checkpoint,
	})


func _teardown() -> void:
	if _board != null and is_instance_valid(_board):
		_board.queue_free()
	_board = null
