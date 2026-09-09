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
	_areas["village"] = _village()
	_areas["trial_road"] = _trial_road()
	_areas["trial_gate"] = _trial_gate()
	_areas["forest_deep"] = _forest_deep()
	# forest_home is PARKED (P1): the old clearing no longer happens. Builder kept
	# for reference; nothing links to it.


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
				"grant": {},
				"text": "A pendant of red glass. Cold — whatever magic it held burned away with the wood.\n\nA reminder, not a reward. The living wood keeps its own counsel."},
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
				"grant": {},
				"text": "The golem's heart-stone. Grey and silent. Its weight is ordinary weight.\n\nNot every stone answers."},
			{"kind": "exit", "pos": [19, 12], "to_area": "trial_road", "to_pos": [18, 6], "facing": "left"},
			{"kind": "sign", "id": "deep_deadend", "pos": [8, 22], "text": "The way south is choked with fallen, half-burnt trees. Nothing that way but ash."},
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
		"TTTTTTTTTT::TTTTTTTTTT",
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
					"You're not thinking of going up there, are you, John?",
					"Six wizards through already and it's barely noon.",
				],
				"lines_flag": {"has_staff": ["That's... Halvard's staff. So it's true.", "Keep it pointed away from the thatch. And John — come back."]}},
			{"kind": "npc", "id": "neighbour_bram", "name": "Bram", "sprite": "villager_b", "pos": [4, 10], "facing": "right",
				"lines": [
					"Trial day! Best day of the year for selling beer.",
					"Worst day for finding anybody sensible to drink it with.",
				]},
			{"kind": "npc", "id": "villager_tom", "name": "Tom", "sprite": "villager_b", "pos": [17, 14], "facing": "left",
				"lines": [
					"Two wizards came through at dawn. Blue one and a red one.",
					"They were throwing the sky at each other. Trial Day's started early this year.",
				]},
			{"kind": "npc", "id": "child_pip", "name": "Pip", "sprite": "child", "pos": [12, 5], "facing": "down",
				"lines": ["Six wizards came through already. One had a bird made of fire!", "When I grow up I'm entering the Trial. Mum says over her dead body."]},
			{"kind": "npc", "id": "stall_greta", "name": "Greta", "sprite": "villager_a", "pos": [5, 7], "facing": "down",
				"lines": [
					"Charms! Fresh charms! Guaranteed* to stop anything. (*Not guaranteed.)",
					"No refunds. Especially not for heroes.",
				],
				"lines_flag": {"has_staff": ["...Is that a real wizard's staff? Put it away before somebody sees!", "Buy a charm? For luck? No? Worth a try."]}},
			{"kind": "npc", "id": "elder", "name": "Elder Wren", "sprite": "elder", "pos": [15, 5], "facing": "down",
				"lines": [
					"A woodcutter watching wizards. Stranger things have started better stories.",
					"The Trial takes them up the hill at sunset. Go and look, if you like.",
				],
				"lines_flag": {"has_staff": ["Halvard's staff. I knew him when he was younger than you.", "Ashby in the workshop was his friend once. Show him the staff."]}},
			{"kind": "trigger", "id": "duel_cutscene", "rect": [2, 8, 12, 9], "event": "duel_cutscene", "once_flag": "duel_seen", "requires_steps": 3},
			{"kind": "pickup", "id": "halvard_staff", "pos": [10, 8], "sprite": "staff", "requires_flag": "duel_seen",
				"grant": {"spell": SPELL_BLUE, "weave": 1}, "set_flag": "has_staff",
				"text": "Halvard's staff. It is cold, and it hums.\n\nYou have learned WATER magic.\nYour weave can hold ONE spell."},
			{"kind": "corpse", "id": "blue_wizard_body", "pos": [9, 8], "sprite": "blue_mage", "facing": "right", "requires_flag": "duel_seen",
				"text": "Halvard of the Blue. Whatever he was, he is not any more."},
			{"kind": "wizard", "id": "ashby_lesson1", "enemy_id": "ashby_lesson1", "pos": [14, 14], "sprite": "hedge_mage", "facing": "up",
				"requires_flag": "has_staff",
				"intro": "Ashby turns the staff over in his hands, and his face does something complicated.\n\n\"Water, and one knot. That's not wizardry yet.\"\n\n\"But it's enough for me to show you what a Ward is. Cast what you hold.\"",
				"on_win_flag": "beat_lesson1"},
			{"kind": "wizard", "id": "ashby_lesson2", "enemy_id": "ashby_lesson2", "pos": [15, 14], "sprite": "hedge_mage", "facing": "up",
				"requires_flag": "beat_lesson1",
				"intro": "\"One knot again. But this time my Ward might be Water — or Fire.\"\n\n\"If it's Fire, your one Water can't break it. That's the lesson: find out which.\"",
				"on_win_flag": "beat_lesson2"},
			{"kind": "exit", "pos": [10, 17], "to_area": "trial_road", "to_pos": [9, 12], "facing": "down"},
			{"kind": "exit", "pos": [11, 17], "to_area": "trial_road", "to_pos": [10, 12], "facing": "down"},
		],
	}


# -------------------------------------------------------------------------------
# AREA 4 — Trial road. 20 wide x 14 tall. Carnival route: village south, gate north,
# burnt wood (training) east.
# -------------------------------------------------------------------------------
static func _trial_road() -> Dictionary:
	var rows := [
		"TTTTTTTTT::TTTTTTTTT",
		"TTT......::....TTTTT",
		"TT.......::.....TTTT",
		"TT..f....::.....TTTT",
		"TT.......::..f..TTTT",
		"TT...LL..::.....TTTT",
		":::::::::::...::::::",
		":::::::::::...::::::",
		"TT.......::.....TTTT",
		"TT...r...::..,...TTT",
		"TT.......::.....TTTT",
		"TTTT.....::.....TTTT",
		"TTTT.....::.....TTTT",
		"TTTTTTTTT::TTTTTTTTT",
	]
	return {
		"id": "trial_road", "name": "Trial Road", "rows": rows,
		"entities": [
			{"kind": "sign", "id": "road_sign", "pos": [11, 1], "text": "TRIAL ROAD. Gate north. Ashwell south. Burnt wood east — mind the ash."},
			{"kind": "npc", "id": "traveller_tam", "name": "Tam", "sprite": "villager_b", "pos": [7, 2], "facing": "down",
				"lines": [
					"Walked three days to watch. My cousin entered last year.",
					"We don't talk about my cousin.",
				]},
			{"kind": "npc", "id": "merchant_sella", "name": "Sella", "sprite": "villager_a", "pos": [12, 2], "facing": "down",
				"lines": [
					"Ribbons! Roasted nuts! Trial-day prices!",
					"You look like a man about to do something stupid. Nuts?",
				]},
			{"kind": "npc", "id": "charm_odd", "name": "Odd", "sprite": "villager_b", "pos": [11, 6], "facing": "up",
				"lines": [
					"This charm belonged to a Champion. Probably.",
					"This rock is lucky. This stick is lucky. You look lucky.",
				]},
			{"kind": "npc", "id": "failed_clem", "name": "Clem", "sprite": "villager_a", "pos": [8, 9], "facing": "down",
				"lines": [
					"I got as far as the gate. The gate! Three years training.",
					"Go on. Laugh. Everyone else does.",
				]},
			{"kind": "npc", "id": "book_vess", "name": "Vess", "sprite": "villager_b", "pos": [14, 9], "facing": "down",
				"lines": [
					"Three-to-one on the Red! Five-to-one on the Knight!",
					"You? Entering? ...Twenty-to-one. No offence.",
				]},
			{"kind": "npc", "id": "healer_sage", "name": "Sage", "sprite": "elder", "pos": [7, 11], "facing": "down",
				"lines": [
					"Bandages, salves, splints. Busiest day of my year.",
					"If you're going up there: aim to come back.",
				]},
			{"kind": "creature", "id": "fly_road1", "enemy_id": "giant_fly", "pos": [13, 8],
				"intro": "A horsefly the size of a hound drops onto the path, buzzing like a saw.\n\nOne Ward slot of Water, by the smell of it — the same magic you hold. And if it goes badly, just walk away."},
			{"kind": "exit", "pos": [9, 0], "to_area": "trial_gate", "to_pos": [8, 12], "facing": "up"},
			{"kind": "exit", "pos": [10, 0], "to_area": "trial_gate", "to_pos": [9, 12], "facing": "up"},
			{"kind": "exit", "pos": [9, 13], "to_area": "village", "to_pos": [10, 16], "facing": "down"},
			{"kind": "exit", "pos": [10, 13], "to_area": "village", "to_pos": [11, 16], "facing": "down"},
			{"kind": "exit", "pos": [19, 6], "to_area": "forest_deep", "to_pos": [18, 12], "facing": "right"},
		],
	}


# -------------------------------------------------------------------------------
# AREA 5 — Trial gate. 20 wide x 14 tall. Seven entrants wait for sunset.
# -------------------------------------------------------------------------------
static func _trial_gate() -> Dictionary:
	var rows := [
		"TTTTTTTT##TTTTTTTTTT",
		"TTTTTTTT##TTTTTTTTTT",
		"TTT..........TTTTTTT",
		"TTT..........TTTTTTT",
		"TT.....ff....TTTTTTT",
		"TT............TTTTTT",
		"TT............TTTTTT",
		"TT......::....TTTTTT",
		"TT......::....TTTTTT",
		"TT......::....TTTTTT",
		"TT......::....TTTTTT",
		"TTT.....::...TTTTTTT",
		"TTT.....::...TTTTTTT",
		"TTTTTTTT::TTTTTTTTTT",
	]
	return {
		"id": "trial_gate", "name": "Trial Gate", "rows": rows,
		"entities": [
			{"kind": "sign", "id": "gate_sign", "pos": [6, 4], "text": "TRIAL GATE. Contestants only beyond this point. Spectators: enjoy the screaming."},
			{"kind": "door", "id": "gate_door_l", "pos": [8, 1], "text": "Enormous doors, shut. They open at sunset."},
			{"kind": "door", "id": "gate_door_r", "pos": [9, 1], "text": "Someone has scratched tally marks into the wood. Dozens of them."},
			{"kind": "npc", "id": "contest_knight", "name": "Serra", "sprite": "knight", "pos": [4, 5], "facing": "down",
				"lines": ["I am Serra of the White Road. First in, first out. That is how it is done."]},
			{"kind": "npc", "id": "contest_elf", "name": "Elven woman", "sprite": "elf", "pos": [5, 5], "facing": "down",
				"lines": ["You carry a dead man's staff, villager. The Trial does not care. Neither do I."]},
			{"kind": "npc", "id": "contest_throm", "name": "Throm", "sprite": "throm", "pos": [4, 6], "facing": "up",
				"lines": ["Throm. ...That is all you get before the doors."]},
			{"kind": "npc", "id": "contest_barb2", "name": "Laughing man", "sprite": "elder", "pos": [5, 6], "facing": "up",
				"lines": ["Hah! Another one come to die famous."]},
			{"kind": "npc", "id": "contest_assassin", "name": "Quiet one", "sprite": "assassin", "pos": [12, 5], "facing": "down",
				"lines": ["..."]},
			{"kind": "npc", "id": "contest_red", "name": "Red Wizard", "sprite": "red_mage", "pos": [12, 6], "facing": "up",
				"lines": ["Halvard's staff. So the old fool died in a ditch after all.", "Don't stare, villager. You'll see worse before sunset."]},
			{"kind": "npc", "id": "gate_official", "name": "Rollkeeper", "sprite": "official", "pos": [9, 3], "facing": "down",
				"lines": [
					"Names for the roll. ...John? John the woodcutter? Halvard's seal — it's genuine.",
					"The Trial takes you at sunset, if you choose it. Step to the doors when you're ready.",
				]},
			{"kind": "trigger", "id": "gate_choice", "rect": [8, 2, 9, 2], "event": "gate_choice", "no_auto_flag": true},
			{"kind": "exit", "pos": [8, 13], "to_area": "trial_road", "to_pos": [9, 12], "facing": "down"},
			{"kind": "exit", "pos": [9, 13], "to_area": "trial_road", "to_pos": [10, 12], "facing": "down"},
		],
	}
