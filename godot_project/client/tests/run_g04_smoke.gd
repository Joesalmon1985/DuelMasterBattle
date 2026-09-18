extends SceneTree

const BattleShell = preload("res://client/scenes/g04_battle_shell.gd")
const HazardShell = preload("res://client/scenes/g04_hazard_shell.gd")


func _init() -> void:
	call_deferred("_go")


func _go() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-BATTLE")
	OS.set_environment("DMB_SEED", "404")
	var battle: Control = BattleShell.new()
	battle._paused = true
	root.add_child(battle)
	await create_timer(2.0).timeout
	if battle._client == null:
		push_error("G04 battle shell failed")
		quit(1)
		return
	var view: Dictionary = battle._client.request_view("player", ["units", "fx_battle", "battles"])
	if view.get("units", {}).size() < 2:
		push_error("G04 battle units missing")
		quit(1)
		return
	if str(view.get("fx_battle", {}).get("save_slot", "")) != "g04_battle":
		push_error("G04 battle save isolation missing")
		quit(1)
		return
	battle.queue_free()
	await create_timer(0.3).timeout

	OS.set_environment("DMB_FIXTURE", "FX-HAZARD")
	OS.set_environment("DMB_SEED", "408")
	var hazard: Control = HazardShell.new()
	hazard._paused = true
	root.add_child(hazard)
	await create_timer(2.0).timeout
	if hazard._client == null:
		push_error("G04 hazard shell failed")
		quit(1)
		return
	var hview: Dictionary = hazard._client.request_view("player", ["fx_hazard", "hazards", "player"])
	if str(hview.get("fx_hazard", {}).get("save_slot", "")) != "g04_hazard":
		push_error("G04 hazard save isolation missing")
		quit(1)
		return
	print("G04_SMOKE_OK battle_units=", view.get("units", {}).size())
	quit(0)
