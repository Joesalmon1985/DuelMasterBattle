extends RefCounted
class_name DmbMagicTargeting

## Client targeting validation mirror for wizard destruction/buffs (C07).

var local_node_id: String = ""
var observed_ids: Array = []


func set_context(node_id: String, observed: Array) -> void:
	local_node_id = node_id
	observed_ids = observed.duplicate()


func can_destroy(target: Dictionary) -> Dictionary:
	var tid := str(target.get("id", ""))
	if tid == "" or tid == "wizard" or bool(target.get("is_wizard", false)):
		return {"ok": false, "reason": "self_or_wizard"}
	if tid.begins_with("group:") or tid.begins_with("formation:"):
		return {"ok": false, "reason": "group_target"}
	if tid.begins_with("rival:") or tid.begins_with("hazard:"):
		return {"ok": false, "reason": "rival_duel_actor"}
	var kind := str(target.get("kind", target.get("target_kind", "")))
	if kind not in ["unit", "person", "worker", "cart", "building"]:
		return {"ok": false, "reason": "not_ordinary"}
	if not observed_ids.is_empty() and tid not in observed_ids:
		return {"ok": false, "reason": "remote_or_unobserved"}
	var node := str(target.get("node_id", target.get("current_node", "")))
	if observed_ids.is_empty() and node != "" and local_node_id != "" and node != local_node_id:
		return {"ok": false, "reason": "remote_or_unobserved"}
	return {"ok": true, "target_id": tid, "allegiance": target.get("faction_id", "")}


func can_buff(target: Dictionary, buff_kind: String) -> Dictionary:
	if buff_kind not in ["shield", "frequency", "range"]:
		return {"ok": false, "reason": "unknown_buff"}
	if str(target.get("kind", "unit")) != "unit":
		return {"ok": false, "reason": "not_military_unit"}
	return can_destroy(target)
