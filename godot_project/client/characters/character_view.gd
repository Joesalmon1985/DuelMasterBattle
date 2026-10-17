extends Node2D
class_name DmbCharView

## A character drawn as a child of a world node (the player, other LAN wizards, cutscene actors).  It watches its parent move, so
## walking, facing and idling need no cooperation from the code that moves the parent.  Presentation only.

const Lib = preload("res://client/characters/character_library.gd")
const Look = preload("res://client/characters/character_look.gd")
const Anim = preload("res://client/characters/character_anim.gd")
const Render = preload("res://client/characters/character_renderer.gd")
const Bus = preload("res://client/characters/character_bus.gd")

## Offset of the cell inside the parent Sprite2D's local space (parent scale 2.5): centres the figure on the tile column and puts the
## feet on the tile's bottom edge, where the old 16x24 sprite's feet were.
const CELL_OFFSET := Vector2(-15.2, -6.6)

var look
var anim
var character_id := ""
var _last_pos := Vector2.INF
var _stable := 0.0
var flash := 0.0
var working := false


func setup(look_, id_: String) -> void:
	look = look_
	character_id = id_
	anim = Anim.new(look_, id_)
	z_index = 0
	queue_redraw()


func set_look(look_) -> void:
	look = look_
	if anim != null:
		anim.set_look(look_)
	queue_redraw()


func face(f: String) -> void:
	if anim != null:
		anim.set_facing(f)
		queue_redraw()


func _process(delta: float) -> void:
	if anim == null or not is_visible_in_tree():
		return
	var par := get_parent() as Node2D
	var moving := false
	if par != null:
		var gp := par.global_position
		if _last_pos != Vector2.INF:
			var d := gp - _last_pos
			if d.length() > 0.05:
				moving = true
				_stable = 0.0
				anim.set_facing(Anim.facing_from_vector(d, anim.facing))
		_last_pos = gp
	if flash > 0.0:
		flash = maxf(0.0, flash - delta)
	var changed: bool = anim.update(delta, moving, working)
	if changed or flash > 0.0:
		queue_redraw()


func _draw() -> void:
	if look == null or anim == null:
		return
	var mod := Color.WHITE
	if flash > 0.0:
		mod = Color(1.0 + flash * 1.6, 1.0 - flash, 1.0 - flash, 1.0)
	Render.draw(self, look, anim.cell(), anim.flipped(), CELL_OFFSET, 1.0, mod, 0, true)
