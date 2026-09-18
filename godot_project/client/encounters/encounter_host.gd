extends RefCounted
class_name DmbEncounterHost

## Client-side lease host; durable consequences stay in Python (C02/C07 T064).

var active_lease_id: String = ""
var lease_version: int = 0
var checkpoint_hash: String = ""
var last_recovery_rollback_ms: int = 0
var lease_kind: String = ""
var retained_on_wait: bool = false
var closed: bool = false
var last_close_reason: String = ""
var pending_reinforcement_ids: Array = []


func acknowledge(lease: Dictionary) -> void:
	active_lease_id = str(lease.get("lease_id", ""))
	lease_version = int(lease.get("version", 0))
	checkpoint_hash = str(lease.get("checkpoint_hash", ""))
	lease_kind = str(lease.get("kind", ""))
	closed = false
	retained_on_wait = false
	last_close_reason = ""


func submit_checkpoint(delta: Dictionary) -> Dictionary:
	return {
		"lease_id": active_lease_id,
		"version": lease_version,
		"base_checkpoint_hash": checkpoint_hash,
		"delta": delta,
	}


func note_recovery(meta: Dictionary) -> void:
	last_recovery_rollback_ms = int(meta.get("rollback_ms", 0))
	if meta.has("checkpoint_hash"):
		checkpoint_hash = str(meta["checkpoint_hash"])


func close_for_travel() -> Dictionary:
	## Travel closes outgoing local lease before offscreen resolution.
	closed = true
	last_close_reason = "travel"
	retained_on_wait = false
	var payload := {
		"lease_id": active_lease_id,
		"version": lease_version,
		"checkpoint_hash": checkpoint_hash,
		"reason": "travel",
	}
	active_lease_id = ""
	return payload


func retain_on_wait() -> Dictionary:
	## Wait retains local ownership.
	retained_on_wait = true
	closed = false
	last_close_reason = ""
	return {
		"lease_id": active_lease_id,
		"retained": true,
		"closed": false,
	}


func accept_reinforcement(unit_id: String) -> Dictionary:
	if unit_id in pending_reinforcement_ids:
		return {"unit_id": unit_id, "added": false, "duplicate": true}
	pending_reinforcement_ids.append(unit_id)
	lease_version += 1
	return {"unit_id": unit_id, "added": true, "version": lease_version}
