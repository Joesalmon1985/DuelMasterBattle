extends SceneTree

## Humanoid sprite families normalise to one displayed height across facings.


func _init() -> void:
	call_deferred("_go")


func _go() -> void:
	var ActorVisual = load("res://client/world/actor_visual.gd")
	var root_n := Node2D.new()
	root.add_child(root_n)
	var families := ["worker", "woodcutter", "miner", "farmer", "shepherd", "villager_a"]
	var facings := ["up", "down", "left", "right"]
	var heights: Array = []
	for sprite in families:
		for facing in facings:
			var spr := Sprite2D.new()
			spr.centered = false
			root_n.add_child(spr)
			ActorVisual.apply(spr, "res://assets/pixel/", sprite, facing, 0, sprite)
			var h: float = ActorVisual.displayed_height_px(spr)
			heights.append(h)
			var target: float = ActorVisual.TARGET_DISPLAY_HEIGHT_PX
			if absf(h - target) > 1.5:
				push_error("height mismatch sprite=%s facing=%s h=%s target=%s" % [sprite, facing, h, target])
				quit(1)
				return
	var lo: float = heights.min()
	var hi: float = heights.max()
	if hi - lo > 2.0:
		push_error("family height spread too large lo=%s hi=%s" % [lo, hi])
		quit(1)
		return
	print("G05_HUMANOID_SCALE_OK families=", families.size(), " samples=", heights.size())
	quit(0)
