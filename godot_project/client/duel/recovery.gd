extends RefCounted
class_name DmbDuelRecoveryPresenter

## Client helper for duel checkpoint / recovery presentation (T092).
## Does not mutate world clocks or visit ledgers — Python RecoveryService owns that.

signal checkpoint_saved(lease_id: String, version: int)
signal resume_requested(lease_id: String)
signal recovery_ack(node_id: String, kind: String)

var lease_id: String = ""
var checkpoint_version: int = 0
var last_checkpoint: Dictionary = {}
var last_recovery: Dictionary = {}


func apply_checkpoint(payload: Dictionary) -> void:
	lease_id = str(payload.get("duel_id", payload.get("lease_id", lease_id)))
	checkpoint_version = int(payload.get("checkpoint_version", checkpoint_version))
	last_checkpoint = payload.get("checkpoint", payload).duplicate(true)
	checkpoint_saved.emit(lease_id, checkpoint_version)


func apply_resume(payload: Dictionary) -> void:
	lease_id = str(payload.get("duel_id", lease_id))
	last_checkpoint = payload.get("checkpoint", {}).duplicate(true)
	resume_requested.emit(lease_id)


func apply_recovery(payload: Dictionary) -> void:
	last_recovery = payload.duplicate(true)
	recovery_ack.emit(str(payload.get("node_id", "")), str(payload.get("kind", "")))


func next_feedback() -> Dictionary:
	return last_checkpoint.get("next_feedback", {})
