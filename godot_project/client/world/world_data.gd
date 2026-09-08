class_name DmbWorldData
extends RefCounted

## Data for the first adventure: three connected areas. Maps are ASCII grids;
## entities (NPCs, fires, pickups, creatures, triggers) are dictionaries.
##
## Tile legend
##   .  grass        ,  dark grass     :  path         ~  water       =  bridge
##   #  wall         R  roof           D  door         f  fence       a  ash
##   T  tree (solid) t  burnt tree     r  rock (solid) L  log pile    X  fire (solid until put out)
##   space = void (solid, drawn dark)
##
## Entity kinds
##   npc      {id, name, sprite, pos, facing, lines: [..] | lines_by_flag}
##   fire     {id, pos}                          — solid; extinguish with Water magic
##   pickup   {id, pos, sprite, grant: {spell, weave}, text}
##   creature {id, enemy_id, pos, sprite, respawn: bool, intro}
##   wizard   {id, enemy_id, pos, sprite, intro, on_win_flag}
##   trigger  {id, pos|rect, event}              — story events fired on step
##   exit     {pos, to_area, to_pos, facing}
##   sign     {pos, text}

const SPELL_BLUE := 1
const SPELL_RED := 0
const SPELL_STONE := 3
const SPELL_VINE := 6

static var _areas: Dictionary = {}


static func get_area(id: String) -> Dictionary:
	_build()
	assert(_areas.has(id), "unknown area %s" % id)
	return _areas[id]


static func area_ids() -> Array:
	_build()
	return _areas.keys()


static func _build() -> void:
	if not _areas.is_empty():
		return
	_areas["forest_home"] = _forest_home()
	_areas["forest_deep"] = _forest_deep()
	_areas["village"] = _village()


# -------------------------------------------------------------------------------
# AREA 1 — John's clearing. 16 wide x 20 tall.
# -------------------------------------------------------------------------------
static func _forest_home() -> Dictionary:
	var rows := [
		"TTTTTTTT..TTTTTT",
		"TTTTT.....,.TTTT",
		"TTT....RRR...TTT",
		"TT..r..RRR..,.TT",
		"TT.....#D#....TT",
		"TT..,..:::..T.TT",
		"TT.L...:....r.TT",
		"T......:.....,TT",
		"T..T...:..T...TT",
		"TT.....:......TT",
		"TT..,..:..r...TT",
		"TTT....:.....TTT",
		"TTTT..,:..TTTTTT",
		"TTTTT..:.TTTTTTT",
		"TTTTTT.:.TTTTTTT",
		"TTTTTTT:TTTTTTTT",
		"TTTTTTT:TTTTTTTT",
		"TTTTTTT:TTTTTTTT",
		"TTTTTTT:TTTTTTTT",
		"TTTTTTTTTTTTTTTT",
	]
	return {
		"id": "forest_home", "name": "The Clearing", "rows": rows,
		"entities": [
			{"kind": "sign", "id": "home_sign", "pos": [10, 5], "text": "John's house. Woodcutter. Knock loudly."},
			{"kind": "door", "id": "home_door", "pos": [8, 4], "text": "Your house. The kettle is still warm. Wood first."},
			{"kind": "logs", "id": "home_logs", "pos": [3, 6], "text": "Your woodpile. It never seems to get any bigger."},
			{"kind": "trigger", "id": "opening_fight", "rect": [1, 6, 14, 12], "event": "opening_fight", "once_flag": "opening_done", "requires_steps": 3},
			# Placed by the opening event: staff, fires, dead wizard, wisps. Listed here so
			# they render when the area is rebuilt after loading.
			{"kind": "pickup", "id": "blue_staff", "pos": [7, 8], "sprite": "staff", "requires_flag": "opening_done",
				"grant": {"spell": SPELL_BLUE, "weave": 1},
				"text": "The Blue wizard's staff. It is cold, and it hums.\n\nYou have learned WATER magic.\nYour weave can hold ONE spell."},
			{"kind": "corpse", "id": "blue_wizard_body", "pos": [6, 8], "sprite": "blue_mage", "facing": "right", "requires_flag": "opening_done",
				"text": "The Blue wizard. Whatever he was, he is not any more."},
			{"kind": "fire", "id": "fire_h1", "pos": [7, 3], "requires_flag": "opening_done"},
			{"kind": "fire", "id": "fire_h2", "pos": [4, 10], "requires_flag": "opening_done"},
			{"kind": "fire", "id": "fire_h3", "pos": [10, 9], "requires_flag": "opening_done"},
			{"kind": "fire", "id": "fire_h4", "pos": [8, 0], "requires_flag": "opening_done", "blocks_exit": true},
			{"kind": "fire", "id": "fire_h5", "pos": [9, 0], "requires_flag": "opening_done", "blocks_exit": true},
			{"kind": "burnt", "id": "burnt_h1", "pos": [12, 8], "requires_flag": "opening_done"},
			{"kind": "burnt", "id": "burnt_h2", "pos": [3, 8], "requires_flag": "opening_done"},
			{"kind": "creature", "id": "wisp_h1", "enemy_id": "flame_wisp", "pos": [5, 4], "requires_flag": "first_fire_out",
				"intro": "A scrap of the fire has come alive. It hisses at you.\n\nIt only knows FIRE. Its Ward is a single slot of WATER — the same magic you hold."},
			{"kind": "creature", "id": "wisp_h2", "enemy_id": "flame_wisp", "pos": [11, 11], "requires_flag": "first_fire_out",
				"intro": "Another wisp. This one is quicker."},
			{"kind": "exit", "pos": [8, 0], "to_area": "forest_deep", "to_pos": [8, 22], "facing": "up"},
			{"kind": "exit", "pos": [9, 0], "to_area": "forest_deep", "to_pos": [8, 22], "facing": "up"},
		],
	}


# -------------------------------------------------------------------------------
# AREA 2 — The burnt forest. 20 wide x 24 tall. Exit south to home, east to village.
# -------------------------------------------------------------------------------
static func _forest_deep() -> Dictionary:
	var rows := [
		"TTTTTTTTTTTTTTTTTTTT",
		"TTTt..a.aaTT...TTTTT",
		"TTt.a.aaa..t..a.TTTT",
		"TT.aa..a.,..a...TTTT",
		"TT.a..r..a..aa.,TTTT",
		"TTa..aa.:.aa..a.TTTT",
		"TT..a...:..a....TTTT",
		"TTt.a..a:aa..t.aTTTT",
		"TT.....a:...a...TTTT",
		"TT..r...:.....a.TTTT",
		"TT,.....:..r..,.TTTT",
		"TT..~~..:......:::::",
		"TT.~~~~.:......:....",
		"TT..~~..:......TTTTT",
		"TT......:...T..,TTTT",
		"TTT.....:......TTTTT",
		"TTTT.T..:..T..TTTTTT",
		"TTTT....:.....TTTTTT",
		"TTTTT...:....TTTTTTT",
		"TTTTTT..:...TTTTTTTT",
		"TTTTTTT.:..TTTTTTTTT",
		"TTTTTTT.:.TTTTTTTTTT",
		"TTTTTTTT:TTTTTTTTTTT",
		"TTTTTTTTTTTTTTTTTTTT",
	]
	return {
		"id": "forest_deep", "name": "The Burnt Wood", "rows": rows,
		"entities": [
			{"kind": "sign", "id": "deep_sign", "pos": [9, 21], "text": "North: the old road. East: Ashwell village.\n(Someone has scorched the word 'village'.)"},
			# Fires gate the way north and east.
			{"kind": "fire", "id": "fire_d1", "pos": [8, 17]},
			{"kind": "fire", "id": "fire_d2", "pos": [8, 13]},
			{"kind": "fire", "id": "fire_d3", "pos": [7, 13]},
			{"kind": "fire", "id": "fire_d4", "pos": [9, 13]},
			{"kind": "fire", "id": "fire_d5", "pos": [15, 11]},
			{"kind": "fire", "id": "fire_d6", "pos": [15, 12]},
			{"kind": "fire", "id": "fire_d7", "pos": [8, 5]},
			# Tier 1
			{"kind": "creature", "id": "imp_d1", "enemy_id": "flame_imp", "pos": [10, 15],
				"intro": "A Flame Imp. Bigger than a wisp, and its Ward could be WATER or FIRE.\n\nYou only know WATER. If the Ward is FIRE you cannot break it — but you can still learn from what your cast tells you."},
			{"kind": "creature", "id": "imp_d2", "enemy_id": "flame_imp", "pos": [5, 10],
				"intro": "Another imp guards the pendant."},
			# Progression: the Red wizard's pendant.
			{"kind": "pickup", "id": "fire_pendant", "pos": [3, 11], "sprite": "pendant",
				"grant": {"spell": SPELL_RED, "weave": 2},
				"text": "A pendant of red glass, dropped in the Red wizard's haste. It is warm.\n\nYou have learned FIRE magic.\nYour weave can now hold TWO spells."},
			# Tier 2
			{"kind": "creature", "id": "sprite_d1", "enemy_id": "steam_sprite", "pos": [12, 9], "requires_spell": SPELL_RED,
				"intro": "A Steam Sprite, born where the fire met the pond. One Ward slot: FIRE or WATER.\n\nWith two weave slots you can try both at once."},
			{"kind": "creature", "id": "sprite_d2", "enemy_id": "steam_sprite", "pos": [3, 4], "requires_spell": SPELL_RED,
				"intro": "Steam hisses out of the ash."},
			{"kind": "creature", "id": "brute_d1", "enemy_id": "steam_brute", "pos": [13, 5], "requires_spell": SPELL_RED,
				"intro": "A Steam Brute. TWO Ward slots, FIRE and WATER.\n\nRead the result: an exact match is a Fracture, a right spell in the wrong slot is an Echo."},
			# Tier 3 gate to the north road: Cinder Golem drops the Stone shard.
			{"kind": "creature", "id": "golem_d1", "enemy_id": "cinder_golem", "pos": [8, 2], "requires_spell": SPELL_RED,
				"intro": "A Cinder Golem blocks the old road. It throws STONE and FIRE at you — but its Ward is woven only from magic you already know.\n\nWhat a thing attacks with is not what protects it.",
				"drops": "stone_shard"},
			{"kind": "pickup", "id": "stone_shard", "pos": [8, 2], "sprite": "stone_shard", "requires_defeated": "golem_d1",
				"grant": {"spell": SPELL_STONE, "weave": 3},
				"text": "The golem's heart-stone. Heavy, patient magic.\n\nYou have learned STONE magic.\nYour weave can now hold THREE spells."},
			{"kind": "exit", "pos": [8, 23], "to_area": "forest_home", "to_pos": [8, 1], "facing": "down"},
			{"kind": "exit", "pos": [19, 11], "to_area": "village", "to_pos": [1, 8], "facing": "right"},
			{"kind": "exit", "pos": [19, 12], "to_area": "village", "to_pos": [1, 9], "facing": "right"},
		],
	}


# -------------------------------------------------------------------------------
# AREA 3 — Ashwell village. 22 wide x 18 tall.
# -------------------------------------------------------------------------------
static func _village() -> Dictionary:
	var rows := [
		"TTTTTTTTT.:.TTTTTTTTTT",
		"TT........:.....,..TTT",
		"TT.RRR....:...RRR..TTT",
		"TT.RRR....:...RRR..TTT",
		"TT.#D#....:...#D#..TTT",
		"TT........:.......,.TT",
		"TT..ffff..:..ffff...TT",
		"TT........:.........TT",
		"::::::::::::::..~~..TT",
		"::::::::::::::..~~..TT",
		"TT........:......,..TT",
		"TT.RRRR...:..RRRR...TT",
		"TT.RRRR...:..RRRR...TT",
		"TT.#DD#...:..#DD#...TT",
		"TT........:.........TT",
		"TT,....r..:....L....TT",
		"TT........:.........TT",
		"TTTTTTTTTTTTTTTTTTTTTT",
	]
	return {
		"id": "village", "name": "Ashwell", "rows": rows,
		"entities": [
			{"kind": "sign", "id": "village_sign", "pos": [3, 8], "text": "ASHWELL. Pop. 31. No wizards."},
			{"kind": "door", "id": "v_door1", "pos": [4, 4], "text": "Locked. Someone inside is pretending not to be home."},
			{"kind": "door", "id": "v_door2", "pos": [15, 4], "text": "The elder's house. He is outside."},
			{"kind": "door", "id": "v_door3", "pos": [4, 13], "text": "A smell of bread. Nobody answers."},
			{"kind": "door", "id": "v_door4", "pos": [14, 13], "text": "Ashby's workshop. Scorch marks around the frame."},
			{"kind": "logs", "id": "v_logs", "pos": [15, 15], "text": "Somebody else's woodpile. Neater than yours."},
			{"kind": "npc", "id": "villager_mara", "name": "Mara", "sprite": "villager_a", "pos": [7, 7], "facing": "down",
				"lines": [
					"You came through the wood? With the fires? You're either brave or a wizard.",
					"...That IS a wizard's staff. Well. Keep it pointed away from the thatch.",
				],
				"lines_flag": {"knows_vine": ["The elder taught you the green word? He hasn't taught anyone in thirty years.", "Go on then. Show that Red devil what Ashwell is made of."]}},
			{"kind": "npc", "id": "villager_tom", "name": "Tom", "sprite": "villager_b", "pos": [17, 14], "facing": "left",
				"lines": [
					"Two of them came through at dawn. Red one, blue one. Throwing the sky at each other.",
					"The red one went north up the hill after. Didn't even look at us.",
				]},
			{"kind": "npc", "id": "child_pip", "name": "Pip", "sprite": "child", "pos": [12, 5], "facing": "down",
				"lines": ["Are you a wizard? Do the fire one! Do the fire one!", "Mum says wizards weave. I think that means knitting."]},
			{"kind": "npc", "id": "elder", "name": "Elder Wren", "sprite": "elder", "pos": [16, 6], "facing": "down",
				"lines": [
					"A woodcutter with a dead man's staff. Stranger things have started better stories.",
					"Listen. The Red one is on the hill north of here, and he weaves FOUR. You weave three. He will take you apart.",
					"Something has crawled into our well since the fires — a Moss Shade. Clear it out, and I will teach you a fourth word. Then we'll see about your weave.",
				],
				"lines_flag": {
					"shade_cleared": [
						"The well is quiet. You have a steady hand for a woodcutter.",
						"Here is the green word: VINE. Slow, patient, alive. Weave it like you'd plant it.",
						"Ashby in the workshop weaves three, same as you. Beat him and he'll owe you a knot — and then you'll have four.",
					],
					"knows_vine": [
						"Four words, four knots. That is a wizard's weave, John, whether you like the name or not.",
						"The Red one is waiting on the hill. Go and finish the story.",
					],
				},
				"grant_on_flag": {"flag": "shade_cleared", "spell": SPELL_VINE, "set_flag": "knows_vine",
					"text": "Elder Wren traces a slow spiral in the air.\n\nYou have learned VINE magic."}},
			{"kind": "creature", "id": "shade_v1", "enemy_id": "moss_shade", "pos": [15, 8], "requires_spell": SPELL_STONE,
				"intro": "The Moss Shade rises out of the well. Three Ward slots, woven from FIRE, WATER and STONE — things it has drunk from the ground.\n\nIt attacks with VINE, a magic you do not have. That does not matter for its Ward.",
				"on_win_flag": "shade_cleared"},
			{"kind": "wizard", "id": "ashby", "enemy_id": "hedge_wizard", "pos": [14, 14], "sprite": "hedge_mage", "facing": "up",
				"requires_flag": "knows_vine",
				"intro": "Ashby cracks his knuckles.\n\n\"Three knots against three. FIRE and STONE are my words, but I'll ward with anything. Let's see what the elder sees in you.\"",
				"on_win_flag": "beat_ashby",
				"grant_on_win": {"weave": 4, "text": "Ashby laughs and presses a cord knotted four times into your hand.\n\n\"Fair's fair. Fourth knot's yours.\"\n\nYour weave can now hold FOUR spells."},
				"lines_after": ["Go on. He's on the hill. Four knots — you can actually reach him now."],
				"lines_before": ["Not yet. The elder says you've three words but no green. Come back when you're whole."]},
			{"kind": "wizard", "id": "red_wizard", "enemy_id": "red_wizard", "pos": [10, 0], "sprite": "red_mage", "facing": "down",
				"intro": "The Red wizard does not turn around.\n\n\"The blue fool gave you his stick. Fine. Four knots, then — FIRE, WATER, STONE and the green. Let us see if a woodcutter can count.\"",
				"on_win_flag": "beat_red_wizard",
				"lines_after": ["The hill is empty. Only ash, and the smell of a story ending."]},
			{"kind": "exit", "pos": [0, 8], "to_area": "forest_deep", "to_pos": [18, 11], "facing": "left"},
			{"kind": "exit", "pos": [0, 9], "to_area": "forest_deep", "to_pos": [18, 12], "facing": "left"},
		],
	}
