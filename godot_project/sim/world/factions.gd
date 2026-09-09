class_name DmbFactions
extends RefCounted
## The six factions of the Fang hinterland. Pure data. Names in the
## Deathtrap Dungeon register: small, tired, provincial powers living in the
## shadow of Baron Sukumvit's dungeon.
##
## stance: "guardian" factions spend their champions treating demons;
## "corrupting" factions expand and let the infection burn.

const DATA := {
	"wardens": {
		"name": "The Fang Wardens",
		"stance": "guardian",
		"ruler": "Reeve Ottilie Marsk",
		"ruler_title": "Reeve of Fang",
		"champion": "Sister Halloran",
		"champion_form": "hedge_wizard",
		"colour": "green",
		"blurb": "Fang's town watch, grown into a small polity by default. They keep the roads clear because nobody else will.",
	},
	"levy": {
		"name": "The Sukumvit Levy",
		"stance": "guardian",
		"ruler": "Factor Dessimund Vole",
		"ruler_title": "Baron's Factor",
		"champion": "Captain Rook",
		"champion_form": "trog_champion",
		"colour": "purple",
		"blurb": "The Baron's tax-men and their hired blades. They protect what pays, which is most things.",
	},
	"kilns": {
		"name": "The Hollow Kilns",
		"stance": "corrupting",
		"ruler": "Mother Ash",
		"ruler_title": "Firstborn of the Kilns",
		"champion": "The Kilnwright",
		"champion_form": "cinder_golem",
		"colour": "red",
		"blurb": "Brick-burners of the hills. Their fires want feeding and demons burn hot.",
	},
	"drovers": {
		"name": "The Drover Compact",
		"stance": "guardian",
		"ruler": "Ewan Grey-Tally",
		"ruler_title": "Speaker of the Compact",
		"champion": "Old Pell",
		"champion_form": "steam_brute",
		"colour": "white",
		"blurb": "Shepherds and carters who agreed, once, to count each other's sheep honestly. It has held so far.",
	},
	"ironmoot": {
		"name": "The Ironmoot",
		"stance": "corrupting",
		"ruler": "Thane Berrick Ashgar",
		"ruler_title": "Thane of the Moot",
		"champion": "Gudda Ironmoot",
		"champion_form": "steam_brute",
		"colour": "grey",
		"blurb": "Miners of the high seams. They build fast and reckon a demon in the next valley is the next valley's problem.",
	},
	"tithe": {
		"name": "The Wheatlord's Tithe",
		"stance": "corrupting",
		"ruler": "Tithe-Reeve Corvin Sallow",
		"ruler_title": "Tithe-Reeve",
		"champion": "Harrow",
		"champion_form": "rival_wizard",
		"colour": "gold",
		"blurb": "Field-lords who collect a tenth of everything. Lately they collect from the demons too, or say they do.",
	},
}

const ORDER := ["wardens", "levy", "kilns", "drovers", "ironmoot", "tithe"]


static func ids() -> Array:
	return ORDER.duplicate()


static func get_data(fid: String) -> Dictionary:
	return DATA.get(fid, {})


static func name_of(fid: String) -> String:
	return DATA.get(fid, {}).get("name", fid)


static func stance_of(fid: String) -> String:
	return DATA.get(fid, {}).get("stance", "guardian")
