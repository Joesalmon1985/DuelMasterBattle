extends SceneTree
## Headless world run: prints per-faction stats after N turns.
## Usage: godot --headless --path godot_project --script res://sim/tools/run_world_sim.gd [seed] [turns]


func _init() -> void:
	var args := OS.get_cmdline_user_args()
	var seed := int(args[0]) if args.size() > 0 else 3
	var turns := int(args[1]) if args.size() > 1 else 200
	var w := DmbWorldSim.new(seed)
	w.setup()
	for i in range(turns):
		w.advance_turn()
	print("seed=%d turns=%d demons=%d outbreaks=%d epidemics=%d carts=%d" % [seed, turns, w.infection.total_demons(), w.infection.outbreaks, w.infection.epidemics, w.carts.active().size()])
	for f in w.factions:
		var s: Dictionary = w.stats[f]
		print("%-9s %-10s VP=%d roads=%d setts=%d cities=%d hand=%d | built r/s/c=%d/%d/%d dev=%d trades=%d treats=%d fights=%d" % [
			f, str(DmbFactions.DATA[f]["stance"]), w.catan.victory_points(f), w.catan.road_count(f), w.catan.settlement_count(f), w.catan.city_count(f), w.catan.hand_total(f),
			s["roads"], s["settlements"], s["cities"], s["dev"], s["trades"], s["treats"], s["fights"]])
	for e in w.last_events:
		print("  ", e["text"])
	quit()
