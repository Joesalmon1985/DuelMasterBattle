extends RefCounted
class_name DmbEncounterHost

## Client-side lease host stub for G01; durable consequences stay in Python.
## Recovery restores the last accepted checkpoint hash reported by Python.

var active_lease_id: String = ""
var lease_version: int = 0
var checkpoint_hash: String = ""
var last_recovery_rollback_ms: int = 0


func acknowledge(lease: Dictionary) -> void:
	active_lease_id = str(lease.get("lease_id", ""))
	lease_version = int(lease.get("version", 0))
	checkpoint_hash = str(lease.get("checkpoint_hash", ""))


func submit_checkpoint(delta: Dictionary) -> Dictionary:
	return {
		"lease_id": active_lease_id,
		"version": lease_version,
		"base_checkpoint_hash": checkpoint_hash,
		"delta": delta,
	}


func note_recovery(meta: Dictionary) -> void:
	## Called after SaveCoordinator-bounded restart restores a checkpoint.
	last_recovery_rollback_ms = int(meta.get("rollback_ms", 0))
	if meta.has("checkpoint_hash"):
		checkpoint_hash = str(meta["checkpoint_hash"])
