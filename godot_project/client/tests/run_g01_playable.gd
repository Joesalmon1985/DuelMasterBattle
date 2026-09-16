extends SceneTree

## Headless check: FX-CLOCK area builds wizard + exit without speculative travel.

const Migrated = preload("res://client/core/migrated_runtime.gd")
const FxArea = preload("res://client/world/fx_clock_area.gd")

func _init() -> void:
	call_deferred("_run")

func _run() -> void:
	Migrated.enable()
	var area = FxArea.new()
	root.add_child(area)
	# Minimal fake client stub.
	var stub = Node.new()
	stub.set_script(load("res://client/tests/g01_view_stub.gd"))
	root.add_child(stub)
	area.client = stub
	area._build_roots()
	area.rebuild_from_view(stub.request_view("player"))
	if area._wizard == null or area._wizard.texture == null:
		push_error("wizard missing texture")
		quit(1)
		return
	if area._exit_nodes.is_empty():
		push_error("no exits")
		quit(1)
		return
	area.travel_pending = false
	var pending := false
	area.exit_activated.connect(func(_n): pending = true)
	# Speculative: calling acknowledge only after flag.
	if area.current_node != "node:1":
		push_error("expected home node")
		quit(1)
		return
	print("G01_PLAYABLE_OK")
	quit(0)
