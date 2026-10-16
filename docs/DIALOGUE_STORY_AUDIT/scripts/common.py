"""Shared helpers for the dialogue and story audit (read-only: nothing here changes the game).

The audit scripts read the game's own data files and describe them in plain English. This module holds the glossaries (what each fact, flag kind,
effect kind and condition kind means) and the functions that turn a raw condition or effect into a sentence a non-programmer can read.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
REPO = HERE.parents[2]
HYBRID = REPO / "WizardRTSHybrid"
DATA = HYBRID / "wizard_rts" / "data"
DIALOGUE = DATA / "narrative" / "dialogue"
NARR = DATA / "narrative"

for p in (HYBRID, REPO, HYBRID / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


# ----------------------------------------------------------------------------------------------------------------------------------------------
# What the numbers mean (copied from the code: wizard.py, checks.py, sim/dmb/narrative/aspects.py, config.json). `validate_inventory.py` re-reads
# the code and fails if these drift.

ASPECTS = ("reason", "empathy", "authority", "guile", "resolve", "curiosity", "wonder")
ASPECT_NAMES = {a: a.capitalize() for a in ASPECTS}
THRESHOLDS = {"easy": 2, "demanding": 4, "exceptional": 6}
FALLIBILITY = {"reason": "overlooks emotion", "empathy": "overtrusts", "authority": "overvalues legitimacy", "guile": "suspects too much",
               "resolve": "persists unwisely", "curiosity": "discounts danger", "wonder": "overinterprets patterns"}
LESSON_TITLES = {"meet": "Speak with your mentor", "colours": "Learn the three colours", "told_ward": "Break a Ward you were told",
                 "hidden_ward": "Duel a hidden Ward", "flame_world": "Use Flame in the world (optional)", "world": "Hear what the village needs (optional)"}
WORLDVIEWS = {"M": "Monarchist", "A": "Anarchist", "R": "Religious", "G": "Guildist", "S": "Arcane Supremacist", "D": "Druidic", "C": "Illuminated / Mad"}
STAGES = {"training": "the mentor's lessons", "explore": "free exploration before the stranger", "arrival": "the stranger is walking in",
          "confrontation": "the stranger's scene", "duel": "the lethal duel with the stranger", "victory": "the stranger has been driven off",
          "aftermath": "the villagers react", "complete": "the introduction is over", "game_over": "the apprentice was defeated"}
SPELLS = {0: "Flame", 1: "Frost", 2: "Water", 3: "Stone", 4: "Light", 5: "Wind/Shadow", 6: "Vine", 9: "Arcane"}

# Facts a line can test. Where each is provided: L = the behaviour ledger (every conversation), O = the occupation facts of an ordinary person,
# R = resident facts (teacher/keeper/mother/official), M = the mother's facts, K = the keeper's facts, S = the scene facts.
FACT_DOC: dict[str, str] = {
    # ledger (counted for the world; "my_" is this wizard's own count)
    "pvp_duels": "duels fought between wizards in this world (any pair)",
    "pvp_wins": "duels between wizards that someone won",
    "pvp_losses": "duels between wizards that someone lost",
    "kills": "wizards killed by another wizard in this world",
    "deaths": "wizard deaths in this world",
    "resurrections": "wizards brought back from the dead in this world",
    "draws": "wizard duels that ended in a draw",
    "protests": "times a wizard protested to the mother after killing a friend",
    "provocations": "times a wizard asked Mira for a duel and was refused",
    "refused_steps": "steps the mother has refused while a wizard was grounded",
    "accosted": "times the mother has walked up to a grounded wizard to speak to them",
    "fourth_wall": "times a character has remarked that they are in a story (rare lines)",
    "my_pvp_duels": "this wizard's own wizard-versus-wizard duels", "my_pvp_wins": "this wizard's own wizard-duel wins", "my_pvp_losses": "this wizard's own wizard-duel losses",
    "my_kills": "wizards this wizard has killed", "my_deaths": "times this wizard has died", "my_resurrections": "wizards this wizard has brought back",
    "my_draws": "this wizard's own drawn duels", "my_protests": "this wizard's own protests", "my_provocations": "this wizard's own refused challenges to Mira",
    "my_refused_steps": "steps the mother refused this wizard", "my_accosted": "times the mother walked up to this wizard", "my_fourth_wall": "fourth-wall lines this wizard has seen",
    "pests_killed": "rats killed by wizards", "my_pests_killed": "rats this wizard has killed", "pest_escapes": "rats that escaped", "my_pest_escapes": "rats that escaped this wizard",
    "infestations_cleared": "rat infestations cleared", "burned_warehouse": "times a wizard burned the warehouse", "my_burned_warehouse": "times this wizard burned the warehouse",
    "sided_with_mason": "times the mason's side was backed", "sided_with_hauler": "times the carrier's side was backed", "found_the_granite": "times the missing granite was found",
    "trial_champion": "Trial of Champions won", "trial_betrayals": "times a wizard left Throm to cross the pit alone", "trial_mercies": "acts of mercy in the Trial",
    "trial_haste": "times a wizard took the charm and left the dying elf", "trial_wits": "puzzles solved cleverly in the Trial", "trial_riddles_right": "riddles answered correctly",
    # scene facts
    "lessons_done": "how many lessons this wizard has completed", "mira_present": "1 if the fellow apprentice Mira is alive in this world",
    "mira_near": "1 if Mira is within four tiles of the wizard", "logs": "logs in the settlement's warehouses",
    # occupation facts
    "keeper_complained_to": "times a wizard asked the keeper about the rats", "keeper_told_machines": "times a wizard told the keeper the rats are machines", "my_trial_entries": "times this wizard has gone into the Trial", "trial_entries": "times wizards have gone into the Trial",
    "trial_declared_unprepared": "times a wizard said ‘I am going in’ unprepared",
    "faction": "the settlement's faction name", "role": "the speaker's trade (lumberjack, ranger, stonemason, hunter, carrier, soldier, worker)",
    "workplace": "where the speaker works", "settlement": "the speaker's settlement", "trees_big": "mature or old trees within ten tiles of the speaker",
    "saplings": "saplings and poles within ten tiles of the speaker", "rocks": "rocks within ten tiles of the speaker", "animals": "living animals within twelve tiles",
    "soldiers": "living soldiers in the speaker's faction", "has_barracks": "the faction has an operating barracks", "barracks": "how many barracks (as words)",
    "hostile_near": "an enemy soldier is within 25 tiles of the speaker", "has_lumberjack": "the faction has a lumberjack", "carrying": "the ware the speaker is carrying",
    # mother facts
    "grounded": "1 if the mother is keeping her child at home", "victim": "name of the friend the child killed", "child": "name of the mother's child",
    "mentor_dead": "1 if the mentor has been killed", "arrived_after": "1 if the child joined the world after the mentor died", "generation": "which apprentice of this seat this is",
    "previous": "name of the apprentice who held this seat before",
    # keeper facts
    "pests_left": "rats still alive", "pests_total": "rats in this infestation", "killed_total": "rats killed so far (all wizards)", "my_killed": "rats this wizard killed",
    "others_killed": "rats other wizards killed", "cooperated": "1 if this wizard and another both killed rats", "eaten_total": "food items the rats have eaten",
    "complained": "1 if the keeper has complained to a wizard", "duels_since_complaint": "wizard-versus-wizard duels since the keeper's complaint",
    "burned": "1 if the warehouse was burned", "wave": "which wave of rats this is", "cleared": "1 if the current infestation is cleared",
    "minutes_since_complaint": "game minutes since the keeper first complained", "escapes": "rats that got away",
}

# What the apprentice can LEARN (campaign facts, written by `fact` effects, read by `fact` / `not_fact` conditions)
LEARNED_FACT_DOC: dict[str, str] = {
    "ward_lore": "the mentor told you why a Ward has three places", "mentor_old_craft": "the mentor admitted the light around his staff is an older craft",
    "ward_method": "the mentor explained how to read fracture and echo as a method", "mentor_creed": "you answered the mentor's question about why wizards do not rule",
    "mentor_wants_log": "the mentor asked you for a log for his brazier", "log_for_mentor": "you brought the mentor a log (set by the keeper)",
    "mentor_thanked": "the mentor thanked you for the log", "stood_firm": "you stood firm against the stranger (Resolve check passed)",
    "manticore_hates_light": "the Trial's old man told you the manticore hates light", "diamond_is_cold": "the dying elf told you the real diamond is cold",
    "dwarf_map": "the Dwarf gave you the map of the lower Trial", "bloodbeast_hates_vine": "the starved man told you the Bloodbeast hates Vine",
    "champion_of_the_trial": "you were crowned Champion of the Trial",
}

CONDITION_KINDS = {
    "requires": "Flags that must already be set (things this wizard has already done or heard in this conversation set).",
    "forbids": "Flags that must NOT be set.",
    "lessons": "Mentor lessons that must be done.", "not_lessons": "Mentor lessons that must NOT be done.",
    "unlocked": "Whether the village stories are unlocked (all four lessons done, or 20 game-minutes passed).",
    "quest": "The state of a village quest (offered, active, done).",
    "facts": "Numbers read live from the game world or the behaviour ledger (see the Facts table).",
    "role": "The speaker's trade.", "stage": "Which stage the campaign is in.", "knows": "What the speaker knows of the stranger's attack.",
    "persona": "The speaker's personality (worldviews, traits, attitude to magic and to the mentor).",
    "relationship": "How the speaker regards this wizard (-100 to 100).", "aspect": "This wizard's score in an Aspect.",
    "player_worldview": "The worldview this wizard leans towards most.", "fact": "A fact this wizard has learned.", "not_fact": "A fact this wizard has NOT learned.",
    "check": "The state of an earlier Aspect check with this speaker (untried / passed / failed).",
}

EFFECT_KINDS = {
    "learn_spell": "The wizard learns spells and a weave size.", "complete_lesson": "A mentor lesson is marked done.", "begin_duel": "A Ward duel starts; the conversation ends.",
    "journal_note": "A line is written into the wizard's journal.", "aspect": "An Aspect score changes by one point (once only).",
    "worldview": "The wizard's worldview leanings shift by the chosen view's table (once per answer).", "relationship": "The speaker's regard for the wizard changes.",
    "fact": "The wizard learns a fact.", "ledger": "A behaviour is counted in the ledger.", "challenge_stranger": "The wizard challenges the stranger to the lethal duel.",
    "ware_delta": "A ware moves out of (or into) the home warehouse through the economy's own accounting.", "pests_complained": "The keeper's complaint about the rats is recorded.",
    "kill_mentor": "The mentor is killed (a real death with a body).", "retreat": "The stranger walks away.", "note": "A line is written into the journal.",
}


ROLE_NAMES = {"cutter": "the woodcutter", "planter": "the forester", "witness": "the witness", "mason": "the mason", "hauler": "the carrier", "ranger": "the forester", "guard": "the guard"}


def aspect_label(a: str) -> str:
    return ASPECT_NAMES.get(a, a)


def th_label(name: str | int) -> str:
    if isinstance(name, int):
        return f"{name}"
    return f"{name} ({THRESHOLDS[name]})"


# ----------------------------------------------------------------------------------------------------------------------------------------------
# Plain-English descriptions of conditions and effects

class Describer:
    """Turns `when` blocks and effect lists into sentences. `flag_doc` maps (template, flag) to a plain meaning (built from who sets the flag)."""

    def __init__(self, flag_doc: dict[tuple[str, str], str] | None = None) -> None:
        self.flag_doc = flag_doc or {}

    def flag(self, tpl: str, f: str) -> str:
        doc = self.flag_doc.get((tpl, f))
        return f"“{doc}”" if doc else f"flag ‘{f}’"

    def fact_cond(self, c: dict[str, Any]) -> str:
        n = c["name"]
        label = FACT_DOC.get(n, n)
        parts = []
        if "gte" in c:
            parts.append(f"at least {c['gte']}")
        if "lte" in c:
            parts.append(f"at most {c['lte']}")
        if "eq" in c:
            parts.append(f"exactly {c['eq']}")
        if c.get("truthy"):
            parts.append("true / non-zero")
        if c.get("falsy"):
            parts.append("false / zero")
        return f"{n} ({label}) is " + " and ".join(parts)

    def when(self, tpl: str, w: dict[str, Any] | None) -> list[str]:
        if not w:
            return []
        out: list[str] = []
        for f in w.get("requires", []):
            out.append(f"{self.flag(tpl, f)} has happened")
        for f in w.get("forbids", []):
            out.append(f"{self.flag(tpl, f)} has NOT happened")
        for l in w.get("lessons", []):
            out.append(f"lesson done: {LESSON_TITLES.get(l, l)}")
        for l in w.get("not_lessons", []):
            out.append(f"lesson NOT yet done: {LESSON_TITLES.get(l, l)}")
        if "unlocked" in w:
            out.append("the village stories are unlocked" if w["unlocked"] else "the village stories are still locked")
        if "quest" in w:
            out.append(f"quest ‘{w['quest']['id']}’ is {' / '.join(w['quest']['in'])}")
        for c in w.get("facts", []):
            out.append(self.fact_cond(c))
        if "role" in w:
            out.append("speaker’s trade is " + " or ".join(w["role"]))
        if "stage" in w:
            out.append("campaign stage is " + " or ".join(f"{s} ({STAGES.get(s, s)})" for s in w["stage"]))
        if "knows" in w:
            out.append("speaker’s knowledge of the attack is " + " or ".join(w["knows"]))
        if "persona" in w:
            out.extend(self.persona(w["persona"]))
        if "relationship" in w:
            r = w["relationship"]
            bits = []
            if "gte" in r:
                bits.append(f"at least {r['gte']}")
            if "lte" in r:
                bits.append(f"at most {r['lte']}")
            out.append("speaker’s regard for you (−100..100) is " + " and ".join(bits))
        if "aspect" in w:
            out.append(f"your {aspect_label(w['aspect']['id'])} is at least {w['aspect']['gte']}")
        if "player_worldview" in w:
            out.append("your strongest worldview is " + " or ".join(WORLDVIEWS.get(c, c) for c in w["player_worldview"]))
        for f in w.get("fact", []):
            out.append(f"you have learned: {LEARNED_FACT_DOC.get(f, f)}")
        for f in w.get("not_fact", []):
            out.append(f"you have NOT learned: {LEARNED_FACT_DOC.get(f, f)}")
        if "check" in w:
            out.append(f"the earlier check ‘{w['check']['id']}’ is {w['check']['state']}")
        return out

    @staticmethod
    def persona(p: dict[str, Any]) -> list[str]:
        out = []
        if "primary" in p:
            out.append("speaker’s main worldview is " + " or ".join(WORLDVIEWS.get(c, c) for c in p["primary"]))
        if "secondary" in p:
            out.append("speaker’s second worldview is " + " or ".join(WORLDVIEWS.get(c, c) for c in p["secondary"]))
        if "any" in p:
            out.append("speaker’s main or second worldview is " + " or ".join(WORLDVIEWS.get(c, c) for c in p["any"]))
        if "trait" in p:
            out.append("speaker has the trait " + " or ".join(p["trait"]))
        if "mentor" in p:
            out.append("speaker’s attitude to the mentor is " + " or ".join(p["mentor"]))
        if "magic" in p:
            out.append("speaker’s attitude to magic is " + " or ".join(p["magic"]))
        return out

    def when_text(self, tpl: str, w: dict[str, Any] | None, extra: list[str] | None = None) -> str:
        parts = self.when(tpl, w) + list(extra or [])
        return "; ".join(parts) if parts else "Always"

    def check(self, tpl: str, ck: dict[str, Any]) -> str:
        ev = ck.get("evidence", [])
        evs = "; ".join(f"+{e.get('mod', 1)} if {self.when_text(tpl, e.get('when'))}" for e in ev) or "none"
        return f"{aspect_label(ck['aspect'])} against {th_label(ck.get('threshold', 'demanding'))}; evidence: {evs}"

    def effect(self, tpl: str, e: dict[str, Any]) -> str:
        k = e["kind"]
        if k == "learn_spell":
            return "Learn " + ", ".join(SPELLS.get(s, str(s)) for s in e["spells"]) + (f"; weave size {e['weave_size']}" if e.get("weave_size") else "")
        if k == "complete_lesson":
            return f"Lesson done: {LESSON_TITLES.get(e['lesson'], e['lesson'])}"
        if k == "begin_duel":
            fw = f"; the opponent’s Ward is fixed and told: {', '.join(SPELLS.get(x, str(x)) for x in e['fixed_ward'])}" if e.get("fixed_ward") else ""
            return f"Start a Ward duel against {e['opponent']} (purpose: {e['purpose']}){fw}"
        if k in ("journal_note", "note"):
            return f"Journal note: “{e['text']}”"
        if k == "aspect":
            d = int(e["delta"])
            return f"{aspect_label(e['aspect'])} {'+1' if d > 0 else '−1'} (once only)"
        if k == "worldview":
            return f"Worldview shift towards {WORLDVIEWS.get(e['code'], e['code'])} (the table row for that view, once)"
        if k == "relationship":
            who = f" of {ROLE_NAMES.get(e['who'], e['who'])}" if e.get("who") else " of the speaker"
            return f"Regard{who} for you {int(e['delta']):+d}"
        if k == "fact":
            return f"You learn: {LEARNED_FACT_DOC.get(e['id'], e['id'])}"
        if k == "ledger":
            return f"Ledger count ‘{e['key']}’ +{e.get('n', 1)}"
        if k == "challenge_stranger":
            return "You challenge the stranger: the lethal duel will follow the scene"
        if k == "ware_delta":
            return f"Warehouse: {int(e.get('n', -1)):+d} {e['good']} (moved through the economy’s own ledger)"
        if k == "pests_complained":
            return "The keeper’s complaint about the rats is recorded"
        if k == "kill_mentor":
            return "The mentor is killed (a real death: body, tombstone, journal note)"
        if k == "retreat":
            return "The stranger walks away from the village"
        return json.dumps(e, ensure_ascii=False)

    def effects(self, tpl: str, block: dict[str, Any]) -> list[str]:
        out = []
        for f in block.get("sets", []):
            out.append(f"Set {self.flag(tpl, f)}")
        for f in block.get("clears", []):
            out.append(f"Clear {self.flag(tpl, f)}")
        for e in block.get("effects", []):
            once = "" if e["kind"] in ("begin_duel", "ledger", "pests_complained") else " [once]"
            scope = " [per person]" if e.get("scope") == "person" else ""
            out.append(self.effect(tpl, e) + once + scope)
        return out


# ----------------------------------------------------------------------------------------------------------------------------------------------
# What each dialogue flag means in plain English ("template::flag"). Flags are per wizard (each seat has its own) and are set by choices or lines.

FLAG_MEANING: dict[str, str] = {
    # Forest Dispute
    "forest_dispute::heard_cutter": "you have heard the woodcutter's side", "forest_dispute::heard_planter": "you have heard the forester's side",
    "forest_dispute::asked_cutter_want": "you asked the woodcutter what would settle it", "forest_dispute::asked_planter_want": "you asked the forester what would settle it",
    "forest_dispute::witness_saw": "the witness told you what they actually saw", "forest_dispute::witness_gossip": "the witness told you only gossip",
    "forest_dispute::outcome_compromise": "you settled the dispute with a compromise", "forest_dispute::outcome_cutter": "you backed the woodcutter",
    "forest_dispute::outcome_planter": "you backed the forester", "forest_dispute::outcome_none": "you stayed out of the dispute",
    "forest_dispute::closed_cutter": "the woodcutter has spoken his closing reaction", "forest_dispute::closed_planter": "the forester has spoken her closing reaction",
    "forest_dispute::done": "the witness has spoken the closing reaction (the quest counts as done)",
    "forest_dispute::sub_cutter": "the woodcutter role was taken over by a different villager", "forest_dispute::sub_planter": "the forester role was taken over by a different villager",
    "forest_dispute::sub_witness": "the witness role was taken over by a different villager",
    # The Missing Granite
    "smith_dispute::heard_mason": "you have heard the mason's side", "smith_dispute::heard_hauler": "you have heard the carrier's side",
    "smith_dispute::outcome_mason": "you backed the mason (the warehouse gave up a load of granite)", "smith_dispute::outcome_hauler": "you backed the carrier",
    "smith_dispute::outcome_found": "you worked out the granite was under the grout sacks", "smith_dispute::closed_mason": "the mason has spoken his closing reaction",
    "smith_dispute::closed_hauler": "the carrier has spoken their closing reaction",
    # The Patrol
    "ranger_patrol::heard_ranger": "you have heard the forester talk about the patrol", "ranger_patrol::heard_cloak": "the forester told you about the cloaked stranger",
    "ranger_patrol::heard_trial": "the forester told you about the Trial gate", "ranger_patrol::patrol_east": "you advised sending the patrol east",
    "ranger_patrol::patrol_north": "you advised sending the patrol north", "ranger_patrol::patrol_set": "a patrol route has been chosen", "ranger_patrol::closed_ranger": "the forester has spoken the closing reaction",
    # Mother
    "mother::mourned": "the mother has mourned with you after you died", "mother::thanked": "the mother has thanked you for bringing a friend back",
    "mother::told_after": "the mother has told you the news after you arrived late", "mother::told_news": "the mother has told you the news",
    # Trial gate
    "trial_gate::said_killers": "the Rollkeeper has warned you about killers", "trial_gate::said_unprepared": "the Rollkeeper has warned you that you are unprepared",
    "trial_gate::gave_advice": "you asked the Rollkeeper for advice (whether or not the Empathy check passed)",
    # Mentor
    "tutorial::meet": "you have had your first conversation with the mentor", "tutorial::colours": "the mentor has taught (or acknowledged) the three colours",
    "tutorial::creed_done": "you answered the mentor's question about why wizards do not rule", "tutorial::rumour_known": "the mentor told you about the quarrel in the forest",
    "tutorial::flame_praised": "the mentor praised your use of Flame", "tutorial::said_mira": "the mentor remarked on Mira", "tutorial::said_steered": "the mentor remarked on your two deaths",
    "tutorial::said_killer": "the mentor gave his speech about killing a friend", "tutorial::said_died": "the mentor remarked that you died and were brought back",
    "tutorial::said_brawler": "the mentor remarked on your early duels",
    "tutorial::told_fresh": "you just finished the ‘told Ward’ duel (the mentor comments once)", "tutorial::told_won": "you won the ‘told Ward’ duel",
    "tutorial::hidden_fresh": "you just finished the hidden-Ward duel (the mentor comments once)", "tutorial::hidden_won": "you won the hidden-Ward duel",
    "tutorial::quick": "you won in three casts or fewer",
    # Warehouse keeper
    "warehouse::said_burned": "the keeper has spoken of the burned warehouse", "warehouse::said_cleared": "the keeper has spoken about the cleared rats",
    "warehouse::said_duelling": "the keeper has complained that you duelled instead of fighting rats",
}
