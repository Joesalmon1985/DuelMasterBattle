extends RefCounted
class_name DmbWizardDungeonSpec
## Structured acceptance data from docs/testing/WIZARD_DUNGEON_SPATIAL_SPEC.txt.
## Fixture/spatial-test authority only — does not assign BG a production terrain.

const ROOM_W := 15
const ROOM_H := 13
const RESERVATION_W := 53
const RESERVATION_H := 32
const CORRIDOR_GAP_X := 4
const CORRIDOR_GAP_Y := 6

## Node size profiles under test (tiles). Production constants are not changed.
const SIZE_PROFILES := [
	Vector2i(65, 49),
	Vector2i(73, 55),
	Vector2i(81, 61),
]

## Catalogue verification: DmbPuzzleRooms max envelope is 15×13 (matches this file).
const CATALOGUE_MAX_ROOM := Vector2i(15, 13)

## Terrain families → dungeon type codes. BG deliberately omitted.
const TERRAIN_TO_TYPES := {
	"forest": ["GW"],
	"hills": ["BR"],
	"mountains": ["WB"],
}

const TYPE_META := {
	"GW": {
		"dungeon_id": "dungeon.gw.rootbound_sanctuary",
		"wizard_id": "wizard.gw.treefolk",
		"name": "Rootbound Sanctuary",
		"terrain_concept": "Forest/Woodland",
		"production_terrain": "forest",
	},
	"BR": {
		"dungeon_id": "dungeon.br.kiln_warrens",
		"wizard_id": "wizard.br.goblin_orc",
		"name": "Kiln Warrens",
		"terrain_concept": "Brick/Hills/Clay",
		"production_terrain": "hills",
	},
	"UB": {
		"dungeon_id": "dungeon.ub.drowned_archive",
		"wizard_id": "wizard.ub.merfolk",
		"name": "Drowned Archive",
		"terrain_concept": "coastal/sea-touching land",
		"production_terrain": "coastal",
	},
	"WB": {
		"dungeon_id": "dungeon.wb.ossuary_mine",
		"wizard_id": "wizard.wb.necromancer",
		"name": "Ossuary Mine",
		"terrain_concept": "Ore/Mountains",
		"production_terrain": "mountains",
	},
	"BG": {
		"dungeon_id": "dungeon.bg.rotgarden_vault",
		"wizard_id": "wizard.bg.elf",
		"name": "Rotgarden Vault",
		"terrain_concept": "UNASSIGNED",
		"production_terrain": "",
	},
}


static func all_types() -> Array:
	return ["GW", "BR", "UB", "WB", "BG"]


static func production_types() -> Array:
	return ["GW", "BR", "UB", "WB"]


static func bg_unassigned_in_production() -> bool:
	return str(TYPE_META["BG"]["production_terrain"]) == "" and not TERRAIN_TO_TYPES.has("bg")


static func dungeon_def(type_code: String) -> Dictionary:
	match type_code:
		"GW":
			return _gw()
		"BR":
			return _br()
		"UB":
			return _ub()
		"WB":
			return _wb()
		"BG":
			return _bg()
		_:
			return {}


## Room origins inside the 53×32 reservation (local coords).
## Packing: R1 R2 R3 on top row; R5 R4 on bottom (see spec diagram).
static func room_origins() -> Array:
	var gap_x := CORRIDOR_GAP_X
	var gap_y := CORRIDOR_GAP_Y
	var top_y := 0
	var bot_y := ROOM_H + gap_y
	return [
		Vector2i(0, top_y),                                    # 1
		Vector2i(ROOM_W + gap_x, top_y),                       # 2
		Vector2i(2 * (ROOM_W + gap_x), top_y),                 # 3
		Vector2i(ROOM_W + gap_x, bot_y),                       # 4
		Vector2i(0, bot_y),                                    # 5
	]


static func room_rects() -> Array:
	var out: Array = []
	for o in room_origins():
		out.append(Rect2i(o.x, o.y, ROOM_W, ROOM_H))
	return out


static func reservation_fits(node_w: int, node_h: int, inset: int = 2) -> bool:
	return (node_w - 2 * inset) >= RESERVATION_W and (node_h - 2 * inset) >= RESERVATION_H


static func _base(type_code: String, rooms: Array, flow: String, states: Array) -> Dictionary:
	var meta: Dictionary = TYPE_META[type_code]
	return {
		"type": type_code,
		"dungeon_id": meta["dungeon_id"],
		"wizard_id": meta["wizard_id"],
		"name": meta["name"],
		"terrain_concept": meta["terrain_concept"],
		"production_terrain": meta["production_terrain"],
		"rooms": rooms,
		"flow": flow,
		"states": states,
	}


static func _gw() -> Dictionary:
	return _base("GW", [
		{"index": 1, "room_id": "gw.root_gate", "name": "ROOT GATE",
			"labels": ["SIGN:gw.seasons_carving", "MECH:gw.root_barrier", "GATE:gw.root_gate"]},
		{"index": 2, "room_id": "gw.seed_shrine", "name": "SEED SHRINE",
			"labels": ["ITEM:item.gw.sun_seed", "RECEPTOR:gw.seed_shrine"]},
		{"index": 3, "room_id": "gw.withered_channel", "name": "WITHERED CHANNEL",
			"labels": ["MECH:gw.channel_weight", "MECH:gw.channel_plate", "MECH:gw.water_switch", "STATE:gw.water_restored"]},
		{"index": 4, "room_id": "gw.heartwood_chamber", "name": "HEARTWOOD CHAMBER",
			"labels": ["ITEM:item.gw.sun_seed", "RECEPTOR:gw.growth_point", "STATE:gw.water_restored", "GATE:gw.living_gate"],
			"rule": "water_restored AND sun_seed installed -> living gate opens"},
		{"index": 5, "room_id": "gw.elder_court", "name": "ELDER COURT",
			"labels": ["WIZARD:wizard.gw.treefolk"]},
	], "restore water -> install seed -> open living gate -> reach GW wizard",
	["gw.water_restored", "gw.sun_seed_installed"])


static func _br() -> Dictionary:
	return _base("BR", [
		{"index": 1, "room_id": "br.collapsed_clayworks", "name": "COLLAPSED CLAYWORKS",
			"labels": ["SIGN:br.furnace_clue", "GATE:br.blocked_route"]},
		{"index": 2, "room_id": "br.scrap_den", "name": "SCRAP DEN",
			"labels": ["ITEM:item.br.furnace_lever"]},
		{"index": 3, "room_id": "br.kiln_gallery", "name": "KILN GALLERY",
			"labels": ["MECH:br.vent_a", "MECH:br.vent_b", "STATE:br.pressure_routed"]},
		{"index": 4, "room_id": "br.great_furnace", "name": "GREAT FURNACE",
			"labels": ["ITEM:item.br.furnace_lever", "RECEPTOR:br.lever_socket", "MECH:br.furnace_control", "MECH:br.weight_or_plate", "GATE:br.furnace_gate"],
			"rule": "lever installed plus correct mechanism state -> gate opens"},
		{"index": 5, "room_id": "br.boss_foundry", "name": "BOSS'S FOUNDRY",
			"labels": ["WIZARD:wizard.br.goblin_orc"]},
	], "recover lever -> route pressure -> install/use lever -> open gate -> reach BR wizard",
	["br.pressure_routed", "br.lever_installed"])


static func _ub() -> Dictionary:
	return _base("UB", [
		{"index": 1, "room_id": "ub.tidal_stair", "name": "TIDAL STAIR",
			"labels": ["STATE:ub.water_level"]},
		{"index": 2, "room_id": "ub.drowned_scriptorium", "name": "DROWNED SCRIPTORIUM",
			"labels": ["ITEM:item.ub.pearl_sluice_handle"]},
		{"index": 3, "room_id": "ub.valve_gallery", "name": "VALVE GALLERY",
			"labels": ["ITEM:item.ub.pearl_sluice_handle", "RECEPTOR:ub.sluice_handle_socket", "MECH:ub.sluice_control", "STATE:ub.water_low", "STATE:ub.water_high"]},
		{"index": 4, "room_id": "ub.sunken_archive", "name": "SUNKEN ARCHIVE",
			"labels": ["GATE:ub.archive_gate"]},
		{"index": 5, "room_id": "ub.black_tide_observatory", "name": "BLACK-TIDE OBSERVATORY",
			"labels": ["WIZARD:wizard.ub.merfolk"]},
	], "recover handle -> install sluice -> change water state -> reveal route -> open archive gate -> reach UB wizard",
	["ub.water_low", "ub.water_high"])


static func _wb() -> Dictionary:
	return _base("WB", [
		{"index": 1, "room_id": "wb.old_shaft", "name": "OLD SHAFT",
			"labels": []},
		{"index": 2, "room_id": "wb.memorial_alcove", "name": "MEMORIAL ALCOVE",
			"labels": ["ITEM:item.wb.funerary_token"]},
		{"index": 3, "room_id": "wb.weighing_hall", "name": "WEIGHING HALL",
			"labels": ["MECH:wb.funeral_weight", "MECH:wb.weighing_plate", "STATE:wb.weight_correct"]},
		{"index": 4, "room_id": "wb.ossuary_lift", "name": "OSSUARY LIFT",
			"labels": ["ITEM:item.wb.funerary_token", "RECEPTOR:wb.token_slot", "STATE:wb.weight_correct", "GATE:wb.ossuary_lift"],
			"rule": "correct weight AND funerary token -> lift/gate opens"},
		{"index": 5, "room_id": "wb.sepulchral_forge", "name": "SEPULCHRAL FORGE",
			"labels": ["WIZARD:wizard.wb.necromancer"]},
	], "obtain token -> set correct weight -> present token -> open lift -> reach WB wizard",
	["wb.weight_correct", "wb.token_presented"])


static func _bg() -> Dictionary:
	return _base("BG", [
		{"index": 1, "room_id": "bg.thorn_gate", "name": "THORN GATE",
			"labels": ["GATE:bg.thorn_gate"]},
		{"index": 2, "room_id": "bg.spore_garden", "name": "SPORE GARDEN",
			"labels": ["ITEM:item.bg.blackbloom_bulb"]},
		{"index": 3, "room_id": "bg.compost_vault", "name": "COMPOST VAULT",
			"labels": ["MECH:bg.decay_mass", "RECEPTOR:bg.compost_bed", "STATE:bg.compost_ready"]},
		{"index": 4, "room_id": "bg.corpse_orchard", "name": "CORPSE ORCHARD",
			"labels": ["ITEM:item.bg.blackbloom_bulb", "RECEPTOR:bg.growth_point", "STATE:bg.compost_ready", "GATE:bg.living_gate"],
			"rule": "compost_ready plus bulb installed -> new growth opens route"},
		{"index": 5, "room_id": "bg.blackbloom_court", "name": "BLACKBLOOM COURT",
			"labels": ["WIZARD:wizard.bg.elf"]},
	], "obtain bulb -> prepare compost -> plant bulb -> growth opens route -> reach BG wizard",
	["bg.compost_ready", "bg.bulb_planted"])
