extends SceneTree

const LocalBattle = preload("res://client/combat/local_battle.gd")


func _init() -> void:
	call_deferred("_run")


func _run() -> void:
	var battle = LocalBattle.new()
	battle.bind_lease({
		"lease_id": "lease:t063",
		"version": 1,
		"snapshot": {
			"units": {
				"u1": {
					"id": "u1", "faction_id": "red", "alive": true,
					"position": [0, 0], "current_health": 40, "max_health": 40,
					"base_attack": 50, "era_factor": 1, "range_tiles": 2,
					"period_ms": 1000, "remaining_attack_cooldown_ms": 0, "armour": 0
				},
				"u2": {
					"id": "u2", "faction_id": "blue", "alive": true,
					"position": [1, 0], "current_health": 40, "max_health": 40,
					"base_attack": 50, "era_factor": 1, "range_tiles": 2,
					"period_ms": 1000, "remaining_attack_cooldown_ms": 0, "armour": 0
				}
			}
		}
	})
	var step = battle.step()
	if step.get("fired", []).size() != 2:
		push_error("expected simultaneous fire: %s" % step)
		quit(1)
		return
	var cp = battle.checkpoint()
	if cp.get("casualties", []).size() != 2:
		push_error("expected casualties: %s" % cp)
		quit(1)
		return
	# Scene import check.
	var packed = load("res://client/world/battle_area.tscn")
	if packed == null:
		push_error("battle_area.tscn failed to load")
		quit(1)
		return
	print("LOCAL_BATTLE_OK lease=", battle.lease_id)
	quit(0)
