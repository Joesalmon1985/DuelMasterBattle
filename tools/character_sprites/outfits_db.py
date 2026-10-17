"""The outfit catalogue.  Every entry is one sheet: garments, hat, tool, default palette and the hair it may be combined with.

pal values are either an (r, g, b) base colour or 'T0' / 'T1' / 'T2': take that colour from the character's tribe palette, so
the same job looks different in every tribe and for every individual while staying recognisably the same job.
"""
from __future__ import annotations

HAIR_ALL = ["short", "swept", "long", "ponytail", "bun", "spiky", "curly", "bob", "braid", "balding"]
HAIR_HAT = ["short", "swept", "bob", "ponytail", "braid", "balding", "long"]
HAIR_NONE = ["bald"]
BEARD_COMMON = ["none"] * 8 + ["stubble", "short", "mustache", "goatee"]
BEARD_BIG = ["short", "long", "mustache", "braided", "goatee", "long"]

WHITE = (240, 238, 232)
CREAM = (232, 218, 182)
LEATHER = (130, 88, 56)
DARK = (58, 50, 66)
OLIVE = (96, 110, 70)
STEEL = (150, 158, 172)


def O(**kw):
    kw.setdefault("body", "adult")
    kw.setdefault("clips", "civil")
    kw.setdefault("hairs", HAIR_ALL)
    kw.setdefault("beards", ["none"])
    kw.setdefault("pal", {})
    return kw


def staff_prop(head="orb", **kw):
    kw.setdefault("orb_layer", "detail" if ("magic" in kw or "flame" in kw) else "c")
    kw.setdefault("follow", 0.5)  # a staff tilts with the arm but stays mostly upright
    return dict(kind="staff", abs=dict(side=3, down=10, up=10), head=head, **kw)


OUTFITS: dict[str, dict] = {
    # ------------------------------------------------------------------ labour
    "carrier": O(spec=dict(hem=3.0, flare=0.6, sleeve="short", hat="headband", back="sack", hem_trim=False, cuff=False),
                 pal=dict(a="T0", b=(120, 100, 84), c=(176, 120, 70)), beards=BEARD_COMMON),
    "farmer": O(spec=dict(hem=3.0, flare=0.6, sleeve="short", hat="straw", hem_trim=False,
                          prop=dict(kind="pitchfork", abs=dict(side=8, down=6, up=6))), hairs=HAIR_HAT,
                pal=dict(a=CREAM, b="T1", c=(206, 168, 80)), beards=BEARD_COMMON),
    "baker": O(spec=dict(hem=3.0, flare=0.6, sleeve="short", hat="toque", apron=True, apron_layer="c", apron_len=9.5, hat_layer="c",
                         prop=dict(kind="loaf", abs=dict(side=0, down=0, up=0), follow=0.5)), hairs=HAIR_HAT,
               pal=dict(a="T0", b=(112, 96, 84), c=WHITE), beards=BEARD_COMMON),
    "woodcutter": O(spec=dict(hem=4.0, flare=0.5, sleeve="long", hat="beanie", hat_layer="c", cuff=False, belt=True,
                              prop=dict(kind="axe", abs=dict(side=12, down=8, up=8))), hairs=HAIR_HAT,
                    pal=dict(a=(190, 70, 56), b=(86, 74, 66), c=(86, 90, 62)), beards=BEARD_BIG),
    "forester": O(spec=dict(hem=5.0, flare=1.0, sleeve="long", hat="hood", hat_layer="a", belt=True, back="satchel", hem_trim=True,
                            prop=dict(kind="spade", abs=dict(side=10, down=7, up=7))), hairs=HAIR_HAT,
                  pal=dict(a=(84, 130, 74), b=(96, 82, 64), c=(150, 110, 60)), beards=BEARD_COMMON),
    "miner": O(spec=dict(hem=4.0, flare=0.4, sleeve="long", hat="hardhat", hat_layer="c", belt=True, collar=False,
                         prop=dict(kind="pickaxe", abs=dict(side=14, down=10, up=10))), hairs=HAIR_HAT,
               pal=dict(a=(96, 92, 106), b=(62, 58, 70), c=(212, 156, 60)), beards=BEARD_BIG),
    "smith": O(spec=dict(hem=3.0, flare=0.5, sleeve="none", hat="headband", hat_layer="c", apron=True, apron_layer="c", apron_len=10.0,
                         prop=dict(kind="hammer", abs=dict(side=14, down=10, up=10))), hairs=HAIR_ALL,
               pal=dict(a=(150, 110, 90), b=(80, 74, 84), c=LEATHER), beards=BEARD_BIG),
    "builder": O(spec=dict(hem=3.0, flare=0.5, sleeve="short", hat="cap", hat_layer="c", belt=True, belt_layer="c",
                           prop=dict(kind="mallet", abs=dict(side=12, down=9, up=9))), hairs=HAIR_HAT,
                 pal=dict(a="T0", b=(100, 94, 110), c=(196, 150, 70)), beards=BEARD_COMMON),
    "mason": O(spec=dict(hem=3.0, flare=0.5, sleeve="short", hat="bandana", hat_layer="c", apron=True, apron_layer="c", apron_len=9.0,
                         prop=dict(kind="chisel", abs=dict(side=20, down=14, up=14))), hairs=HAIR_HAT,
               pal=dict(a=(170, 168, 160), b=(96, 90, 100), c="T2"), beards=BEARD_BIG),
    "fisher": O(spec=dict(hem=4.0, flare=0.6, sleeve="long", hat="sailor", belt=True,
                          prop=dict(kind="rod", abs=dict(side=24, down=18, up=18))), hairs=HAIR_HAT,
                pal=dict(a=(80, 128, 150), b=(92, 100, 118), c=(238, 236, 230)), beards=BEARD_BIG),
    "hunter": O(spec=dict(hem=4.0, flare=0.6, sleeve="long", hat="cap", hat_layer="a", back="quiver", belt=True, collar=True,
                          prop=dict(kind="bow", abs=dict(side=0, down=0, up=0), follow=0.5)), hairs=HAIR_HAT,
                pal=dict(a=(96, 120, 66), b=(110, 86, 64), c=(150, 100, 56)), beards=BEARD_COMMON),
    "cook": O(spec=dict(hem=3.0, flare=0.7, sleeve="short", hat="toque", apron=True, apron_len=10.0, hat_layer="c",
                        prop=dict(kind="ladle", abs=dict(side=16, down=10, up=10))), hairs=HAIR_HAT,
              pal=dict(a="T0", b=(100, 86, 78), c=WHITE), beards=BEARD_COMMON),
    "brewer": O(spec=dict(hem=3.0, flare=0.7, sleeve="short", hat="cap", hat_layer="c", apron=True, apron_len=9.0,
                          prop=dict(kind="mug", abs=dict(side=0, down=0, up=0), follow=0.3)), hairs=HAIR_HAT,
                pal=dict(a="T1", b=(100, 80, 70), c=(150, 100, 60)), beards=BEARD_BIG),
    "miller": O(spec=dict(hem=3.0, flare=0.6, sleeve="short", hat="cap", hat_layer="c", back="sack", belt=True), hairs=HAIR_HAT,
                pal=dict(a=(232, 226, 214), b=(150, 140, 130), c=(238, 236, 228)), beards=BEARD_COMMON),
    "carpenter": O(spec=dict(hem=3.0, flare=0.5, sleeve="short", hat="cap", hat_layer="a", apron=True, apron_layer="c", apron_len=8.0,
                             prop=dict(kind="saw", abs=dict(side=-8, down=-6, up=-6))), hairs=HAIR_HAT,
                   pal=dict(a=(188, 150, 96), b=(100, 90, 90), c=LEATHER), beards=BEARD_COMMON),
    "weaver": O(spec=dict(hem=7.0, flare=1.2, sleeve="long", hat="headband", hat_layer="c", belt=True, hem_trim=True,
                          prop=dict(kind="scroll", abs=dict(side=0, down=0, up=0), follow=0.2)), hairs=HAIR_ALL,
                pal=dict(a="T0", b=(120, 90, 100), c="T2"), beards=["none"]),
    "digger": O(spec=dict(hem=3.0, flare=0.5, sleeve="short", hat="cap", hat_layer="c", belt=True,
                          prop=dict(kind="spade", abs=dict(side=10, down=7, up=7))), hairs=HAIR_HAT,
                pal=dict(a=(158, 120, 86), b=(90, 80, 74), c=(120, 96, 66)), beards=BEARD_COMMON),
    "herder": O(spec=dict(hem=5.0, flare=1.0, sleeve="long", hat="straw", hat_layer="c", belt=True,
                          prop=dict(kind="staff", head="crook", abs=dict(side=4, down=4, up=4), wood=(150, 110, 70))), hairs=HAIR_HAT,
                pal=dict(a=(210, 200, 176), b="T1", c=(190, 150, 70)), beards=BEARD_COMMON),
    "gardener": O(spec=dict(hem=4.0, flare=0.6, sleeve="short", hat="straw", hat_layer="c", apron=True, apron_layer="c", apron_len=8.0,
                            prop=dict(kind="basket", abs=dict(side=0, down=0, up=0), follow=0.3)), hairs=HAIR_HAT,
                  pal=dict(a=(220, 214, 180), b="T1", c=(94, 140, 80)), beards=BEARD_COMMON),
    "scout": O(spec=dict(hem=5.0, flare=1.0, sleeve="long", hat="hood", hat_layer="a", belt=True, back="backpack", hem_trim=True,
                         prop=dict(kind="staff", head="plain", abs=dict(side=4, down=4, up=4))), hairs=HAIR_HAT,
               pal=dict(a=(110, 120, 100), b=(86, 74, 66), c=(150, 110, 60)), beards=BEARD_COMMON),
    "geologist": O(spec=dict(hem=4.0, flare=0.6, sleeve="short", hat="hardhat", hat_layer="a", belt=True, back="backpack",
                             prop=dict(kind="hammer", abs=dict(side=14, down=10, up=10))), hairs=HAIR_HAT,
                   pal=dict(a="T0", b=(92, 86, 98), c=(200, 160, 70)), beards=BEARD_COMMON),
    "charcoal": O(spec=dict(hem=4.0, flare=0.6, sleeve="long", hat="hood", hat_layer="a", belt=True,
                            prop=dict(kind="spade", abs=dict(side=10, down=7, up=7))), hairs=HAIR_HAT,
                  pal=dict(a=(70, 62, 62), b=(56, 50, 54), c=(120, 90, 66)), beards=BEARD_COMMON),
    "shipwright": O(spec=dict(hem=3.0, flare=0.5, sleeve="short", hat="sailor", belt=True,
                              prop=dict(kind="mallet", abs=dict(side=12, down=9, up=9))), hairs=HAIR_HAT,
                    pal=dict(a=(238, 236, 228), b=(70, 90, 130), c=(180, 60, 56)), beards=BEARD_BIG),
    "trainer": O(spec=dict(hem=4.0, flare=0.8, sleeve="long", hat="helmet_round", belt=True, collar=True, cuff=True, hem_trim=True,
                           prop=dict(kind="sword", abs=dict(side=160, down=170, up=170), follow=0.4)), hairs=HAIR_HAT,
                 pal=dict(a="T0", b=(70, 70, 80), c=GOLD if False else (220, 180, 70)), beards=BEARD_BIG),
    "recruit": O(spec=dict(hem=3.0, flare=0.5, sleeve="short", hat="beanie", hat_layer="c", belt=True,
                           prop=dict(kind="club", abs=dict(side=14, down=10, up=10))), hairs=HAIR_HAT,
                 pal=dict(a="T0", b=(110, 100, 96), c=(150, 120, 80)), beards=BEARD_COMMON),
    "merchant": O(spec=dict(hem=6.0, flare=1.0, sleeve="long", hat="spyhat", belt=True, collar=True, back="backpack", cuff=True, hem_trim=True,
                            prop=dict(kind="book", abs=dict(side=0, down=0, up=0), follow=0.2)), hairs=HAIR_HAT,
                 pal=dict(a="T0", b=(60, 56, 78), c=(226, 180, 70)), beards=BEARD_COMMON),
    "settler": O(spec=dict(hem=3.0, flare=0.6, sleeve="short", hat="headband", back="bedroll", hem_trim=False,
                           prop=dict(kind="lantern", abs=dict(side=0, down=0, up=0), follow=0.1)), hairs=HAIR_HAT,
                 pal=dict(a="T0", b=(100, 96, 110), c=(170, 120, 70)), beards=BEARD_COMMON),
    "child": O(body="child", spec=dict(hem=3.0, flare=0.6, sleeve="short", belt=False), hairs=["short", "swept", "ponytail", "bun", "spiky", "curly", "bob", "braid"],
               pal=dict(a="T0", b="T1", c=(220, 170, 80)), beards=["none"]),
    "elder": O(spec=dict(hem=9.0, flare=1.6, sleeve="bell", hat="circlet", belt=True, hem_trim=True, cuff=True, collar=True,
                         prop=dict(kind="staff", head="crook", abs=dict(side=4, down=4, up=4), wood=(120, 86, 56))), hairs=["balding", "short", "long"],
               pal=dict(a=(150, 120, 190), b=(90, 70, 130), c=(226, 190, 90)), beards=["long", "braided", "long", "short"]),
    "healer": O(spec=dict(hem=9.0, flare=1.4, sleeve="bell", hat="hood", hat_layer="a", belt=True, hem_trim=True, cuff=True,
                          prop=dict(kind="wand", abs=dict(side=0, down=0, up=0), follow=0.3), magic=(120, 255, 170)), hairs=HAIR_HAT,
                pal=dict(a=(226, 232, 226), b=(90, 160, 120), c=(90, 190, 130)), beards=["none"]),
    # ------------------------------------------------------------------ soldiers
    "soldier_barbarian": O(spec=dict(hem=4.0, flare=0.6, sleeve="none", hat="helmet_horned", belt=True, collar=True, legs="trousers",
                                     prop=[dict(kind="axe", abs=dict(side=16, down=10, up=10)), dict(kind="shield", hand="off", abs=0, follow=0.0)]), hairs=HAIR_HAT,
                           pal=dict(a=(140, 90, 62), b=(86, 66, 58), c=(190, 70, 50)), beards=BEARD_BIG, clips="civil"),
    "soldier_empire": O(spec=dict(hem=5.0, flare=1.1, sleeve="short", hat="helmet_crest", belt=True, hem_trim=True, crest_layer="a",
                                  prop=[dict(kind="sword", abs=dict(side=150, down=160, up=160), follow=0.5), dict(kind="shield", hand="off", shape="kite", abs=0, follow=0.0)]),
                        hairs=HAIR_HAT, pal=dict(a=(190, 50, 56), b=(120, 90, 80), c=(226, 190, 80)), beards=BEARD_COMMON),
    "soldier_atlantean": O(spec=dict(hem=7.0, flare=1.0, sleeve="short", hat="helmet_round", belt=True, hem_trim=True,
                                     prop=dict(kind="spear", abs=dict(side=4, down=4, up=4))), hairs=HAIR_HAT,
                           pal=dict(a=(60, 150, 160), b=(76, 100, 124), c=(226, 190, 90)), beards=BEARD_COMMON),
    "soldier_frisian": O(spec=dict(hem=4.0, flare=0.7, sleeve="long", hat="kettle", belt=True, collar=True,
                                   prop=[dict(kind="spear", abs=dict(side=4, down=4, up=4)), dict(kind="shield", hand="off", abs=0, follow=0.0)]), hairs=HAIR_HAT,
                         pal=dict(a=(70, 110, 170), b=(98, 90, 86), c=(230, 200, 90)), beards=BEARD_BIG),
    "soldier_amazon": O(spec=dict(hem=3.0, flare=0.5, sleeve="none", hat="headdress", belt=True, legs="shorts", boots="bare",
                                  prop=dict(kind="spear", abs=dict(side=6, down=5, up=5))), hairs=["ponytail", "braid", "long", "bun", "short"],
                        pal=dict(a=(50, 150, 96), b=(200, 120, 56), c=(226, 190, 80)), beards=["none"]),
    "clubman": O(spec=dict(hem=3.0, flare=0.5, sleeve="none", hat="bandana", hat_layer="c", belt=True,
                           prop=dict(kind="club", abs=dict(side=14, down=10, up=10))), hairs=HAIR_ALL,
                 pal=dict(a=(150, 110, 74), b=(100, 80, 66), c=(180, 80, 56)), beards=BEARD_BIG),
    "spearman": O(spec=dict(hem=4.0, flare=0.6, sleeve="short", hat="helmet_round", belt=True,
                            prop=[dict(kind="spear", abs=dict(side=4, down=4, up=4)), dict(kind="shield", hand="off", abs=0, follow=0.0)]), hairs=HAIR_HAT,
                  pal=dict(a="T0", b=(100, 90, 90), c=(150, 120, 70)), beards=BEARD_COMMON),
    "slinger": O(spec=dict(hem=3.0, flare=0.5, sleeve="short", hat="bandana", hat_layer="c", belt=True, back="satchel",
                           prop=dict(kind="sling", abs=dict(side=-20, down=-20, up=-20), follow=0.7)), hairs=HAIR_ALL,
                 pal=dict(a="T0", b=(110, 96, 80), c=(86, 110, 70)), beards=BEARD_COMMON),
    # ------------------------------------------------------------------ the engineers' army (infantry)
    "e1": O(spec=dict(hem=4.0, flare=0.5, sleeve="long", hat="helmet_round", belt=True, collar=True, prop=dict(kind="rifle", abs=dict(side=-70, down=-60, up=-60), follow=0.5)),
            hairs=HAIR_HAT, pal=dict(a=OLIVE, b=(78, 90, 60), c=(70, 62, 52)), beards=BEARD_COMMON),
    "e2": O(spec=dict(hem=4.0, flare=0.5, sleeve="long", hat="helmet_round", belt=True, back="satchel", collar=True, prop=dict(kind="lantern", abs=dict(side=0, down=0, up=0), follow=0.2)),
            hairs=HAIR_HAT, pal=dict(a=(120, 100, 70), b=(80, 74, 56), c=(200, 80, 40)), beards=BEARD_COMMON),
    "e3": O(spec=dict(hem=4.0, flare=0.5, sleeve="long", hat="helmet_round", belt=True, collar=True, prop=dict(kind="launcher", abs=dict(side=-40, down=-30, up=-30), follow=0.5)),
            hairs=HAIR_HAT, pal=dict(a=(80, 104, 120), b=(70, 80, 90), c=(70, 62, 52)), beards=BEARD_COMMON),
    "e4": O(spec=dict(hem=5.0, flare=0.6, sleeve="long", hat="hood", hat_layer="b", belt=True, back="backpack", collar=True, prop=dict(kind="flamer", abs=dict(side=-60, down=-50, up=-50), follow=0.5)),
            hairs=HAIR_HAT, pal=dict(a=(190, 90, 50), b=(86, 54, 46), c=(60, 50, 50)), beards=["none"]),
    "e6": O(spec=dict(hem=3.0, flare=0.5, sleeve="short", hat="hardhat", hat_layer="c", belt=True, belt_layer="c", prop=dict(kind="wrench", abs=dict(side=16, down=10, up=10))),
            hairs=HAIR_HAT, pal=dict(a=(232, 190, 56), b=(70, 90, 130), c=(240, 210, 70)), beards=BEARD_COMMON),
    "e7": O(spec=dict(hem=3.0, flare=0.4, sleeve="none", hat="bandana", hat_layer="c", belt=True, legs="trousers", collar=True, prop=dict(kind="pistols", abs=dict(side=-70, down=-60, up=-60), follow=0.5)),
            hairs=["ponytail"], pal=dict(a=(210, 200, 180), b=(70, 90, 120), c=(190, 50, 50)), beards=["none"]),
    "spy": O(spec=dict(hem=7.0, flare=0.9, sleeve="long", hat="spyhat", belt=True, collar=True, hem_trim=False, cuff=True),
             hairs=HAIR_HAT, pal=dict(a=(96, 88, 98), b=(60, 56, 66), c=(220, 220, 224)), beards=BEARD_COMMON),
    "thief": O(spec=dict(hem=5.0, flare=0.8, sleeve="long", hat="hood", hat_layer="a", belt=True, prop=dict(kind="cleaver", abs=dict(side=170, down=170, up=170), follow=0.3)),
               hairs=HAIR_HAT, pal=dict(a=(60, 60, 72), b=(46, 44, 54), c=(140, 60, 60)), beards=["none"]),
    "medic": O(spec=dict(hem=7.0, flare=0.9, sleeve="long", hat="cap", hat_layer="c", belt=True, collar=True, prop=dict(kind="medbag", abs=dict(side=0, down=0, up=0), follow=0.1)),
               hairs=HAIR_HAT, pal=dict(a=WHITE, b=(120, 150, 170), c=(230, 236, 236)), beards=BEARD_COMMON),
    "mechanic": O(spec=dict(hem=4.0, flare=0.4, sleeve="long", hat="cap", hat_layer="c", belt=True, prop=dict(kind="wrench", abs=dict(side=16, down=10, up=10))),
                  hairs=HAIR_HAT, pal=dict(a=(70, 100, 150), b=(60, 84, 128), c=(180, 70, 56)), beards=BEARD_COMMON),
    "shock": O(spec=dict(hem=5.0, flare=0.6, sleeve="long", hat="helmet_round", belt=True, collar=True, cuff=True, back="backpack", prop=dict(kind="tesla", abs=dict(side=-40, down=-30, up=-30), follow=0.5)),
               hairs=HAIR_HAT, pal=dict(a=(80, 90, 150), b=(60, 64, 110), c=(110, 220, 255)), beards=["none"]),
    "zombie": O(spec=dict(hem=4.0, flare=0.9, sleeve="long", belt=True, hem_trim=False, pose_mod="zombie"),
                hairs=["balding", "short", "curly"], pal=dict(a=(96, 98, 80), b=(70, 70, 70), c=(80, 70, 60)), beards=["stubble", "none"]),
    # ------------------------------------------------------------------ wizards (the full clip set)
    "wizard": O(clips="full", spec=dict(hem=9.0, flare=1.6, sleeve="bell", hat="wizard", belt=True, hem_trim=True, cuff=True, cloak=True, collar=True, hat_tip=6.5,
                                         prop=staff_prop("orb")), hairs=HAIR_HAT, pal=dict(a="W0", b="W1", c="W2"), beards=["none", "short", "long", "mustache"]),
    "wizard_hooded": O(clips="full", spec=dict(hem=9.0, flare=1.3, sleeve="long", hat="hood", hat_layer="a", belt=True, hem_trim=True, cuff=True, cloak=True,
                                                prop=staff_prop("crystal")), hairs=HAIR_HAT, pal=dict(a="W0", b="W1", c="W2"), beards=["none", "stubble"]),
    "wizard_battle": O(clips="full", spec=dict(hem=6.0, flare=1.0, sleeve="long", hat="helmet_round", belt=True, hem_trim=True, cuff=True, cloak=True, collar=True,
                                                prop=staff_prop("orb")), hairs=HAIR_HAT, pal=dict(a="W0", b="W1", c="W2"), beards=["none", "short", "goatee"]),
    "wizard_witch": O(clips="full", spec=dict(hem=9.0, flare=1.8, sleeve="bell", hat="wizard", hat_tip=5.5, hat_bend=-3.0, belt=True, hem_trim=True, cuff=True, collar=True,
                                               prop=staff_prop("leaf")), hairs=["long", "ponytail", "braid", "bob"], pal=dict(a="W0", b="W1", c="W2"), beards=["none"]),
    "wizard_druid": O(clips="full", spec=dict(hem=7.0, flare=1.2, sleeve="short", hat="laurel", belt=True, hem_trim=True, cloak=True, boots="bare",
                                               prop=staff_prop("leaf")), hairs=["long", "braid", "curly", "short"], pal=dict(a="W0", b="W1", c="W2"), beards=["none", "long", "braided"]),
    "wizard_fire": O(clips="full", spec=dict(hem=9.0, flare=1.4, sleeve="bell", hat="hood", hat_layer="a", belt=True, hem_trim=True, cuff=True, cloak=True,
                                              prop=staff_prop("flame")), hairs=HAIR_HAT, pal=dict(a="W0", b="W1", c="W2"), beards=["none", "stubble"]),
}


# ---------------------------------------------------------------------- named characters from the story (their own sheets)
def _named(**kw):
    kw.setdefault("clips", "full")
    return O(**kw)


OUTFITS.update({
    "john": _named(spec=dict(hem=4.0, flare=0.6, sleeve="short", belt=True, back="satchel", hem_trim=False, collar=True, collar_layer="c"),
                   hairs=["short"], pal=dict(a=(190, 66, 60), b=(70, 66, 90), c=(120, 84, 56))),
    "john_staff": _named(spec=dict(hem=4.0, flare=0.6, sleeve="short", belt=True, back="satchel", hem_trim=False, collar=True, collar_layer="c",
                                    prop=staff_prop("orb", magic=(90, 150, 255))),
                         hairs=["short"], pal=dict(a=(190, 66, 60), b=(70, 66, 90), c=(120, 84, 56))),
    "blue_mage": _named(spec=dict(hem=10.0, flare=1.8, sleeve="bell", hat="hood", hat_layer="a", belt=False, hem_trim=True, cuff=True, cloak=True, face_hidden=True,
                                   glow_eyes=(170, 240, 255), back="wings", magic=(150, 230, 255), prop=staff_prop("crystal", magic=(150, 230, 255))),
                        hairs=["bald"], pal=dict(a=(70, 150, 220), b=(40, 100, 180), c=(190, 240, 255))),
    "red_mage": _named(spec=dict(hem=10.0, flare=1.8, sleeve="bell", hat="hood", hat_layer="a", belt=False, hem_trim=True, cuff=True, cloak=True, face_hidden=True,
                                  glow_eyes=(255, 220, 90), back="wings", magic=(255, 150, 60),
                                  prop=staff_prop("flame", flame=((255, 120, 40), (255, 226, 110)))),
                       hairs=["bald"], pal=dict(a=(190, 76, 44), b=(110, 40, 34), c=(255, 170, 60))),
    "hedge_mage": _named(spec=dict(hem=9.0, flare=1.6, sleeve="bell", hat="hood", hat_layer="a", belt=True, hem_trim=True, cuff=True, cloak=True, face_hidden=True,
                                    glow_eyes=(200, 255, 120), magic=(120, 255, 90), prop=staff_prop("flame", flame=((90, 220, 60), (210, 255, 150)))),
                         hairs=["bald"], pal=dict(a=(70, 120, 56), b=(46, 80, 46), c=(150, 220, 80))),
    "reaper": _named(spec=dict(hem=11.0, flare=1.6, sleeve="bell", hat="hood", hat_layer="a", belt=False, hem_trim=False, cloak=True, face_hidden=True,
                                glow_eyes=(255, 80, 80), prop=dict(kind="scythe", abs=dict(side=3, down=5, up=5))),
                     hairs=["bald"], pal=dict(a=(46, 42, 54), b=(34, 30, 40), c=(90, 80, 100))),
    "assassin": _named(spec=dict(hem=5.0, flare=0.6, sleeve="long", hat="bandana", hat_layer="a", belt=True, collar=True, cuff=True,
                                  prop=dict(kind="cleaver", abs=dict(side=170, down=170, up=170), follow=0.3)),
                       hairs=["short", "swept"], pal=dict(a=(52, 50, 64), b=(40, 40, 52), c=(150, 40, 50))),
    "knight": _named(spec=dict(hem=6.0, flare=1.0, sleeve="long", hat="helmet_round", belt=True, collar=True, cuff=True, hem_trim=True,
                                prop=[dict(kind="sword", abs=dict(side=150, down=160, up=160), follow=0.5), dict(kind="shield", hand="off", shape="kite", abs=0, follow=0.0)]),
                     hairs=["short"], pal=dict(a=(150, 156, 170), b=(96, 100, 116), c=(200, 60, 60))),
    "dwarf": _named(spec=dict(hem=4.0, flare=0.7, sleeve="short", hat="cap", hat_layer="a", belt=True, collar=False, boots="boots",
                               prop=dict(kind="pickaxe", abs=dict(side=14, down=10, up=10))),
                    hairs=["short"], pal=dict(a=(150, 100, 70), b=(86, 66, 56), c=(120, 80, 50))),
    "elf": _named(spec=dict(hem=5.0, flare=0.9, sleeve="long", hat="circlet", belt=True, collar=True, ears="pointed", hem_trim=True, cuff=True,
                             prop=dict(kind="bow", abs=dict(side=0, down=0, up=0), follow=0.5), back="quiver"),
                  hairs=["long"], pal=dict(a=(96, 170, 96), b=(120, 96, 70), c=(226, 196, 90))),
    "elder_green": _named(spec=dict(hem=9.0, flare=1.6, sleeve="bell", hat="wizard", hat_tip=3.2, hat_bend=1.0, belt=True, hem_trim=True, cuff=True, collar=True,
                                     prop=staff_prop("orb", magic=(90, 150, 255))), hairs=["balding"], pal=dict(a=(96, 150, 90), b=(60, 100, 66), c=(220, 190, 90))),
    "igbut": _named(spec=dict(hem=8.0, flare=1.4, sleeve="bell", hat="wizard", hat_tip=4.0, hat_bend=-2.0, belt=True, hem_trim=True, cuff=True, collar=True, cloak=True,
                               prop=dict(kind="book", abs=dict(side=0, down=0, up=0), follow=0.2, open=True)), hairs=["bob"], pal=dict(a=(80, 160, 160), b=(50, 100, 110), c=(226, 190, 90))),
    "ivy": _named(spec=dict(hem=6.0, flare=1.0, sleeve="short", belt=True, hem_trim=True, hat="laurel", prop=dict(kind="wand", abs=dict(side=0, down=0, up=0), follow=0.3, magic=(120, 255, 130))),
                  hairs=["long"], pal=dict(a=(70, 150, 70), b=(60, 100, 56), c=(150, 80, 170))),
    "official": _named(spec=dict(hem=8.0, flare=1.2, sleeve="long", hat="wizard", hat_tip=2.6, hat_bend=0.0, belt=True, collar=True, hem_trim=True, cuff=True,
                                  prop=dict(kind="scroll", abs=dict(side=0, down=0, up=0), follow=0.2)), hairs=["short"], pal=dict(a=(120, 70, 160), b=(80, 50, 110), c=(226, 190, 90))),
    "matron": _named(spec=dict(hem=10.0, flare=1.6, sleeve="long", belt=True, apron=True, apron_layer="c", apron_len=11.0, hem_trim=True, hat="headband", hat_layer="c"),
                     hairs=["bun"], pal=dict(a=(150, 70, 80), b=(110, 60, 70), c=(238, 232, 224))),
    "throm": _named(spec=dict(hem=3.0, flare=0.4, sleeve="none", belt=True, buckle=True, legs="trousers", hem_trim=False, collar=False,
                               prop=dict(kind="club", abs=dict(side=14, down=10, up=10))), hairs=["bald"], pal=dict(a=(206, 160, 120), b=(90, 76, 66), c=(130, 84, 50))),
})
