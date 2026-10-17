"""Colour palettes (desired base colours; the runtime tint is base / 0.9 so the lit pixels reach the intended colour)."""
from __future__ import annotations

SKIN = [(255, 226, 200), (244, 206, 168), (226, 176, 128), (190, 134, 92), (148, 98, 66), (104, 68, 50)]
SKIN_W = [3, 4, 4, 3, 2, 1]
HAIR = [(44, 34, 40), (78, 50, 36), (118, 78, 46), (150, 92, 50), (228, 192, 112), (190, 94, 50), (168, 168, 176), (230, 230, 236)]
HAIR_W = [3, 4, 4, 3, 2, 2, 1, 1]

TRIBES = {
    "barbarians": [[(186, 92, 60), (116, 84, 60), (214, 170, 70)], [(150, 60, 56), (96, 100, 72), (200, 150, 80)], [(170, 120, 70), (90, 80, 70), (190, 70, 50)],
                   [(120, 86, 60), (150, 70, 50), (226, 190, 90)]],
    "empire": [[(70, 100, 170), (220, 214, 200), (190, 60, 70)], [(110, 80, 150), (200, 196, 186), (220, 180, 70)], [(60, 120, 160), (232, 226, 214), (160, 50, 60)],
               [(150, 60, 70), (210, 206, 196), (80, 100, 160)]],
    "atlanteans": [[(60, 150, 160), (226, 206, 150), (90, 70, 130)], [(80, 170, 150), (210, 190, 140), (70, 100, 160)], [(50, 120, 150), (240, 224, 180), (160, 90, 80)],
                   [(100, 150, 190), (220, 200, 150), (60, 130, 120)]],
    "frisians": [[(96, 150, 80), (214, 186, 90), (110, 90, 70)], [(80, 130, 110), (226, 200, 110), (150, 100, 70)], [(130, 160, 70), (190, 170, 130), (80, 100, 130)],
                 [(70, 120, 150), (220, 200, 120), (120, 150, 80)]],
    "amazons": [[(70, 160, 110), (230, 150, 60), (200, 70, 70)], [(60, 140, 150), (240, 200, 70), (170, 80, 120)], [(120, 170, 60), (210, 110, 60), (80, 70, 140)],
                [(200, 100, 60), (80, 160, 120), (230, 200, 70)]],
}
TRIBE_NAMES = list(TRIBES)

# wizard robe sets: (robe, cloak / second cloth, accent / trim / orb)
WIZARD_SETS = [
    [(110, 70, 170), (70, 44, 120), (236, 186, 70)],
    [(60, 110, 190), (40, 70, 140), (240, 220, 120)],
    [(170, 50, 60), (110, 34, 50), (250, 190, 80)],
    [(50, 140, 90), (36, 96, 70), (230, 210, 110)],
    [(200, 120, 40), (130, 70, 36), (255, 230, 150)],
    [(60, 150, 160), (40, 100, 120), (230, 240, 250)],
    [(150, 70, 150), (100, 44, 110), (250, 210, 120)],
    [(90, 96, 120), (56, 60, 84), (190, 230, 255)],
]

# stable look of every named person (outfit + skin + hair + beard + palette); skin / hair are RGB or indexes into SKIN / HAIR
NAMED = {
    "john": dict(outfit="john", skin=1, hair_style="short", hair=2, beard="none"),
    "john_staff": dict(outfit="john_staff", skin=1, hair_style="short", hair=2, beard="none"),
    "halvard": dict(outfit="blue_mage", skin=1, hair_style="bald", hair=7, beard="none"),
    "blue_mage": dict(outfit="blue_mage", skin=1, hair_style="bald", hair=7, beard="none"),
    "red_mage": dict(outfit="red_mage", skin=1, hair_style="bald", hair=5, beard="none"),
    "hedge_mage": dict(outfit="hedge_mage", skin=1, hair_style="bald", hair=3, beard="none"),
    "reaper": dict(outfit="reaper", skin=0, hair_style="bald", hair=0, beard="none"),
    "assassin": dict(outfit="assassin", skin=2, hair_style="swept", hair=0, beard="none"),
    "knight": dict(outfit="knight", skin=1, hair_style="short", hair=6, beard="none"),
    "dwarf": dict(outfit="dwarf", skin=2, hair_style="short", hair=3, beard="braided"),
    "elf": dict(outfit="elf", skin=0, hair_style="long", hair=4, beard="none"),
    "elder": dict(outfit="elder_green", skin=1, hair_style="balding", hair=7, beard="long"),
    "igbut": dict(outfit="igbut", skin=2, hair_style="bob", hair=1, beard="none"),
    "ivy": dict(outfit="ivy", skin=0, hair_style="long", hair=(150, 70, 170), beard="none"),
    "official": dict(outfit="official", skin=1, hair_style="short", hair=6, beard="mustache"),
    "matron": dict(outfit="matron", skin=2, hair_style="bun", hair=6, beard="none"),
    "throm": dict(outfit="throm", skin=3, hair_style="bald", hair=1, beard="goatee"),
    "child": dict(outfit="child", skin=1, hair_style="short", hair=2, beard="none", pal=dict(a=(206, 150, 100), b=(80, 74, 100), c=(220, 170, 80))),
    "farmer": dict(outfit="farmer", skin=2, hair_style="short", hair=3, beard="stubble"),
    "miner": dict(outfit="miner", skin=2, hair_style="short", hair=1, beard="short"),
    "woodcutter": dict(outfit="woodcutter", skin=2, hair_style="short", hair=1, beard="short"),
    "shepherd": dict(outfit="herder", skin=1, hair_style="short", hair=6, beard="long"),
    "worker": dict(outfit="builder", skin=2, hair_style="short", hair=1, beard="none"),
    "villager_a": dict(outfit="carrier", skin=1, hair_style="short", hair=2, beard="none", pal=dict(a=(80, 110, 170), b=(70, 66, 80), c=(150, 100, 60))),
    "villager_b": dict(outfit="carrier", skin=2, hair_style="balding", hair=7, beard="mustache", pal=dict(a=(150, 110, 80), b=(80, 76, 84), c=(120, 90, 60))),
    # wizards of the Ward duel (their portraits exist in assets/generated/composite/wizards)
    "archmage": dict(outfit="wizard", skin=1, hair_style="long", hair=7, beard="long", pal=dict(a=(110, 70, 170), b=(70, 44, 120), c=(236, 186, 70))),
    "blue_apprentice": dict(outfit="wizard", skin=0, hair_style="short", hair=4, beard="none", pal=dict(a=(60, 110, 190), b=(40, 70, 140), c=(240, 220, 120))),
    "mirror_mage": dict(outfit="wizard_hooded", skin=1, hair_style="bald", hair=6, beard="none", pal=dict(a=(190, 200, 214), b=(120, 130, 150), c=(150, 230, 255))),
    "thorn_adept": dict(outfit="wizard_druid", skin=2, hair_style="braid", hair=3, beard="none", pal=dict(a=(86, 140, 70), b=(96, 76, 54), c=(210, 160, 70))),
    "eightfold_warden": dict(outfit="wizard_battle", skin=3, hair_style="short", hair=0, beard="goatee", pal=dict(a=(150, 70, 60), b=(90, 70, 80), c=(240, 190, 80))),
    "player": dict(outfit="wizard", skin=1, hair_style="short", hair=2, beard="none", pal=dict(a=(60, 110, 190), b=(40, 70, 140), c=(240, 220, 120))),
}

# every widelands job name (tribe prefix stripped, "_worker" stripped) -> outfit
JOBS = {
    "carrier": "carrier", "builder": "builder", "farmer": "farmer", "blackroot_farmer": "farmer", "cassava_farmer": "farmer", "cocoa_farmer": "farmer", "reed_farmer": "farmer",
    "berry_farmer": "gardener", "vinefarmer": "gardener", "fruit_collector": "gardener", "gardener": "gardener", "vintner": "brewer",
    "baker": "baker", "baker_master": "baker", "lumberjack": "woodcutter", "woodcutter": "woodcutter", "woodcutter_master": "woodcutter",
    "forester": "forester", "ranger": "forester", "gamekeeper": "forester", "jungle_preserver": "forester", "jungle_master": "forester", "wilderness_keeper": "forester",
    "liana_cutter": "forester", "miner": "miner", "miner_master": "miner", "miner_chief": "miner", "gold_digger": "miner", "smelter": "smith", "gold_smelter": "smith",
    "blacksmith": "smith", "blacksmith_master": "smith", "armorsmith": "smith", "weaponsmith": "smith", "toolsmith": "smith", "helmsmith": "smith", "lime_burner": "smith",
    "stonemason": "mason", "stonecutter": "mason", "stone_carver": "mason", "brickmaker": "mason", "claydigger": "digger", "diker": "digger",
    "fisher": "fisher", "fishbreeder": "fisher", "hunter_gatherer": "hunter", "hunter": "hunter", "innkeeper": "cook", "cook": "cook", "landlady": "cook", "smoker": "cook",
    "brewer": "brewer", "brewer_master": "brewer", "miller": "miller", "carpenter": "carpenter", "sawyer": "carpenter",
    "weaver": "weaver", "dressmaker": "weaver", "seamstress": "weaver", "seamstress_master": "weaver", "charcoal_burner": "charcoal",
    "cattlebreeder": "herder", "horsebreeder": "herder", "pigbreeder": "herder", "shepherd": "herder", "spiderbreeder": "herder", "tapir_breeder": "herder",
    "reindeer_breeder": "herder", "donkeybreeder": "herder", "beekeeper": "herder", "scout": "scout", "geologist": "geologist", "trainer": "trainer", "recruit": "recruit",
    "shipwright": "shipwright", "ferry": "shipwright", "stonemason_worker": "mason",
}
ANIMAL_JOBS = ["ox", "donkey", "horse", "tapir", "reindeer", "bunny", "deer", "tapir"]
SOLDIER_BY_TRIBE = {"barbarians": "soldier_barbarian", "empire": "soldier_empire", "atlanteans": "soldier_atlantean", "frisians": "soldier_frisian", "amazons": "soldier_amazon"}
OPENRA = {"e1": "e1", "e2": "e2", "e3": "e3", "e4": "e4", "e6": "e6", "e7": "e7", "spy": "spy", "thf": "thief", "medi": "medic", "mech": "mechanic", "shok": "shock", "zombie": "zombie"}
DMB = {"clubman": "clubman", "spearman": "spearman", "slinger": "slinger", "caravan": "merchant", "settlers": "settler"}
