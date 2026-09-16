extends RefCounted
class_name DmbEncounterHost

## Client-side lease host stub for G01; durable consequences stay in Python.

var active_lease_id: String = ""
var lease_version: int = 0
var checkpoint_hash: String = ""


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
