extends SceneTree

## Rendered G02 performance baseline / after measurement.
## Walks the wizard and advances a cart journey while sampling frame times.
## Usage:
##   Godot --path godot_project --resolution 450x800 \
##     --script res://client/tests/run_g02_perf_baseline.gd [-- --minutes=1 --label=after]

const Migrated = preload("res://client/core/migrated_runtime.gd")
const G02Shell = preload("res://client/scenes/g02_shell.gd")

var _minutes := 1.0
var _label := "sample"
var _out_path := ""


func _init() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--minutes="):
			_minutes = float(arg.substr(10))
		elif arg.begins_with("--label="):
			_label = arg.substr(8)
		elif arg.begins_with("--out="):
			_out_path = arg.substr(6)
	call_deferred("_run")


func _run() -> void:
	Migrated.enable()
	OS.set_environment("DMB_FIXTURE", "FX-CARGO")
	OS.set_environment("DMB_SEED", "202")
	DisplayServer.window_set_size(Vector2i(450, 800))

	var shell: Control = G02Shell.new()
	root.add_child(shell)
	for _i in range(120):
		await process_frame
		if shell._client != null and shell._area != null:
			break
	if shell._client == null or shell._area == null:
		push_error("G02_PERF_FAIL boot")
		quit(1)
		return

	shell._force_playable_focus()
	if shell._economy != null:
		shell._economy._expanded = true
		shell._economy._apply_expanded()
		# New economy_view accepts force:bool; older builds take no args.
		if shell._economy.has_method("is_expanded"):
			shell._economy.refresh(true)
		else:
			shell._economy.refresh()

	# Start delivery so cart motion is in play.
	shell._client.send_command("perf-start", "Interact", {"action": "start_delivery"})
	await process_frame

	var duration_sec := maxf(_minutes * 60.0, 15.0)
	var end_usec := Time.get_ticks_usec() + int(duration_sec * 1_000_000.0)
	var frames: Array = []
	var stalls := 0
	var last := Time.get_ticks_usec()
	var walk_dir := 1.0
	var phase := 0
	var phase_t := 0.0

	while Time.get_ticks_usec() < end_usec:
		await process_frame
		var now := Time.get_ticks_usec()
		var dt_ms := float(now - last) / 1000.0
		last = now
		frames.append(dt_ms)
		if dt_ms > 100.0:
			stalls += 1
		# Alternate walking left/right and occasional Wait.
		phase_t += dt_ms / 1000.0
		if shell._area != null:
			shell._area._move_dir = Vector2(walk_dir, 0.0)
		if phase_t > 2.5:
			phase_t = 0.0
			walk_dir *= -1.0
			phase += 1
			if phase % 4 == 0:
				var node := "node:1"
				if shell._client.has_method("has_player_cache") and shell._client.has_player_cache():
					node = str(shell._client.cached_player_view().get("player", {}).get("node_id", node))
				elif shell._client.has_method("request_view"):
					node = str(shell._client.request_view("player").get("player", {}).get("node_id", node))
				shell._client.send_command(
					"perf-wait-%d" % phase,
					"Wait",
					{"current_node": node, "press_id": "perf-%d" % phase},
				)
			if phase % 6 == 0 and shell._economy != null:
				shell._economy._expanded = not shell._economy._expanded
				shell._economy._apply_expanded()
				if shell._economy._expanded:
					if shell._economy.has_method("is_expanded"):
						shell._economy.refresh(true)
					else:
						shell._economy.refresh()

	if shell._area != null:
		shell._area._move_dir = Vector2.ZERO

	var snap: Dictionary = shell.perf_snapshot() if shell.has_method("perf_snapshot") else {}
	var sorted := frames.duplicate()
	sorted.sort()
	var n := sorted.size()
	var median := float(sorted[n / 2]) if n > 0 else 0.0
	var p95 := float(sorted[mini(n - 1, int(floor(float(n - 1) * 0.95)))]) if n > 0 else 0.0
	var p99 := float(sorted[mini(n - 1, int(floor(float(n - 1) * 0.99)))]) if n > 0 else 0.0
	var bridge: Dictionary = {}
	if snap.has("bridge"):
		bridge = snap.get("bridge", {})
	if bridge.is_empty() and shell._client != null and shell._client.has_method("bridge_metrics"):
		bridge = shell._client.bridge_metrics()
	var elapsed := duration_sec
	var req_per_sec := float(bridge.get("requests_completed", 0)) / maxf(elapsed, 0.001)
	var report := {
		"label": _label,
		"machine": OS.get_name(),
		"model": OS.get_model_name(),
		"resolution": [450, 800],
		"build": "g02_shell",
		"duration_sec": elapsed,
		"frames": n,
		"frame_ms_median": median,
		"frame_ms_p95": p95,
		"frame_ms_p99": p99,
		"stalls_over_100ms": stalls,
		"bridge_requests_per_sec": req_per_sec,
		"bridge_bytes_in": bridge.get("bytes_in", 0),
		"bridge_bytes_out": bridge.get("bytes_out", 0),
		"bridge_latency_avg_ms": bridge.get("latency_avg_ms", 0.0),
		"bridge_queue_high_water": bridge.get("queue_high_water", 0),
		"economy_expanded_samples": true,
	}
	var text := JSON.stringify(report, "\t")
	print("G02_PERF_REPORT ", text)
	var dest := _out_path
	if dest == "":
		var root := ProjectSettings.globalize_path("res://").get_base_dir().get_base_dir()
		if root.ends_with("godot_project"):
			root = root.get_base_dir()
		dest = root.path_join(
			"Pack/DuelMasterBattle_Build_Pack/tracking/gates/G02/perf_%s.json" % _label
		)
	var f := FileAccess.open(dest, FileAccess.WRITE)
	if f:
		f.store_string(text + "\n")
		f.close()
		print("G02_PERF_WRITTEN ", dest)
	print("G02_PERF_OK")
	if shell._launcher:
		shell._launcher.stop()
	quit(0)
