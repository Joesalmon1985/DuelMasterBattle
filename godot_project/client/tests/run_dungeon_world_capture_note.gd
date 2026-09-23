extends SceneTree
## Records that automated pixel screenshots were not taken in headless CI;
## writes a text board dump as geometric evidence.
const Fixture = preload("res://sim/world/dungeon_world_fixture.gd")
func _init():
	call_deferred("_run")
func _run():
	var fx = Fixture.new()
	fx.setup(507)
	var lines: PackedStringArray = []
	lines.append("Strategic board dump seed=507")
	lines.append("hexes=%d nodes=%d" % [fx.sim.board.hexes.size(), fx.sim.board.nodes.size()])
	for h in fx.sim.board.hexes:
		lines.append("HEX %d q=%d r=%d terrain=%s" % [h["id"], h["q"], h["r"], h["terrain"]])
	for s in fx.settlements:
		lines.append("SETTLEMENT %s node=%d hexes=%s" % [s["faction"], s["node"], str(s["hexes"])])
	for c in fx.candidates:
		lines.append("CAND node=%d faction=%s types=%s terrains=%s coastal=%s reasons=%s" % [
			c["node"], c["faction"], str(c["types"]), str(c["terrains"]), c["coastal"], str(c["reasons"])])
	var abs := ProjectSettings.globalize_path("res://") + "../docs/testing/dungeon_world_captures/board_dump.txt"
	var f := FileAccess.open(abs, FileAccess.WRITE)
	f.store_string("\n".join(lines))
	f.close()
	print("WROTE ", abs)
	quit(0)
