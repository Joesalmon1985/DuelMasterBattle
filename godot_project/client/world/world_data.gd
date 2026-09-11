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
	_areas["dd_entrance"] = _dd_entrance()
	_areas["dd_fork"] = _dd_fork()
	_areas["dd_galleries"] = _dd_galleries()
	_areas["dd_pit"] = _dd_pit()
	_areas["dd_lower"] = _dd_lower()
	_areas["dd_trialmaster"] = _dd_trialmaster()
	_areas["dd_idol"] = _dd_idol()
	_areas["dd_grotto"] = _dd_grotto()
	_areas["dd_vaults"] = _dd_vaults()
	_areas["dd_vault_inner"] = _dd_vault_inner()
	_areas["dd_service"] = _dd_service()
	_areas["dd_mirror"] = _dd_mirror()
	_areas["dd_blood"] = _dd_blood()
	_areas["dd_grub"] = _dd_grub()
	_areas["dd_troglodytes"] = _dd_troglodytes()
	_areas["dd_manticore"] = _dd_manticore()
	_areas["dd_igbut"] = _dd_igbut()
	_areas["jane_placeholder"] = _jane_placeholder()


# -------------------------------------------------------------------------------
# The Burnt Wood. 20 wide x 24 tall. Entered from trial_road (east mouth).
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
				"intro": "A Flame Imp, two slots deep. Fire and Vine in its teeth; Fire and Water in its Ward.\n\nWater and Vine, two knots. Read it, and use both."},
			{"kind": "creature", "id": "imp_d2", "enemy_id": "flame_imp", "pos": [5, 10],
				"intro": "Another imp guards the pendant."},
			# Progression: the Red wizard's pendant.
			{"kind": "pickup", "id": "fire_pendant", "pos": [3, 11], "sprite": "pendant",
				"grant": {"spell": SPELL_RED, "weave": 3},
				"text": "A pendant of red glass, still warm. Whatever the Red Wizard left in it did not burn away with the wood.\n\nYou have learned FIRE magic.\nYour weave can now hold THREE spells.\n\nThe wood feels it too. Listen: everything out there just got a third knot."},
			# Tier 2
			{"kind": "creature", "id": "sprite_d1", "enemy_id": "steam_sprite", "pos": [12, 9], "requires_spell": SPELL_RED,
				"intro": "A Steam Sprite, born where the fire met the pond. THREE slots, Fire or Water — and it reads you faster than the imps did.\n\nThe wood has changed since you picked up that pendant. Everything in it has a third knot now. So do you."},
			{"kind": "creature", "id": "sprite_d2", "enemy_id": "steam_sprite", "pos": [3, 4], "requires_spell": SPELL_RED,
				"intro": "Steam hisses out of the ash."},
			{"kind": "creature", "id": "brute_d1", "enemy_id": "steam_brute", "pos": [13, 5], "requires_spell": SPELL_RED,
				"intro": "A Steam Brute. Three Ward slots of Fire and Water, and it throws Vine as well.\n\nRead the result: an exact match is a Fracture, a right spell in the wrong slot is an Echo."},
			# Tier 3 gate to the north road: Cinder Golem drops the Stone shard.
			{"kind": "creature", "id": "golem_d1", "enemy_id": "cinder_golem", "pos": [8, 2], "requires_spell": SPELL_RED,
				"intro": "A Cinder Golem blocks the old road. Three slots of Fire and Vine — but its Ward is Water and Vine, the things that put a fire out.\n\nWhat a thing attacks with is not what protects it.",
				"drops": "stone_shard"},
			{"kind": "pickup", "id": "stone_shard", "pos": [8, 2], "sprite": "stone_shard", "requires_defeated": "golem_d1",
				"grant": {"spell": SPELL_STONE},
				"text": "The golem's heart-stone. Grey, patient, heavier than it looks — and it answers.\n\nYou have learned STONE magic. A fourth colour, for the Trial."},
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
			{"kind": "logs", "id": "v_logs", "pos": [16, 15], "text": "Somebody else's woodpile. Neater than yours."},
			{"kind": "npc", "id": "villager_mara", "name": "Mara", "sprite": "villager_a", "pos": [7, 7], "facing": "down",
				"lines": [
					"You're not thinking of going up there, are you, John?",
					"Six wizards through already and it's barely noon.",
				],
				"lines_phase": {"halvard_prologue": ["Oh! You're — you're the Blue one, aren't you? Halvard? My mother had a print of you.", "Go on. The gate's north. Everyone's waiting to see you win."]},
				"lines_flag": {"has_staff": ["That's... Halvard's staff. So it's true.", "Keep it pointed away from the thatch. And John — come back."]}},
			{"kind": "npc", "id": "neighbour_bram", "name": "Bram", "sprite": "villager_b", "pos": [4, 10], "facing": "right",
				"lines": [
					"Trial day! Best day of the year for selling beer.",
					"Worst day for finding anybody sensible to drink it with.",
				],
				"lines_phase": {"halvard_prologue": ["Beer, wizard? On the house. For luck. Mine, not yours — I've got money on you."]}},
			{"kind": "npc", "id": "villager_tom", "name": "Tom", "sprite": "villager_b", "pos": [17, 14], "facing": "left",
				"lines": [
					"Two wizards, right there in the road. Blue one and a red one.",
					"They were throwing the sky at each other. Then they weren't. Then you were.",
				],
				"lines_phase": {"halvard_prologue": ["Mind the road, sir. There's a red fellow up there who keeps looking back at the village.", "Looking for someone, I'd say."]}},
			{"kind": "npc", "id": "child_pip", "name": "Pip", "sprite": "child", "pos": [12, 5], "facing": "down",
				"lines": ["Six wizards came through already. One had a bird made of fire!", "When I grow up I'm entering the Trial. Mum says over her dead body."],
				"lines_phase": {"halvard_prologue": ["Are you a REAL wizard? Do the water thing! Do it!", "Mum says you're the one who's going to win. Mum says a lot of things."]}},
			{"kind": "npc", "id": "stall_greta", "name": "Greta", "sprite": "villager_a", "pos": [5, 7], "facing": "down",
				"lines": [
					"Charms! Fresh charms! Guaranteed* to stop anything. (*Not guaranteed.)",
					"No refunds. Especially not for heroes.",
				],
				"lines_phase": {"halvard_prologue": ["A charm for the great Halvard? Free. Advertising.", "...You don't need one. Fine. Everyone else does, apparently."]},
				"lines_flag": {"has_staff": ["...Is that a real wizard's staff? Put it away before somebody sees!", "Buy a charm? For luck? No? Worth a try."]}},
			{"kind": "npc", "id": "elder", "name": "Elder Wren", "sprite": "elder", "pos": [15, 5], "facing": "down",
				"lines": [
					"A woodcutter watching wizards. Stranger things have started better stories.",
					"The Trial takes them up the hill at sunset. Go and look, if you like.",
				],
				"lines_phase": {"halvard_prologue": ["Halvard. You've aged. So has the Trial — it eats better men than it used to.", "The Red one came through an hour ago. He asked after you by name."]},
				"lines_flag": {"has_staff": ["Halvard's staff. I knew him when he was younger than you.", "Ashby in the workshop was his friend once. Show him the staff."]}},
			# Prologue (brief §1–§4): Halvard walks the village; Red intercepts on the road.
			{"kind": "trigger", "id": "red_intercept", "rect": [2, 8, 12, 9], "event": "red_intercept", "once_flag": "prologue_duel_started", "requires_steps": 3, "requires_phase": "halvard_prologue"},
			{"kind": "corpse", "id": "blue_wizard_body", "pos": [9, 8], "sprite": "blue_mage", "facing": "right", "requires_flag": "halvard_dead",
				"text": "Halvard of the Blue. Whatever he was, he is not any more."},
			{"kind": "pickup", "id": "halvard_staff", "pos": [10, 8], "sprite": "staff", "requires_flag": "halvard_dead",
				"grant": {"spells": [SPELL_BLUE, SPELL_VINE], "weave": 2}, "set_flag": "has_staff",
				"text": "Halvard's staff. It is cold, and it hums, and it does not seem to mind whose hand it is in. Something green is wound into the grain of it — old, alive.\n\nYou have learned WATER and VINE magic.\nYour weave can hold TWO spells."},
			# Ashby (brief §6–§8): one NPC, three training duels driven by story flags.
			{"kind": "npc", "id": "ashby", "name": "Ashby", "sprite": "hedge_mage", "pos": [14, 14], "facing": "up",
				"requires_flag": "has_staff",
				"lines": [], "choice_event": "ashby_training"},
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
				],
				"lines_flag": {"halvard_dead": ["Is it true? The Blue one, in the road, before the Trial even opened?", "Three days I walked. Well. The Red one still owes us a show."]}},
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
				],
				"lines_flag": {"has_staff": ["Two-to-one on the Red now that the Blue's out of it. Nobody's happy about how.", "You, with his staff? ...Fifty-to-one. I'll take your coin, but I won't feel good about it."]}},
			{"kind": "npc", "id": "healer_sage", "name": "Sage", "sprite": "elder", "pos": [7, 11], "facing": "down",
				"lines": [
					"Bandages, salves, splints. Busiest day of my year.",
					"If you're going up there: aim to come back.",
				],
				"lines_flag": {"has_staff": ["I saw them carry him in. There was nothing to bandage — the Red one is very neat.", "You hold that staff like an axe. Learn to hold it like a staff before sunset."]}},
			{"kind": "creature", "id": "fly_road1", "enemy_id": "giant_fly", "pos": [13, 8],
				"intro": "A horsefly the size of a hound drops onto the path, buzzing like a saw.\n\nTwo slots. It will lunge before it thinks — and then it will think."},
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
			{"kind": "door", "id": "gate_door_l", "pos": [8, 1], "marker": "door_closed", "text": "Enormous doors, shut. They open at sunset."},
			{"kind": "door", "id": "gate_door_r", "pos": [9, 1], "marker": "door_closed", "text": "Someone has scratched tally marks into the wood. Dozens of them."},
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


# -------------------------------------------------------------------------------
# ZONE A — Crystal entrance (p.1, 270). 20 wide x 14 tall.
# -------------------------------------------------------------------------------
static func _dd_entrance() -> Dictionary:
	var rows := [
		"TTTTTTTT::TTTTTTTTTT",
		"TTTT....::....TTTTTT",
		"TTT.....::.....TTTTT",
		"TTT.....::.....TTTTT",
		"TT......::......TTTT",
		"TT......::......TTTT",
		"TT......::......TTTT",
		"TT......::......TTTT",
		"TT......::......TTTT",
		"TT......::......TTTT",
		"TTT.....::.....TTTTT",
		"TTT.....::.....TTTTT",
		"TTTT....::....TTTTTT",
		"TTTTTTTT::TTTTTTTTTT",
	]
	return {
		"id": "dd_entrance", "name": "Crystal Entrance", "rows": rows,
		"entities": [
			{"kind": "sign", "id": "dd_crystal", "pos": [11, 3], "text": "Crystal veins in the walls hum faintly. The light has no source."},
			{"kind": "logs", "id": "dd_table", "pos": [12, 5], "text": "A stone table. Six boxes — five already taken. The contestants ahead of you helped themselves."},
			{"kind": "pickup", "id": "aid_box", "pos": [7, 5], "sprite": "box", "run_pickup": true,
				"grant": {},
				"text": "A box bearing a familiar seal: HALVARD.\n\nInside: two gold pieces, and a note in a sharp hand — SUKUMVIT: 'The Trial wants useful things, not just strong arms. Carry what matters.'"},
			{"kind": "exit", "pos": [9, 0], "to_area": "dd_fork", "to_pos": [9, 12], "facing": "up"},
			{"kind": "exit", "pos": [8, 0], "to_area": "dd_fork", "to_pos": [8, 12], "facing": "up"},
		],
	}


# -------------------------------------------------------------------------------
# ZONE A — First footprint fork (p.66, 119). 20 wide x 14 tall.
# -------------------------------------------------------------------------------
static func _dd_fork() -> Dictionary:
	var rows := [
		"TTTTTTTTTTTTTTTTTTTT",
		"TTTTTTTTTTTTTTTTTTTT",
		"TTTT......TTTTTTTTTT",
		"TTTT......TTTTTTTTTT",
		"TTTT......TTTTTTTTTT",
		"TTTT......TTTTTTTTTT",
		"::::::::::::::::::::",
		"::::::::::::::::::::",
		"TTTT......TTTTTTTTTT",
		"TTTT......TTTTTTTTTT",
		"TT........TTTTTTTTTT",
		"TT........TTTTTTTTTT",
		"TT........TTTTTTTTTT",
		"TTTTTTTTTTTTTTTTTTTT",
	]
	return {
		"id": "dd_fork", "name": "Footprint Fork", "rows": rows,
		"entities": [
			{"kind": "sign", "id": "dd_arrow", "pos": [6, 3], "text": "A white arrow, painted fresh, points WEST. Below it, in charcoal: 'don't'."},
			{"kind": "sign", "id": "dd_prints_west", "pos": [5, 5], "text": "Wet footprints — several sets — head west along the road."},
			{"kind": "sign", "id": "dd_prints_east", "pos": [7, 5], "text": "One set of prints, smaller, goes east."},
			{"kind": "creature", "id": "fly_east", "enemy_id": "giant_fly", "pos": [16, 6],
				"intro": "Something huge buzzes in the eastern dark. It smells of Water.",
				"on_win_run_flag": "fork_east_open"},
			{"kind": "sign", "id": "dd_east_draught", "pos": [15, 7], "text": "A cold draught from the east, and a single small footprint pressed into the wet. Someone slight went this way and did not come back for their box."},
			{"kind": "exit", "pos": [19, 6], "to_area": "dd_service", "to_pos": [9, 1], "facing": "down", "requires_run_flag": "fork_east_open", "shortcut": true},
			{"kind": "exit", "pos": [19, 7], "to_area": "dd_service", "to_pos": [10, 1], "facing": "down", "requires_run_flag": "fork_east_open", "shortcut": true},
			{"kind": "logs", "id": "dd_empty_box", "pos": [17, 7], "text": "An open box, its seal broken. Someone got here first — and went west."},
			{"kind": "exit", "pos": [0, 6], "to_area": "dd_galleries", "to_pos": [20, 8], "facing": "left"},
			{"kind": "exit", "pos": [0, 7], "to_area": "dd_galleries", "to_pos": [20, 9], "facing": "left"},
			{"kind": "exit", "pos": [8, 12], "to_area": "dd_entrance", "to_pos": [9, 1], "facing": "down"},
			{"kind": "exit", "pos": [9, 12], "to_area": "dd_entrance", "to_pos": [10, 1], "facing": "down"},
		],
	}


# -------------------------------------------------------------------------------
# ZONE B — Footprint galleries + statue riddle (p.293, 382). 22 wide x 16 tall.
# -------------------------------------------------------------------------------
static func _dd_galleries() -> Dictionary:
	var rows := [
		"TTTTTTTTTTTTTTTTTTTTTT",
		"TTTT..............TTTT",
		"TTTT..............TTTT",
		"TTTT......::......TTTT",
		"TTTT......::......TTTT",
		"TTTT......::......TTTT",
		"TT..................TT",
		"TT..................TT",
		"::::::::::::::::::::::",
		"::::::::::::::::::::::",
		"TT..................TT",
		"TT..................TT",
		"TTTT..............TTTT",
		"TTTT......rr......TTTT",
		"TTTT..............TTTT",
		"TTTTTTTTTTTTTTTTTTTTTT",
	]
	return {
		"id": "dd_galleries", "name": "Footprint Galleries", "rows": rows,
		"entities": [
			{"kind": "npc", "id": "dd_old_man", "name": "Old man", "sprite": "elder", "pos": [9, 4], "facing": "down",
				"lines": ["One hundred? One hundred and fifty? Two hundred? Answer, if the stone lets you."],
				"choice_event": "statue_riddle"},
			{"kind": "corpse", "id": "dd_knight_statue", "pos": [12, 4], "sprite": "knight", "facing": "down",
				"text": "Not a statue. A knight in White Road armour, turned to stone mid-step.\n\nSerra went first. This is where first got her."},
			{"kind": "logs", "id": "dd_bell", "pos": [5, 6], "text": "A bronze bell on a rope. Ringing it would tell EVERYTHING down here where you are. You don't."},
			{"kind": "logs", "id": "dd_chest", "pos": [16, 6], "text": "A chest, sprung and empty. The scratches around the lock are fresh."},
			{"kind": "pickup", "id": "dd_torch", "pos": [5, 13], "sprite": "staff", "run_pickup": true,
				"grant": {},
				"text": "A dry torch, still good. Someone thoughtful left it. Or careless."},
			{"kind": "creature", "id": "dog_gal1", "enemy_id": "guard_dog", "pos": [14, 8],
				"intro": "A Trialmastiff pads out of the dark, silent until it isn't.\n\nOne Ward slot. Water, by the drool."},
			{"kind": "exit", "pos": [0, 8], "to_area": "dd_pit", "to_pos": [19, 8], "facing": "left"},
			{"kind": "exit", "pos": [0, 9], "to_area": "dd_pit", "to_pos": [19, 9], "facing": "left"},
			{"kind": "exit", "pos": [21, 8], "to_area": "dd_fork", "to_pos": [1, 6], "facing": "right"},
			{"kind": "exit", "pos": [21, 9], "to_area": "dd_fork", "to_pos": [1, 7], "facing": "right"},
		],
	}


# -------------------------------------------------------------------------------
# ZONE D — Throm pit (p.154, 22, 184). 20 wide x 14 tall.
# -------------------------------------------------------------------------------
static func _dd_pit() -> Dictionary:
	var rows := [
		"TTTTTTTTTTTTTTTTTTTT",
		"TTT..............TTT",
		"TT................TT",
		"TT................TT",
		"TT.....rrrr......TTT",
		"TT.....rrrr......TTT",
		"TT.....rrrr......TTT",
		"TT.....rrrr......TTT",
		"....................",
		"....................",
		"TT................TT",
		"TTT..............TTT",
		"TTT..............TTT",
		"TTTTTTTTTTTTTTTTTTTT",
	]
	return {
		"id": "dd_pit", "name": "Throm's Pit", "rows": rows,
		"entities": [
			{"kind": "sign", "id": "dd_pit_mouth", "pos": [6, 4], "text": "A deep pit. Black water far below. A rope is tied to a spike — the knots are barbarian work."},
			{"kind": "npc", "id": "dd_throm", "name": "Throm", "sprite": "throm", "pos": [6, 6], "facing": "right",
				"lines": ["You walk loud, villager.", "Only one of us wins this. Remember it while I hold the rope."],
				"lines_run_flag": {
					"pit_ally": ["Lowered you fair. Don't make me regret it.", "West. And keep up."],
					"pit_betrayed": ["..."],
					"pit_jump": ["Ha! Mad. I like mad. West, then."]},
				"choice_event": "throm_pit"},
			{"kind": "exit", "pos": [0, 8], "to_area": "dd_lower", "to_pos": [21, 5], "facing": "left"},
			{"kind": "exit", "pos": [0, 9], "to_area": "dd_lower", "to_pos": [21, 6], "facing": "left"},
			{"kind": "exit", "pos": [19, 8], "to_area": "dd_galleries", "to_pos": [1, 8], "facing": "right"},
			{"kind": "exit", "pos": [19, 9], "to_area": "dd_galleries", "to_pos": [1, 9], "facing": "right"},
		],
	}


# -------------------------------------------------------------------------------
# ZONE D — Lower route: books + Cave Trolls (p.194, 138, 52, 169, 288). 22 x 14.
# -------------------------------------------------------------------------------
static func _dd_lower() -> Dictionary:
	var rows := [
		"TTTTTTTTTTTTTTTTTTTTTT",
		"TTT...............TTTT",
		"TT..................TT",
		"TT..................TT",
		"TT...LL.............TT",
		"......................",
		"......................",
		"TT.........rr.......TT",
		"TT..................TT",
		"TT..................TT",
		"TT..................TT",
		"TT..................TT",
		"TTT...............TTTT",
		"TTTTTTTTTTTTTTTTTTTTTT",
	]
	return {
		"id": "dd_lower", "name": "Lower Route", "rows": rows,
		"entities": [
			{"kind": "pickup", "id": "red_book", "pos": [5, 4], "sprite": "book_red", "run_pickup": true,
				"grant": {"weave": 4},
				"text": "A red-bound book, chained to the alcove. It opens for you like it was waiting, and the diagram inside is of a hand with one more finger than yours.\n\nYour weave can now hold FOUR spells."},
			{"kind": "pickup", "id": "black_book", "pos": [6, 4], "sprite": "book_black", "run_pickup": true,
				"grant": {},
				"text": "A black-bound book. Beside it, a vial of something that moves when you don't look.\n\nYou take the vial.",
				"choice_event": "black_book"},
			{"kind": "npc", "id": "dd_throm_lower", "name": "Throm", "sprite": "throm", "pos": [4, 5], "facing": "right",
				"lines": ["Books. We don't have time for books.", "Read the red one if you must. Quickly."],
				"lines_run_flag": {"troll_down": ["...My arm. Keep walking. Don't look at it."]}},
			{"kind": "creature", "id": "troll_lower1", "enemy_id": "cave_troll", "pos": [15, 7],
				"intro": "Two Cave Trolls blunder in, clubs up — and Throm is suddenly beside you, smelling of rope and anger.\n\n\"Mine's the big one,\" he says, and takes it.\n\nYours weaves Fire and Water behind two slots.",
				"on_win_run_flag": "troll_down"},
			{"kind": "pickup", "id": "bone_ring", "pos": [15, 9], "sprite": "ring", "run_pickup": true,
				"requires_defeated": "troll_lower1",
				"grant": {},
				"text": "A druidic bone ring. Warm in a way bone should not be.\n\nThrom: \"Don't.\"\n\n(You take it anyway. Nothing happens. Yet.)"},
			{"kind": "door", "id": "dwarf_door", "pos": [2, 5], "text": "A stone door with dwarfish locks. It is not for you. Yet."},
			{"kind": "exit", "pos": [0, 5], "to_area": "dd_trialmaster", "to_pos": [20, 8], "facing": "left", "requires_run_flag": "troll_down"},
			{"kind": "exit", "pos": [0, 6], "to_area": "dd_trialmaster", "to_pos": [20, 9], "facing": "left", "requires_run_flag": "troll_down"},
			{"kind": "exit", "pos": [21, 5], "to_area": "dd_pit", "to_pos": [1, 8], "facing": "right"},
			{"kind": "exit", "pos": [21, 6], "to_area": "dd_pit", "to_pos": [1, 9], "facing": "right"},
		],
	}


# -------------------------------------------------------------------------------
# ZONE E — Dwarf Trialmaster complex (p.60, 365, 302, 379). 22 wide x 14 tall.
# -------------------------------------------------------------------------------
static func _dd_trialmaster() -> Dictionary:
	var rows := [
		"TTTTTTTTTTTTTTTTTTTTTT",
		"TTTT..............TTTT",
		"TTTT..............TTTT",
		"TTTT......::......TTTT",
		"TTTT......::......TTTT",
		"TTTT......::......TTTT",
		"TT..................TT",
		"TT..................TT",
		"......................",
		"......................",
		"TT..................TT",
		"TT..................TT",
		"TTTT..............TTTT",
		"TTTT:TTTTTTTTTTTTTTTTT",
	]
	return {
		"id": "dd_trialmaster", "name": "Trialmaster Complex", "rows": rows,
		"entities": [
			{"kind": "npc", "id": "dd_dwarf", "name": "Dwarf", "sprite": "dwarf", "pos": [9, 4], "facing": "down",
				"lines": ["John. And Throm. The Trialmaster at your service — locked doors are my speciality."],
				"lines_run_flag": {
					"pit_betrayed": ["John. Alone. The Trialmaster at your service — locked doors are my speciality."],
					"trial_ready": ["The cobra is ready. He waits in the arena. Finish it."],
					"trial_done": ["The way is open. Go, and don't thank me."]},
				"choice_event": "dwarf_meet"},
			{"kind": "sign", "id": "dd_dice_table", "pos": [6, 4], "text": "A stone table with two dice in a cup. Someone has been practising probabilities."},
			{"kind": "wizard", "id": "throm_arena", "enemy_id": "throm_duel", "pos": [4, 7], "sprite": "throm", "facing": "right",
				"requires_run_flag": "trial_ready",
				"intro": "They drag Throm into the arena. His eyes don't know you. The cobra's work.\n\n\"John?\" he says. \"No. Not John. FIGHT.\"\n\nThree slots of barbarian fury — fast, and wrong. Defend yourself.",
				"on_win_run_flag": "trial_done"},
			{"kind": "sign", "id": "dd_tunnel_tease", "pos": [3, 8], "text": "A concealed tunnel breathes cold air from the south-west corner. The Dwarf's crossbow does not waver. Not yet.",
				"text_run_flag": {"trial_done": "The concealed tunnel in the south-west corner stands open. The Dwarf shrugs: 'Staff passage. Comes out by the lion-thing. Don't say I never gave you anything.'"}},
			{"kind": "exit", "pos": [4, 13], "to_area": "dd_manticore", "to_pos": [3, 2], "facing": "down", "requires_run_flag": "trial_done", "shortcut": true},
			{"kind": "exit", "pos": [21, 8], "to_area": "dd_lower", "to_pos": [1, 5], "facing": "right"},
			{"kind": "exit", "pos": [21, 9], "to_area": "dd_lower", "to_pos": [1, 6], "facing": "right"},
			{"kind": "exit", "pos": [0, 8], "to_area": "dd_idol", "to_pos": [18, 8], "facing": "left", "requires_run_flag": "trial_done"},
			{"kind": "exit", "pos": [0, 9], "to_area": "dd_idol", "to_pos": [18, 9], "facing": "left", "requires_run_flag": "trial_done"},
		],
	}


# -------------------------------------------------------------------------------
# ZONE C — Idol cavern, Emerald (p.37, 240). 20 wide x 14 tall.
# -------------------------------------------------------------------------------
static func _dd_idol() -> Dictionary:
	var rows := [
		"TTTTTTTTTTTTTTTTTTTT",
		"TTT..............TTT",
		"TT................TT",
		"TT................TT",
		"TT......rrrr......TT",
		"TT......rrrr......TT",
		"TT......rrrr......TT",
		"TT......rrrr......TT",
		"....................",
		"....................",
		"TT................TT",
		"TTT..............TTT",
		"TTT..............TTT",
		"TTTTTTTTTTTTTTTTTTTT",
	]
	return {
		"id": "dd_idol", "name": "Idol Cavern", "rows": rows,
		"entities": [
			{"kind": "sign", "id": "dd_idol_sign", "pos": [10, 2], "marker": "idol", "text": "An idol twice your height, jewel-eyed, bird-guarded. It is smiling the way doors smile.\n\nIts left eye — your right, as you face it — is smaller, duller, and set deep. The other is enormous and catches the torchlight far too well. Around its base, in a dozen hands: WEST EYE. The rest of each sentence has been scratched out."},
			{"kind": "creature", "id": "guard_idol1", "enemy_id": "flying_guardian", "pos": [6, 8],
				"intro": "The stuffed birds open their eyes. All of them.\n\nTwo Ward slots of whatever shines — read them like Ashby taught you."},
			{"kind": "creature", "id": "guard_idol2", "enemy_id": "flying_guardian", "pos": [12, 8],
				"intro": "The second guardian unfolds from the idol's shoulder."},
			{"kind": "pickup", "id": "emerald_eye", "pos": [8, 4], "sprite": "stone_shard", "run_pickup": true,
				"requires_defeated": "guard_idol2",
				"grant": {"gem": "emerald"},
				"text": "The emerald eye comes away in your hand. It is heavier than a sin.\n\nEMERALD acquired."},
			{"kind": "pickup", "id": "false_eye", "pos": [11, 4], "sprite": "stone_shard", "run_pickup": true,
				"grant": {},
				"text": "The east eye glitters. Bigger. Greener. The scratched warnings around the base were about this one.",
				"choice_event": "false_eye"},
			{"kind": "exit", "pos": [19, 8], "to_area": "dd_trialmaster", "to_pos": [1, 8], "facing": "right"},
			{"kind": "exit", "pos": [19, 9], "to_area": "dd_trialmaster", "to_pos": [1, 9], "facing": "right"},
			{"kind": "exit", "pos": [0, 8], "to_area": "dd_grotto", "to_pos": [19, 7], "facing": "left"},
			{"kind": "exit", "pos": [0, 9], "to_area": "dd_grotto", "to_pos": [19, 8], "facing": "left"},
		],
	}


# -------------------------------------------------------------------------------
# ZONE I — Elf grotto, Boa, Vine (p.281, 399). 20 wide x 14 tall.
# -------------------------------------------------------------------------------
static func _dd_grotto() -> Dictionary:
	var rows := [
		"TTTTTTTTTTTTTTTTTTTT",
		"TTT..............TTT",
		"TT................TT",
		"TT......~~~~......TT",
		"TT......~~~~......TT",
		"TT................TT",
		"TT................TT",
		"....................",
		"....................",
		"TT................TT",
		"TT................TT",
		"TTT..............TTT",
		"TTT..............TTT",
		"TTTTTTTTTTTTTTTTTTTT",
	]
	return {
		"id": "dd_grotto", "name": "Drowned Grotto", "rows": rows,
		"entities": [
			{"kind": "creature", "id": "boa_grotto1", "enemy_id": "boa_constrictor", "pos": [10, 6],
				"intro": "A Boa Constrictor is crushing an elven woman against the rocks. She sees you.\n\nThree slots. Break it or bury her."},
			{"kind": "npc", "id": "dd_elf", "name": "Dying elf", "sprite": "elf", "pos": [9, 8], "facing": "up",
				"lines": ["...help... the snake..."],
				"lines_run_flag": {"elf_gone": ["She is gone. The hollow smells of bread and dust."]},
				"choice_event": "elf_rescue"},
			{"kind": "pickup", "id": "elf_bread", "pos": [8, 9], "sprite": "seed", "run_pickup": true,
				"requires_defeated": "boa_grotto1",
				"grant": {}, "clear_conditions": true,
				"text": "Her bread, packed with healing herbs. You eat. The shaking stops.\n\n(Your conditions are cleared.)"},
			{"kind": "pickup", "id": "elf_charm", "pos": [11, 9], "sprite": "pendant", "run_pickup": true,
				"requires_defeated": "boa_grotto1",
				"grant": {"run_flag": "has_elf_charm"}, "set_flag": "diamond_clue",
				"text": "Her vine-charm. It curls around your wrist like it was always yours. Green things will know you carry it — and the snake did not like her for it."},
			{"kind": "sign", "id": "dd_grotto_undertow", "pos": [10, 5], "text": "The pool has an undertow. Something down there pulls east — a flooded passage, for anyone who can hold their breath long enough."},
			{"kind": "exit", "pos": [9, 5], "to_area": "dd_troglodytes", "to_pos": [11, 4], "facing": "down", "requires_run_flag": "picked_dd_tube", "shortcut": true,
				"travel_text": "Reed between your teeth, you let the undertow take you. Drums, muffled by water, then air."},
			{"kind": "exit", "pos": [19, 7], "to_area": "dd_idol", "to_pos": [1, 8], "facing": "right"},
			{"kind": "exit", "pos": [19, 8], "to_area": "dd_idol", "to_pos": [1, 9], "facing": "right"},
			{"kind": "exit", "pos": [0, 7], "to_area": "dd_vaults", "to_pos": [21, 7], "facing": "left"},
			{"kind": "exit", "pos": [0, 8], "to_area": "dd_vaults", "to_pos": [21, 8], "facing": "left"},
		],
	}


# -------------------------------------------------------------------------------
# ZONE I — Sapphire vaults + diamonds (p.162, 218, 269). 22 wide x 14 tall.
# -------------------------------------------------------------------------------
static func _dd_vaults() -> Dictionary:
	var rows := [
		"TTTTTTTTTTTTTTTTTTTTTT",
		"TTTT..............TTTT",
		"TTTT..............TTTT",
		"TTTT......::......TTTT",
		"TTTT......::......TTTT",
		"TTTT......::......TTTT",
		"TT..................TT",
		"......................",
		"......................",
		"TT..................TT",
		"TT..................TT",
		"TTTT..............TTTT",
		"TTTT..............TTTT",
		"TTTTTTTTTTTTTTTTTTTTTT",
	]
	return {
		"id": "dd_vaults", "name": "Sapphire Vaults", "rows": rows,
		"entities": [
			{"kind": "pickup", "id": "sapphire_box", "pos": [9, 2], "sprite": "box", "run_pickup": true,
				"grant": {"gem": "sapphire", "run_flag": "iron_key"},
				"text": "A box, an iron key, and a sapphire the size of a robin's egg.\n\nSAPPHIRE acquired — and the key fits the northern lock."},
			{"kind": "pickup", "id": "false_diamond", "pos": [14, 12], "sprite": "diamond", "run_pickup": true,
				"grant": {},
				"text": "A diamond beside a fallen warrior, just lying there. Every instinct says trap.",
				"choice_event": "false_diamond"},
			{"kind": "exit", "pos": [11, 1], "to_area": "dd_vault_inner", "to_pos": [7, 8], "facing": "up", "requires_run_flag": "iron_key", "blocked_by_run_flag": "vault_alarm"},
			{"kind": "sign", "id": "dd_vault_bolt", "pos": [10, 1], "text": "The inner vault door. Iron, keyed.", "text_run_flag": {"vault_alarm": "The inner vault door — bolted from inside since you touched the warrior's jewel. No key opens a bolt. The Basket man's rope might."}},
			{"kind": "exit", "pos": [21, 7], "to_area": "dd_grotto", "to_pos": [1, 7], "facing": "right"},
			{"kind": "exit", "pos": [21, 8], "to_area": "dd_grotto", "to_pos": [1, 8], "facing": "right"},
			{"kind": "exit", "pos": [0, 7], "to_area": "dd_service", "to_pos": [19, 7], "facing": "left"},
			{"kind": "exit", "pos": [0, 8], "to_area": "dd_service", "to_pos": [19, 8], "facing": "left"},
		],
	}


# -------------------------------------------------------------------------------
# ZONE I — Inner vault, true Diamond (p.269). 14 wide x 10 tall.
# -------------------------------------------------------------------------------
static func _dd_vault_inner() -> Dictionary:
	var rows := [
		"TTTTTTTTTTTTTT",
		"TTT........TTT",
		"TT..........TT",
		"TT..........TT",
		"TT..........TT",
		"TT..........TT",
		"TT..........TT",
		"TT..........TT",
		"TTT........TTT",
		"TTTTTT::TTTTTT",
	]
	return {
		"id": "dd_vault_inner", "name": "Inner Vault", "rows": rows,
		"entities": [
			{"kind": "exit", "pos": [6, 9], "to_area": "dd_service", "to_pos": [9, 12], "facing": "up", "requires_run_flag": "basket_ok", "travel_text": "Down the rope-shaft, the basket swaying. The Basket man catches it without looking up.", "shortcut": true},
			{"kind": "exit", "pos": [7, 9], "to_area": "dd_service", "to_pos": [10, 12], "facing": "up", "requires_run_flag": "basket_ok", "travel_text": "Down the rope-shaft, the basket swaying. The Basket man catches it without looking up.", "shortcut": true},
			{"kind": "sign", "id": "dd_lift_shaft", "pos": [7, 8], "text": "A rope-shaft drops through the floor. Far below, someone whistles tunelessly and waits for a fare."},
			{"kind": "pickup", "id": "true_diamond", "pos": [7, 4], "sprite": "diamond", "run_pickup": true,
				"grant": {"gem": "diamond"},
				"text": "A diamond in a hall of echoes — real, cold, and yours.\n\nDIAMOND acquired."},
			{"kind": "exit", "pos": [6, 8], "to_area": "dd_vaults", "to_pos": [10, 1], "facing": "down"},
		],
	}


# -------------------------------------------------------------------------------
# ZONE H — Service layer: prisoner, Ivy, basket (P5 support). 20 wide x 14 tall.
# -------------------------------------------------------------------------------
static func _dd_service() -> Dictionary:
	var rows := [
		"TTTTTTTTT::TTTTTTTTT",
		"TTT..............TTT",
		"TT................TT",
		"TT................TT",
		"TT................TT",
		"TT................TT",
		"TT................TT",
		"....................",
		"....................",
		"TT................TT",
		"TT................TT",
		"TTT..............TTT",
		"TTT..............TTT",
		"TTTTTTTTT::TTTTTTTTT",
	]
	return {
		"id": "dd_service", "name": "Service Tunnels", "rows": rows,
		"entities": [
			{"kind": "npc", "id": "dd_prisoner", "name": "Starved man", "sprite": "villager_a", "pos": [6, 6], "facing": "down",
				"lines": ["...failed... they took my eyes... no, my boots..."],
				"lines_run_flag": {"prisoner_free": ["Go. Stones. It loves... no. It HATES the green. Vine. Its eyes water."]},
				"choice_event": "free_prisoner"},
			{"kind": "npc", "id": "dd_ivy", "name": "Poison Ivy", "sprite": "ivy", "pos": [12, 6], "facing": "down",
				"lines": ["Tribute, sweetling. Something useful, or thorns."],
				"lines_run_flag": {"ivy_paid": ["Paid in full. Walk soft, sweetling."]},
				"choice_event": "ivy_toll"},
			{"kind": "npc", "id": "dd_basket", "name": "Basket man", "sprite": "villager_b", "pos": [9, 10], "facing": "up",
				"lines": ["Up or down? I only work the rope. Don't ask about the screams."],
				"lines_run_flag": {"basket_ok": ["Up, then. Mind your fingers on the way past the vault ceiling."]},
				"choice_event": "basket_ride"},
			{"kind": "exit", "pos": [9, 0], "to_area": "dd_fork", "to_pos": [18, 6], "facing": "left", "requires_run_flag": "fork_east_open", "shortcut": true},
			{"kind": "exit", "pos": [10, 0], "to_area": "dd_fork", "to_pos": [18, 7], "facing": "left", "requires_run_flag": "fork_east_open", "shortcut": true},
			{"kind": "exit", "pos": [9, 13], "to_area": "dd_vault_inner", "to_pos": [6, 8], "facing": "up", "requires_run_flag": "basket_ok", "shortcut": true,
				"travel_text": "The basket creaks upward. Stone slides past your face for a long time."},
			{"kind": "exit", "pos": [10, 13], "to_area": "dd_vault_inner", "to_pos": [7, 8], "facing": "up", "requires_run_flag": "basket_ok", "shortcut": true,
				"travel_text": "The basket creaks upward. Stone slides past your face for a long time."},
			{"kind": "sign", "id": "dd_shaft_sign", "pos": [10, 2], "text": "A crawl-shaft climbs north. Small footprints on the rungs, going up. The assassin's way in — or out."},
			{"kind": "sign", "id": "dd_servants", "pos": [14, 4], "text": "A duty roster, scratched in charcoal. Names, days, arrows. The Trial is somebody's job."},
			{"kind": "exit", "pos": [19, 7], "to_area": "dd_vaults", "to_pos": [1, 7], "facing": "right"},
			{"kind": "exit", "pos": [19, 8], "to_area": "dd_vaults", "to_pos": [1, 8], "facing": "right"},
			{"kind": "exit", "pos": [0, 7], "to_area": "dd_mirror", "to_pos": [19, 7], "facing": "left"},
			{"kind": "exit", "pos": [0, 8], "to_area": "dd_mirror", "to_pos": [19, 8], "facing": "left"},
		],
	}


# -------------------------------------------------------------------------------
# ZONE G — Mirror gallery: demon + Light (environmental solutions first).
# -------------------------------------------------------------------------------
static func _dd_mirror() -> Dictionary:
	var rows := [
		"TTTTTTTTTTTTTTTTTTTT",
		"TTT..............TTT",
		"TT................TT",
		"TT................TT",
		"TT................TT",
		"TT................TT",
		"TT................TT",
		"....................",
		"....................",
		"TT................TT",
		"TT................TT",
		"TTT..............TTT",
		"TTT..............TTT",
		"TTTTTTTTTTTTTTTTTTTT",
	]
	return {
		"id": "dd_mirror", "name": "Mirror Gallery", "rows": rows,
		"entities": [
			{"kind": "sign", "id": "dd_mirrors", "pos": [10, 4], "marker": "mirror", "text": "Tall mirrors, silver-backed. Something moves in them a breath after you do.",
				"choice_event": "mirror_smash"},
			{"kind": "creature", "id": "demon_mirror1", "enemy_id": "mirror_demon", "pos": [10, 6],
				"intro": "What steps out of the glass is made of looking back.\n\nThree slots of reflected things — never what it casts. (Or smash the mirrors instead.)"},
			{"kind": "pickup", "id": "light_shard", "pos": [10, 2], "sprite": "stone_shard", "run_pickup": true,
				"requires_defeated": "demon_mirror1",
				"grant": {"spell": 4},
				"text": "A shard of mirror-light. It wants to be a spell.\n\nYou have learned LIGHT magic."},
			{"kind": "exit", "pos": [19, 7], "to_area": "dd_service", "to_pos": [1, 7], "facing": "right"},
			{"kind": "exit", "pos": [19, 8], "to_area": "dd_service", "to_pos": [1, 8], "facing": "right"},
			{"kind": "exit", "pos": [0, 7], "to_area": "dd_blood", "to_pos": [19, 7], "facing": "left"},
			{"kind": "exit", "pos": [0, 8], "to_area": "dd_blood", "to_pos": [19, 8], "facing": "left"},
		],
	}


# -------------------------------------------------------------------------------
# ZONE G — Bloodbeast lair: knowledge-sensitive boss + Shadow.
# -------------------------------------------------------------------------------
static func _dd_blood() -> Dictionary:
	var rows := [
		"TTTTTTTTTTTTTTTTTTTT",
		"TTT..............TTT",
		"TT................TT",
		"TT......rrrr......TT",
		"TT......rrrr......TT",
		"TT................TT",
		"TT................TT",
		"....................",
		"....................",
		"TT................TT",
		"TT................TT",
		"TTT..............TTT",
		"TTT..............TTT",
		"TTTTTTTTTTTTTTTTTTTT",
	]
	return {
		"id": "dd_blood", "name": "Bloodbeast Lair", "rows": rows,
		"entities": [
			{"kind": "pickup", "id": "blood_clue", "pos": [8, 5], "sprite": "seed", "run_pickup": true,
				"grant": {"run_flag": "blood_weakness"},
				"text": "Bitter herbs, chewed and spat out. Something with a tongue hates Vine the way fire hates water.\n\n(Bloodbeast weakness learned: no Vine in its Ward.)"},
			{"kind": "creature", "id": "beast_blood1", "enemy_id": "bloodbeast", "pos": [12, 7],
				"intro": "Four slots of hunger unhinge the dark.\n\nBreak it — and what it was will teach you Shadow.",
				"grant_on_win": {"spell": 5, "text": "The beast dissolves into its own shadow, and the shadow stays.\n\nYou have learned SHADOW magic."}},
			{"kind": "exit", "pos": [19, 7], "to_area": "dd_mirror", "to_pos": [1, 7], "facing": "right"},
			{"kind": "exit", "pos": [19, 8], "to_area": "dd_mirror", "to_pos": [1, 8], "facing": "right"},
			{"kind": "exit", "pos": [0, 7], "to_area": "dd_grub", "to_pos": [19, 7], "facing": "left"},
			{"kind": "exit", "pos": [0, 8], "to_area": "dd_grub", "to_pos": [19, 8], "facing": "left"},
		],
	}


# -------------------------------------------------------------------------------
# ZONE G — Grub tunnels: duel, boulder run, trapped chest.
# -------------------------------------------------------------------------------
static func _dd_grub() -> Dictionary:
	var rows := [
		"TTTTTTTTTTTTTTTTTTTT",
		"TTT..............TTT",
		"TT................TT",
		"TT......rrrr......TT",
		"TT......rrrr......TT",
		"TT................TT",
		"TT................TT",
		"....................",
		"....................",
		"TT................TT",
		"TT................TT",
		"TTT..............TTT",
		"TTT..............TTT",
		"TTTTTTTTTTTTTTTTTTTT",
	]
	return {
		"id": "dd_grub", "name": "Grub Tunnels", "rows": rows,
		"entities": [
			{"kind": "creature", "id": "grub_grub1", "enemy_id": "rock_grub", "pos": [10, 7],
				"intro": "The floor breathes. Then it opens.\n\nBlind, heat-sensing, enormous. Three slots — and it can smell your torch."},
			{"kind": "sign", "id": "boulder_sign", "pos": [10, 5], "text": "A side tunnel slopes down into the dark. Dust falls in a steady trickle, and the floor here is scored with one long, round-bottomed groove. Something heavy has come down this slope before.",
				"choice_event": "boulder_run"},
			{"kind": "sign", "id": "dd_chest_marks", "pos": [14, 11], "text": "Scratches in the stone floor around the chest: a fan of gouges, all the same length, all pointing outward. Whatever the lid does, it does it fast and low."},
			{"kind": "pickup", "id": "trapped_chest", "pos": [15, 10], "sprite": "box", "run_pickup": true,
				"grant": {},
				"text": "An iron-bound chest, lid a finger's width open. Gold glints inside. So does something else, at floor height.",
				"choice_event": "trapped_chest"},
			{"kind": "exit", "pos": [19, 7], "to_area": "dd_blood", "to_pos": [1, 7], "facing": "right"},
			{"kind": "exit", "pos": [19, 8], "to_area": "dd_blood", "to_pos": [1, 8], "facing": "right"},
			{"kind": "exit", "pos": [0, 7], "to_area": "dd_troglodytes", "to_pos": [19, 7], "facing": "left"},
			{"kind": "exit", "pos": [0, 8], "to_area": "dd_troglodytes", "to_pos": [19, 8], "facing": "left"},
		],
	}


# -------------------------------------------------------------------------------
# ZONE F — Troglodyte river cavern: ritual, arrow, or champion.
# -------------------------------------------------------------------------------
static func _dd_troglodytes() -> Dictionary:
	var rows := [
		"TTTTTTTTTTTTTTTTTTTT",
		"TTT..............TTT",
		"TT................TT",
		"TT......~~~~......TT",
		"TT......===.......TT",
		"TT................TT",
		"TT................TT",
		"....................",
		"....................",
		"TT................TT",
		"TT................TT",
		"TTT..............TTT",
		"TTT..............TTT",
		"TTTTTTTTTTTTTTTTTTTT",
	]
	return {
		"id": "dd_troglodytes", "name": "Troglodyte Cavern", "rows": rows,
		"entities": [
			{"kind": "npc", "id": "dd_trog_elder", "name": "Ritual elder", "sprite": "elder", "pos": [10, 5], "facing": "down",
				"lines": ["The rite, stranger. Dance it, run it, or bleed it. The tribe does not mind which."],
				"lines_run_flag": {"trog_rite": ["Danced. Witnessed. Go with wet feet, stranger."]},
				"choice_event": "trog_ritual"},
			{"kind": "sign", "id": "dd_bridge", "pos": [6, 9], "text": "A bridge of black stone over black water. Drums on the far side."},
			{"kind": "sign", "id": "dd_river", "pos": [13, 9], "text": "The river pulls hard. A hollow reed-tube bobs against the bank — somebody escaped this way once."},
			{"kind": "pickup", "id": "dd_tube", "pos": [16, 4], "sprite": "staff", "run_pickup": true,
				"grant": {},
				"text": "A hollow tube, wax-sealed at both ends. For breathing underwater, if it comes to that."},
			{"kind": "exit", "pos": [11, 4], "to_area": "dd_grotto", "to_pos": [9, 5], "facing": "down", "requires_run_flag": "picked_dd_tube", "shortcut": true,
				"travel_text": "You bite the reed, fill your chest, and go under. The current does the rest. You come up in colder, quieter water."},
			{"kind": "exit", "pos": [19, 7], "to_area": "dd_grub", "to_pos": [1, 7], "facing": "right"},
			{"kind": "exit", "pos": [19, 8], "to_area": "dd_grub", "to_pos": [1, 8], "facing": "right"},
			{"kind": "exit", "pos": [0, 7], "to_area": "dd_manticore", "to_pos": [19, 7], "facing": "left"},
			{"kind": "exit", "pos": [0, 8], "to_area": "dd_manticore", "to_pos": [19, 8], "facing": "left"},
		],
	}


# -------------------------------------------------------------------------------
# ZONE J — Manticore gate + optional Red duel. 20 wide x 14 tall.
# -------------------------------------------------------------------------------
static func _dd_manticore() -> Dictionary:
	var rows := [
		"TTT:TTTTTTTTTTTTTTTT",
		"TTT..............TTT",
		"TT................TT",
		"TT......rrrr......TT",
		"TT......rrrr......TT",
		"TT................TT",
		"TT................TT",
		"....................",
		"....................",
		"TT................TT",
		"TT................TT",
		"TTT..............TTT",
		"TTT..............TTT",
		"TTTTTTTTTTTTTTTTTTTT",
	]
	return {
		"id": "dd_manticore", "name": "Manticore Gate", "rows": rows,
		"entities": [
			{"kind": "exit", "pos": [3, 0], "to_area": "dd_trialmaster", "to_pos": [4, 12], "facing": "up", "requires_run_flag": "trial_done", "shortcut": true},
			{"kind": "sign", "id": "dd_staff_passage", "pos": [4, 1], "text": "A narrow staff passage climbs north — swept, lamplit, and clearly not meant for contestants.",
				"text_run_flag": {"trial_done": "The Dwarf's staff passage. It runs back to the Trialmaster's complex, for anyone he has decided to like."}},
			{"kind": "creature", "id": "manticore_gate1", "enemy_id": "manticore", "pos": [10, 6],
				"intro": "The last gate has teeth, wings, and patience.\n\nFour slots. It has been waiting longer than you."},
			{"kind": "wizard", "id": "red_settle", "enemy_id": "red_wizard", "pos": [14, 8], "sprite": "red_mage", "facing": "left",
				"intro": "The Red Wizard is already here, picking his teeth.\n\n\"The woodcutter. Still counting? Four knots, then — settle it, or walk past.\""},
			{"kind": "exit", "pos": [19, 7], "to_area": "dd_troglodytes", "to_pos": [1, 7], "facing": "right"},
			{"kind": "exit", "pos": [19, 8], "to_area": "dd_troglodytes", "to_pos": [1, 8], "facing": "right"},
			{"kind": "exit", "pos": [0, 7], "to_area": "dd_igbut", "to_pos": [9, 10], "facing": "left"},
			{"kind": "exit", "pos": [0, 8], "to_area": "dd_igbut", "to_pos": [9, 10], "facing": "left"},
		],
	}


# -------------------------------------------------------------------------------
# ZONE K — Igbut, gem lock, daylight (p.364, 62, 241, 400). 16 wide x 12 tall.
# -------------------------------------------------------------------------------
static func _dd_igbut() -> Dictionary:
	var rows := [
		"TTTTTTTTTTTTTTTT",
		"TTTT........TTTT",
		"TTT..........TTT",
		"TT............TT",
		"TT............TT",
		"TT............TT",
		"TT............TT",
		"TT............TT",
		"TTT..........TTT",
		"TTTT........TTTT",
		"TTTTTT....TTTTTT",
		"TTTTTTTTTTTTTTTT",
	]
	return {
		"id": "dd_igbut", "name": "Igbut's Door", "rows": rows,
		"entities": [
			{"kind": "npc", "id": "dd_igbut", "name": "Igbut", "sprite": "igbut", "pos": [8, 6], "facing": "down",
				"lines": ["Three gems, contestant. Emerald. Sapphire. Diamond. The door does the rest."],
				"choice_event": "igbut_door"},
			{"kind": "door", "id": "victory_door", "pos": [8, 2], "text": "A door of black stone with three empty sockets, gem-sized, in a row."},
			# D5: after three wrong placements the door scatters the gems; they lie
			# where they fell until picked up again. Recoverable, local, not a death.
			{"kind": "pickup", "id": "scattered_emerald", "pos": [4, 4], "sprite": "diamond", "run_pickup": true,
				"requires_run_flag": "gems_scattered", "grant": {"gem": "emerald"},
				"text": "The Emerald, chipped now, under the plinth."},
			{"kind": "pickup", "id": "scattered_sapphire", "pos": [11, 5], "sprite": "diamond", "run_pickup": true,
				"requires_run_flag": "gems_scattered", "grant": {"gem": "sapphire"},
				"text": "The Sapphire, against the far wall."},
			{"kind": "pickup", "id": "scattered_diamond", "pos": [7, 8], "sprite": "diamond", "run_pickup": true,
				"requires_run_flag": "gems_scattered", "grant": {"gem": "diamond"},
				"text": "The Diamond, cold as ever, by your boot."},
			{"kind": "exit", "pos": [9, 10], "to_area": "dd_manticore", "to_pos": [1, 7], "facing": "right"},
		],
	}


# -------------------------------------------------------------------------------
# JANE — placeholder only (brief §24). One room, no exits. The wider-world chapter
# is explicitly deferred; this exists so the defeat architecture has somewhere to go.
# -------------------------------------------------------------------------------
static func _jane_placeholder() -> Dictionary:
	var rows := [
		"#########",
		"#.......#",
		"#.......#",
		"#.......#",
		"#.......#",
		"#.......#",
		"#.......#",
		"#########",
	]
	return {
		"id": "jane_placeholder", "name": "Somewhere else", "rows": rows, "theme": "interior",
		"entities": [
			{"kind": "logs", "id": "jane_kettle", "pos": [6, 2], "text": "A kettle. Somebody has been arguing with it."},
			{"kind": "exit", "id": "jane_door", "pos": [4, 6], "to_area": "wn_home", "to_pos": [3, 5], "facing": "down", "travel_text": "The door sticks, then gives. Daylight, and a smell of sheep."},
		],
	}
