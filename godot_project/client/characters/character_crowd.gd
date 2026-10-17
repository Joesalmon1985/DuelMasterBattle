extends RefCounted
class_name DmbCharCrowd

## Draws the simulation's mobile people (workers, carriers, soldiers, story NPCs) from the shared character sheets inside the hybrid
## world's single `_draw()`.  One animation controller per entity id, created on first sight, dropped when unseen for a while.
## Appearance is a function of the entity id, so it is stable across save/load, polling, scrolling and LAN clients.

const Lib = preload("res://client/characters/character_library.gd")
const Look = preload("res://client/characters/character_look.gd")
const Anim = preload("res://client/characters/character_anim.gd")
const Render = preload("res://client/characters/character_renderer.gd")
const Appearance = preload("res://client/characters/character_appearance.gd")
const Bus = preload("res://client/characters/character_bus.gd")

const PX := 2.5                  # screen pixels per sprite pixel at tile size 64: a 38-pixel figure is about 95 px, 1.5 tiles
const FEET := Vector2(28.0, 45.0)  # feet position inside the cell
const FEET_DROP := 20.0          # feet sit this far below the tile centre

var _rec: Dictionary = {}        # id -> {anim, look, def, seen}
var _frame := 0
var player_tile := Vector2(-9999, -9999)
var drawn_count := 0
var _cull_every := 240


func handles(entity: Dictionary) -> bool:
	if not Lib.available():
		return false
	var cls := str(entity.get("class", ""))
	if cls == "npc" or str(entity.get("kind", "")) == "npc":
		return true
	if cls not in ["worker", "carrier", "unit"]:
		return false
	var definition := str(entity.get("definition", ""))
	if Appearance.is_animal_definition(definition):
		return false
	return Appearance.outfit_for_definition(definition, str(Appearance.faction_tribes.get(str(entity.get("faction_name", "")), ""))) != ""


func begin_frame(dt: float) -> void:
	_frame += 1
	drawn_count = 0
	if _frame % _cull_every == 0:
		for id in _rec.keys():
			if int(_rec[id]["seen"]) < _frame - _cull_every:
				_rec.erase(id)


func record(entity: Dictionary) -> Dictionary:
	var id := str(entity.get("id", ""))
	var definition := str(entity.get("definition", ""))
	var r: Dictionary = _rec.get(id, {})
	if r.is_empty() or str(r["def"]) != definition:
		var look = Appearance.for_entity(entity)
		var a = Anim.new(look, id)
		a.set_facing(Anim.facing_from_compass(str(entity.get("facing", "s")), "down"))
		r = {"anim": a, "look": look, "def": definition, "seen": _frame}
		_rec[id] = r
	r["seen"] = _frame
	return r


## `anchor` is the tile centre; `drawn` carries the presentation-smoothed motion fields of hybrid_art._motion.
func draw(canvas: CanvasItem, entity: Dictionary, anchor: Vector2, dt: float, zoom: float) -> void:
	var r := record(entity)
	var anim = r["anim"]
	var moving: bool = bool(entity.get("_moving", false))
	var cls := str(entity.get("class", ""))
	var work_anim := str(entity.get("anim", ""))
	var is_working := cls == "worker" and work_anim not in ["", "idle", "walk", "walkload"] and not moving
	# facing: follow the glide direction; a speaking person turns to the wizard
	var face: String = Anim.facing_from_compass(str(entity.get("_face", entity.get("facing", "s"))), anim.facing)
	if cls == "npc" or str(entity.get("kind", "")) == "npc":
		moving = false
		is_working = false
		face = anim.facing
		if Bus.is_speaking(str(entity.get("id", ""))):
			var dv := player_tile - Vector2(float(entity.get("tx", 0)), float(entity.get("ty", 0)))
			if dv.length() < 12.0:
				face = Anim.facing_from_vector(dv, face)
		elif face == "down" and anim.facing == "down":
			face = "down"
		var alive := bool(entity.get("alive", true))
		anim.dead = not alive
	elif not moving and cls == "worker":
		face = Anim.facing_from_compass(str(entity.get("facing", "s")), anim.facing)
	if cls != "npc" and str(entity.get("kind", "")) != "npc":
		anim.dead = entity.get("alive", true) == false  # a fallen soldier lies where it fell until the simulation removes the corpse
		if entity.has("hp") and not anim.dead:
			var hp := int(entity["hp"])
			if r.has("hp") and hp < int(r["hp"]):
				Bus.react(str(entity.get("id", "")), "hurt")
			r["hp"] = hp
	anim.set_facing(face)
	anim.update(dt, moving, is_working)
	if zoom < 0.16:
		return
	var origin := anchor + Vector2(0.0, FEET_DROP) - FEET * PX
	var lod := 0 if zoom >= 0.4 else 1
	Render.draw(canvas, r["look"], anim.cell(), anim.flipped(), origin, PX, Color.WHITE, lod, zoom >= 0.3)
	drawn_count += 1


func head_height() -> float:
	return 40.0 * PX


func has(id: String) -> bool:
	return _rec.has(id)


func anim_of(id: String):
	return _rec[id]["anim"] if _rec.has(id) else null


func look_of(id: String):
	return _rec[id]["look"] if _rec.has(id) else null


func count() -> int:
	return _rec.size()
