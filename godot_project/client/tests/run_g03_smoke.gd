extends SceneTree

const G03Shell = preload("res://client/scenes/g03_shell.gd")


func _init() -> void:
	call_deferred("_go")


func _go() -> void:
	OS.set_environment("DMB_FIXTURE", "FX-INDUSTRY")
	OS.set_environment("DMB_SEED", "303")
	var shell: Control = G03Shell.new()
	shell._paused = true
	root.add_child(shell)
	await create_timer(2.0).timeout
	if shell._client == null or shell._area == null:
		push_error("G03 shell failed to boot")
		quit(1)
		return
	var initial: Dictionary = shell._client.request_view("economy", [
		"fx_industry", "industry", "industry_workers", "buildings", "stocks"
	])
	var workers: Array = initial.get("industry_workers", [])
	if workers.is_empty():
		push_error("G03 worker missing")
		quit(1)
		return
	var worker_id := str(workers[0].get("person_id", ""))
	var seq := int(initial.get("clock", {}).get("clock_sequence", 0))
	for index in range(10):
		seq += 1
		var reply: Dictionary = shell._client.send_command(
			"g03-advance-%d" % index, "AdvanceGame",
			{"delta_ms": 10000, "clock_sequence": seq}
		)
		if str(reply.get("status", "")) != "ACCEPTED":
			push_error("G03 advance failed")
			quit(1)
			return
	var after: Dictionary = shell._client.request_view("economy", [
		"fx_industry", "industry", "industry_workers", "buildings", "stocks"
	])
	var factory_count := 0
	for factory in after.get("industry", {}).get("factories", {}).values():
		if factory.get("meter") == {"numerator": "0", "denominator": "1"}:
			factory_count += 1
	if factory_count != 3:
		push_error("G03 100-second oracle failed")
		quit(1)
		return
	var finite_id := str(after.get("fx_industry", {}).get("finite_layer_id", ""))
	var finite: Dictionary = after.get("industry", {}).get("layers", {}).get(finite_id, {}).get("finite_balance", {})
	if str(finite.get("numerator", "")) != "590":
		push_error("G03 finite consumption oracle failed")
		quit(1)
		return
	if str(after.get("industry_workers", [])[0].get("person_id", "")) != worker_id:
		push_error("worker identity changed")
		quit(1)
		return
	var damage: Dictionary = shell._client.send_command("g03-damage", "Interact", {"action": "industry_damage"})
	var repair: Dictionary = shell._client.send_command("g03-repair", "Interact", {"action": "industry_repair"})
	if str(damage.get("status", "")) != "ACCEPTED" or str(repair.get("status", "")) != "ACCEPTED":
		push_error("damage/paid repair controls failed")
		quit(1)
		return
	shell._client.send_command("g03-save", "Save", {"slot": "g03_smoke"})
	var loaded: Dictionary = shell._client.send_command("g03-load", "Load", {"slot": "g03_smoke"})
	if str(loaded.get("status", "")) != "ACCEPTED":
		push_error("G03 save/load failed")
		quit(1)
		return
	print("G03_SMOKE_OK worker=", worker_id, " factories=", factory_count, " finite=590")
	if shell._launcher:
		shell._launcher.stop()
	quit(0)
