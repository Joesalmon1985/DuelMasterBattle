"""Read-only extraction of every piece of Wizard World dialogue that the data files and the runtime code contain.

Run:  python docs/DIALOGUE_STORY_AUDIT/scripts/extract_inventory.py
Writes: docs/DIALOGUE_STORY_AUDIT/generated/inventory.json   (the workbook, the diagrams and the validator all read this one file)

Nothing in the game is changed. The extractor opens the dialogue JSON (`wizard_rts/data/narrative/dialogue/*.json`, `ai_wizards.json`, `trial/*.json`,
`story/*.json`) and the Python modules that hold dialogue text, and writes plain rows. Every row carries its source file and path so that a line in
the workbook can be found in the game's files again.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

from common import (DATA, DIALOGUE, FLAG_MEANING, HYBRID, NARR, OUT, REPO, THRESHOLDS, WORLDVIEWS, Describer, aspect_label, load_json, rel)

GEN = OUT / "generated"
GEN.mkdir(exist_ok=True)

# ----------------------------------------------------------------------------------------------------------------------------------------------
# The collections (stories, conversations, dialogue banks) and who speaks in them

COLLECTIONS: list[dict[str, Any]] = [
    {"id": "CV-OPEN", "title": "The opening narration", "kind": "Narration", "file": "tutorial.json", "status": "Playable",
     "where": "A card shown once when a new campaign world starts, before the player has control",
     "how": "Automatic: shown on the first launch of a new world (not shown again once dismissed).",
     "prereq": "A new campaign world with a mentor cast.", "characters": "Narrator", "summary": "Three paragraphs that set the scene: six winters of apprenticeship, magic is rare but does not make a ruler, the mentor has sent for you."},
    {"id": "CV-MENTOR", "title": "The Mentor: introduction, lessons and the creed question", "kind": "Authored conversation (lessons)", "file": "tutorial.json", "status": "Playable",
     "where": "In the home settlement, standing near the square",
     "how": "Walk up to the mentor and press E (or click and choose Talk).",
     "prereq": "None for the first talk. Each lesson unlocks the next. The creed question needs the first talk only.",
     "characters": "Mentor (authored); Mira may be mentioned; the apprentice (you)",
     "summary": "The mentor greets you, teaches the three colours, lets you break a Ward you are told, then a hidden Ward, and asks why wizards do not rule. Skill questions about Wards, the staff's glow and fracture/echo reading reveal secrets the stranger scene later uses. After the lessons the mentor points you at the village."},
    {"id": "CV-FOREST", "title": "The Forest Dispute (quest)", "kind": "Village quest", "file": "forest_dispute.json", "status": "Playable (needs a woodcutter, a forester and a witness in the settlement)",
     "where": "Wherever the three chosen villagers happen to be working",
     "how": "Ask the mentor 'What should I do now?' after the lessons (it names the three people), or just talk to the woodcutter or forester.",
     "prereq": "Stories unlocked (all four lessons done or 20 game-minutes). The settlement needs a lumberjack, a ranger and a witness (soldier, else stonemason/hunter, else carrier).",
     "characters": "Woodcutter, Forester, Witness (ordinary villagers cast from the simulation)",
     "summary": "A woodcutter and a forester have fallen out over felling young trees. Hear both, optionally ask the witness, then choose: compromise, back the woodcutter, back the forester, or stay out."},
    {"id": "CV-GRANITE", "title": "The Missing Granite (quest)", "kind": "Village quest", "file": "smith_dispute.json", "status": "Playable (needs a stonemason and a carrier)",
     "where": "Wherever the mason and the carrier are", "how": "Talk to the stonemason or carrier once stories are unlocked.",
     "prereq": "Stories unlocked. A stonemason and a carrier in the settlement.",
     "characters": "Mason, Carrier (ordinary villagers)", "summary": "A mason says a load of granite never arrived; a carrier says it did. Back the mason (costs the warehouse a real load of granite), back the carrier, or work out where it went (Reason check)."},
    {"id": "CV-PATROL", "title": "The Patrol (quest)", "kind": "Village quest", "file": "ranger_patrol.json", "status": "Playable (needs a forester; a guard is optional)",
     "where": "Wherever the forester and the guard are", "how": "Talk to the forester or the guard once stories are unlocked.",
     "prereq": "Stories unlocked. A ranger in the settlement; a soldier is optional.",
     "characters": "Forester, Guard (optional soldier)", "summary": "A forester prepares a patrol of the valley's edge and wants a guard to walk with them."},
    {"id": "CV-WAREHOUSE", "title": "The warehouse keeper and the rats", "kind": "Authored conversation + event", "file": "warehouse.json", "status": "Playable",
     "where": "Beside the home settlement's central warehouse", "how": "Talk to the keeper. Rats around the warehouse can be fought (Ward duels).",
     "prereq": "The campaign has started. The keeper reads what the rats have done and what wizards have done about them.",
     "characters": "Warehouse keeper; five rats (two sizes)", "summary": "Rats are eating the stores. The keeper complains, reacts to who fights them, to cooperation, to fire, and rewards a cleared warehouse. A smaller wave returns later."},
    {"id": "CV-MOTHER", "title": "The apprentice's mother", "kind": "Authored conversation (reactive)", "file": "mother.json", "status": "Playable",
     "where": "In the home settlement; she walks to a grounded apprentice", "how": "She is cast beside each new apprentice. If a wizard kills their friend at home, she confronts them and grounds them until the friend is brought back.",
     "prereq": "A wizard has killed another wizard within the home territory (for the grounding lines); otherwise she greets.",
     "characters": "The mother (one per wizard seat)", "summary": "Her lines escalate with what the apprentice has done: kills, protests, resurrections and deaths. She refuses to let them walk away from a dead friend."},
    {"id": "CV-STRANGER", "title": "The stranger: arrival, confrontation, duel and retreat", "kind": "Scripted scenes (campaign)", "file": "campaign_scenes.json", "status": "Playable",
     "where": "The home settlement's square", "how": "Automatic: after enough exploring (3 minutes and 3 contacts, or 7 minutes regardless) when nothing else owns the player.",
     "prereq": "The lessons are over (or 5 minutes passed, or a wizard duel/death happened). Nothing else open (no conversation, duel or dungeon).",
     "characters": "The stranger (authored), the mentor, the apprentice, Mira (optional line)", "summary": "A stranger in a dark cloak kills the mentor in front of the village. The apprentice may answer with a belief, challenge him to a lethal Ward duel, or let him go. A verified win makes him retreat alive; a loss is the apprentice's death."},
    {"id": "CV-AFTER", "title": "After the stranger: what the villagers say", "kind": "Dynamic dialogue (reactions + topics)", "file": "aftermath.json", "status": "Playable",
     "where": "Any ordinary villager, worker, carrier or soldier of the settlement", "how": "Talk to any villager after the stranger has been driven off.",
     "prereq": "Campaign stage victory, aftermath or complete.",
     "characters": "Every ordinary villager (dynamic personas)", "summary": "Each person speaks first about the attack, chosen by their trade, what they saw (witnessed, rumour) and their personality. Topics offer Aspect checks (Curiosity, Empathy, Authority, Guile, Reason) and ideological replies."},
    {"id": "CV-EVERYDAY", "title": "Everyday talk by occupation", "kind": "Dynamic dialogue (topics)", "file": "occupations.json", "status": "Playable",
     "where": "Any ordinary lumberjack, forester, stonemason, hunter, carrier or soldier; any other worker", "how": "Walk up and press E; click and choose Talk. A worker inside a building must be asked out first.",
     "prereq": "None; topics appear only when their conditions hold in the live simulation.",
     "characters": "Ordinary villagers (dynamic personas)", "summary": "Seven occupation sets: an introduction, greetings and 4-8 topics each, plus topics shared by everyone (opinions of the mentor, wizards, apprentices, thanks, road rumours, a rare fourth-wall remark)."},
    {"id": "CV-TRIALGATE", "title": "The Trial gate: the Rollkeeper and the contestants", "kind": "Authored conversation", "file": "trial_gate.json", "status": "Playable",
     "where": "At the Trial's gate east of the village, and inside the first zone", "how": "Walk to the gate and talk to the Rollkeeper; talk to the contestants in the entrance zone.",
     "prereq": "The Trial gate exists in the world (campaign). Entering needs a wizard who is not grounded.",
     "characters": "Rollkeeper (official), a knight, an elf, Throm, a barbarian, an assassin", "summary": "The Rollkeeper registers contestants and warns about the Trial; contestants speak in the entrance zone."},
    {"id": "CV-TRIAL", "title": "The Trial of Champions (zones, signs, choices)", "kind": "Choice events (book-style)", "file": "trial/events.py + data/trial/*.json", "status": "Playable (zones A to K; some passages unverified)",
     "where": "Inside the Trial dungeon (17 zones)", "how": "Enter through the gate; walk and interact with signs, people and objects.",
     "prereq": "Enter the gate. Many choices depend on earlier choices in the same run (shared by all wizards in the run).",
     "characters": "Throm, the Dwarf Trialmaster, the old man, the dying elf, Poison Ivy, the Basket man, Igbut, ritual elder and others", "summary": "Fifteen choice events with consequences: wounds, allies, learned facts, items, a champion's exit."},
    {"id": "CV-MIRA", "title": "Mira, the AI fellow apprentice", "kind": "AI companion lines", "file": "ai_wizards.json + net/ai_wizard.py", "status": "Playable (single-player only; the AI seat is the second seat)",
     "where": "Follows the human wizard everywhere, including into the Trial", "how": "Automatic in single player. Challenge her to a duel; she declines twice and accepts the third time.",
     "prereq": "A single-player hosted world (the AI seat exists).", "characters": "Mira (authored AI wizard)", "summary": "She greets, declines challenges, duels, reacts to wins/losses/death, resurrects friends, helps with rats and follows into the Trial."},
    {"id": "CV-SYSTEM", "title": "System and presentation text (toasts, fallbacks, journal notes)", "kind": "System text", "file": "various", "status": "Playable",
     "where": "Everywhere", "how": "Triggered by events: deaths, resurrections, notices, refusals, journal entries.", "prereq": "Varies.", "characters": "System", "summary": "Fallback lines, refusals, toasts and journal notes written by the code rather than by dialogue data."},
    {"id": "CV-LEGACY-MINE", "title": "Legacy story layer: the collapsed gallery (miner quest)", "kind": "Legacy quest (still wired)", "file": "story.py + data/story/*.json", "status": "Partially reachable: appears only if the simulation collapses a mine",
     "where": "Beside the collapsed mine", "how": "A miner appears when a working mine's gallery collapses (tremor, war damage, age). Talk to the miner.",
     "prereq": "A mine collapse in the live simulation. Not on demand.", "characters": "Miner", "summary": "The miner explains the fall, tells of an old gallery, hands over a sigil, and an Empathy check can earn extra casts in the warden's Mastermind duel."},
    {"id": "CV-LEGACY-OUTBREAK", "title": "Legacy story layer: the outbreak healer", "kind": "Legacy quest (still wired)", "file": "story.py + data/story/*.json", "status": "Partially reachable: appears only if the simulation produces an outbreak",
     "where": "In a settlement whose region holds two or more outbreak marks", "how": "A healer appears; talk to them and accept to treat the region.",
     "prereq": "An outbreak (two or more marks) in a standing settlement's region.", "characters": "Healer of <settlement>", "summary": "The healer reports the outbreak; the wizard accepts and stands in the region to treat it, or says they cannot help."},
]

SPEAKER_NAMES: dict[tuple[str, str], str] = {
    ("tutorial", "teacher"): "Mentor", ("forest_dispute", "cutter"): "Woodcutter", ("forest_dispute", "planter"): "Forester", ("forest_dispute", "witness"): "Witness",
    ("smith_dispute", "mason"): "Mason", ("smith_dispute", "hauler"): "Carrier", ("ranger_patrol", "ranger"): "Forester", ("ranger_patrol", "guard"): "Guard",
    ("warehouse", "keeper"): "Warehouse keeper", ("mother", "mother"): "Mother", ("trial_gate", "official"): "The Rollkeeper", ("trial_gate", "knight"): "Knight contestant",
    ("trial_gate", "elf"): "Elf contestant", ("trial_gate", "throm"): "Throm", ("trial_gate", "barbarian"): "Barbarian contestant", ("trial_gate", "assassin"): "Assassin contestant",
}
TEMPLATE_CONV = {"tutorial": "CV-MENTOR", "forest_dispute": "CV-FOREST", "smith_dispute": "CV-GRANITE", "ranger_patrol": "CV-PATROL", "warehouse": "CV-WAREHOUSE",
                 "mother": "CV-MOTHER", "trial_gate": "CV-TRIALGATE"}
TEMPLATE_SHORT = {"tutorial": "MENTOR", "forest_dispute": "FOREST", "smith_dispute": "GRANITE", "ranger_patrol": "PATROL", "warehouse": "WAREHOUSE", "mother": "MOTHER",
                  "trial_gate": "TRIALGATE"}
# Flags the engine itself sets (not a dialogue file): tutorial.on_duel_resolved, quests._substitute
ENGINE_FLAGS = {"tutorial": {"told_fresh", "told_won", "hidden_fresh", "hidden_won", "quick"}}
# What each speaker's regard for the apprentice is when the game starts (checks.relationship): the mentor 40, the mother 60, everybody else 0.
START_RELATIONSHIP = {("tutorial", "teacher"): 40, ("mother", "mother"): 60}
START_ASPECTS = load_json(NARR / "config.json")["campaign"]["start_aspects"]
CONFIG = load_json(NARR / "config.json")


def band(r: int) -> int:
    return -1 if r <= -25 else (1 if r >= 25 else 0)


CONV_SHORT = {"CV-OPEN": "OPEN", "CV-MENTOR": "MENTOR", "CV-FOREST": "FOREST", "CV-GRANITE": "GRANITE", "CV-PATROL": "PATROL", "CV-WAREHOUSE": "WAREHOUSE", "CV-MOTHER": "MOTHER",
              "CV-STRANGER": "STRANGER", "CV-AFTER": "AFTER", "CV-EVERYDAY": "EVERYDAY", "CV-TRIALGATE": "TRIALGATE", "CV-TRIAL": "TRIAL", "CV-MIRA": "MIRA"}


def clean(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_\-:]+", "_", str(s)).strip("_")


class Extractor:
    def __init__(self) -> None:
        self.lines: list[dict[str, Any]] = []
        self.choices: list[dict[str, Any]] = []
        self.checks: list[dict[str, Any]] = []
        self.nodes: list[dict[str, Any]] = []
        self.pools: list[dict[str, Any]] = []
        self.setters: dict[tuple[str, str], list[str]] = {}   # (template, flag) -> [choice/variant ids that set it]
        self.readers: dict[tuple[str, str], list[str]] = {}
        self.fact_setters: dict[str, list[str]] = {}
        self.fact_readers: dict[str, list[str]] = {}
        self.desc = Describer({tuple(k.split('::')): v for k, v in FLAG_MEANING.items()})
        self.n = 0

    # ------------------------------------------------------------------ small helpers
    def src(self, file: Path, path: str) -> dict[str, str]:
        return {"source_file": rel(file), "source_path": path}

    def record_when(self, tpl: str, w: dict[str, Any] | None, who: str) -> None:
        if not w:
            return
        for k in ("requires", "forbids"):
            for f in w.get(k, []):
                self.readers.setdefault((tpl, f), []).append(who)
        for f in w.get("fact", []) + w.get("not_fact", []):
            self.fact_readers.setdefault(f, []).append(who)

    def record_block(self, tpl: str, block: dict[str, Any], who: str) -> None:
        for f in block.get("sets", []):
            self.setters.setdefault((tpl, f), []).append(who)
        for e in block.get("effects", []):
            if e["kind"] == "fact":
                self.fact_setters.setdefault(e["id"], []).append(who)
        for branch in ("pass", "fail", "blocked"):
            if branch in block:
                self.record_block(tpl, block[branch], who + "." + branch)

    @staticmethod
    def line_items(lines: list[Any]) -> list[tuple[str, dict[str, Any] | None]]:
        out = []
        for l in lines:
            if isinstance(l, dict):
                out.append((l["text"], l.get("when")))
            else:
                out.append((str(l), None))
        return out

    def add_lines(self, *, conv: str, tpl: str, speaker: str, speaker_name: str, node: str, block: str, line_type: str, lines: list[Any],
                  when: dict[str, Any] | None, extra_cond: list[str] | None, effects: list[str], reached: str, file: Path, path: str, order: int | None = None,
                  notes: str = "", alt_of: str = "", ref: str = "") -> list[str]:
        ids = []
        items = self.line_items(lines)
        for i, (text, lw) in enumerate(items, 1):
            self.n += 1
            lid = f"{CONV_SHORT.get(conv, conv)}.{clean(speaker)}.{clean(node)}.{block}.{i}"
            conds = self.desc.when(tpl, when) + list(extra_cond or []) + self.desc.when(tpl, lw)
            self.record_when(tpl, lw, lid)
            self.lines.append({"id": lid, "n": self.n, "conv": conv, "tpl": tpl, "speaker_key": speaker, "speaker": speaker_name, "node": node, "block": block,
                               "line_type": line_type, "text": text, "cond": "; ".join(conds) if conds else "Always", "cond_raw": json.dumps({"block": when, "line": lw}, ensure_ascii=False) if (when or lw) else "",
                               "effects": "; ".join(effects) if effects else "", "reached": reached, "order": order, "notes": notes, "alt_of": alt_of, "ref": ref,
                               **self.src(file, path + (f"/lines/{i - 1}" if len(items) > 1 or isinstance(lines[0], dict) else "/lines/0"))})
            ids.append(lid)
        return ids

    # ------------------------------------------------------------------ graph templates (tutorial, quests, keeper, mother, Trial gate)
    def classify_variant(self, v: dict[str, Any], idx: int, total: int) -> str:
        w = v.get("when") or {}
        sets = set(v.get("sets", []))
        forbids = set(w.get("forbids", []))
        requires = set(w.get("requires", []))
        if sets and sets & forbids:
            if any(r.startswith("outcome_") for r in requires):
                return "Ending reaction (said once)"
            return "Introduction or one-time remark"
        if not w:
            return "Introduction / default greeting"
        if any(r.startswith(("closed_", "done")) for r in requires) and not sets:
            return "Repeat after the ending"
        if any(r.startswith(("outcome_",)) for r in requires):
            return "Ending reaction"
        return "Greeting / repeat"

    def walk_template(self, tpl: str, file: Path) -> None:
        data = load_json(file)
        conv = TEMPLATE_CONV[tpl]
        short = TEMPLATE_SHORT[tpl]
        for sp_key, sp in data["speakers"].items():
            sp_name = SPEAKER_NAMES.get((tpl, sp_key), sp_key)
            for node_id, node in sp["nodes"].items():
                npath = f"speakers/{sp_key}/nodes/{node_id}"
                self.nodes.append({"id": f"{short}.{sp_key}.{node_id}", "conv": conv, "tpl": tpl, "speaker": sp_name, "speaker_key": sp_key, "node": node_id,
                                   "variants": len(node.get("variants", [])), "choices": len(node.get("choices", []))})
                variants = node.get("variants", [])
                for vi, v in enumerate(variants):
                    vid = v.get("id") or f"v{vi + 1}"
                    who = f"{short}.{sp_key}.{node_id}.v-{vid}"
                    self.record_when(tpl, v.get("when"), who)
                    self.record_block(tpl, v, who)
                    ltype = self.classify_variant(v, vi, len(variants))
                    eff = self.desc.effects(tpl, v)
                    extra = [f"no earlier entry of this node applied (entry {vi + 1} of {len(variants)}; the first one whose conditions hold is spoken)"]
                    ids = self.add_lines(conv=conv, tpl=tpl, speaker=sp_key, speaker_name=sp_name, node=node_id, block=f"v-{vid}", line_type=ltype, lines=v["lines"],
                                         when=v.get("when"), extra_cond=extra, effects=eff, reached="Automatic when the conversation opens or returns to this node", file=file,
                                         path=f"{npath}/variants/{vi}", order=vi + 1, ref="")
                    for ai, alt in enumerate(v.get("lines_alt", []), 1):
                        self.add_lines(conv=conv, tpl=tpl, speaker=sp_key, speaker_name=sp_name, node=node_id, block=f"v-{vid}.alt{ai}", line_type=ltype + " (alternate wording)",
                                       lines=alt, when=v.get("when"), extra_cond=extra + [f"alternate wording {ai}: the variant rotates through its wordings each time it is heard"],
                                       effects=eff, reached="Automatic (rotates with the number of times the variant has been heard)", file=file,
                                       path=f"{npath}/variants/{vi}/lines_alt/{ai - 1}", order=vi + 1, alt_of=ids[0] if ids else "", ref="")
                for ci, c in enumerate(node.get("choices", [])):
                    self.walk_choice(tpl, conv, short, sp_key, sp_name, node_id, c, ci, file, f"{npath}/choices/{ci}", [n for n in sp["nodes"]], data)
                # data-driven flags set by choices
        for sp_key, sp in data["speakers"].items():
            pass

    def walk_choice(self, tpl: str, conv: str, short: str, sp_key: str, sp_name: str, node_id: str, c: dict[str, Any], ci: int, file: Path, path: str,
                    node_names: list[str], data: dict[str, Any]) -> None:
        cid = f"{short}.{sp_key}.{node_id}.c-{c['id']}"
        self.record_when(tpl, c.get("when"), cid)
        self.record_block(tpl, c, cid)
        if c.get("once"):
            self.setters.setdefault((tpl, "done:" + c["id"]), []).append(cid)
        ck = c.get("check")
        conds = self.desc.when(tpl, c.get("when"))
        if c.get("once"):
            conds.append("not already chosen (this choice can be taken only once)")
        ends = bool(c.get("ends"))
        pass_b, fail_b = c.get("pass"), c.get("fail")
        goto = c.get("goto", "hub")
        has_duel = any(e["kind"] == "begin_duel" for e in c.get("effects", []))
        if has_duel:
            dest_main = "A Ward duel starts and the conversation ends; the mentor speaks again when the duel is over"
        elif ends:
            dest_main = "Conversation ends"
        elif goto != "hub":
            dest_main = f"Moves to node ‘{goto}’ of the same speaker"
        else:
            dest_main = "Stays in the conversation (back to the speaker's hub)"
        success = dest_main
        failure = ""
        if ck:
            success = "Check passed: " + ("conversation ends" if (pass_b or {}).get("ends") else "stays in the conversation")
            failure = "Check failed: " + ("conversation ends" if (fail_b or {}).get("ends") else "stays in the conversation; this choice is greyed out until something changes (see Rules: retry)")
        text = c["text"]
        label = f"[{aspect_label(ck['aspect'])}] " + text if ck else text
        eff_main = self.desc.effects(tpl, {k: v for k, v in c.items() if k in ("sets", "clears", "effects")})
        eff_pass = self.desc.effects(tpl, pass_b) if pass_b else []
        eff_fail = self.desc.effects(tpl, fail_b) if fail_b else []
        if goto != "hub" and goto not in node_names:
            goto_bad = True
        else:
            goto_bad = False
        row = {"id": cid, "conv": conv, "tpl": tpl, "speaker": sp_name, "speaker_key": sp_key, "node": node_id, "choice_id": c["id"], "kind": "Choice", "text": label,
               "raw_text": text, "cond": "; ".join(conds) if conds else "Always offered", "aspect": aspect_label(ck["aspect"]) if ck else "",
               "threshold": th_label(ck.get("threshold", "demanding")) if ck else "", "evidence": "; ".join(f"+{e.get('mod', 1)}: {self.desc.when_text(tpl, e.get('when'))}" for e in ck.get("evidence", [])) if ck else "",
               "relationship_req": self._rel_req(c.get("when")), "persona_req": self._persona_req(tpl, c.get("when")),
               "success": success, "failure": failure, "other": ("BROKEN destination: " + goto) if goto_bad else "", "effects": "; ".join(eff_main), "pass_effects": "; ".join(eff_pass),
               "fail_effects": "; ".join(eff_fail), "ends": "Yes" if (ends or has_duel) else ("Only if the check passes" if (pass_b or {}).get("ends") else "No"), "once": "Yes" if c.get("once") else "",
               "goto": goto, "order": ci + 1, **self.src(file, path)}
        self.choices.append(row)
        if ck:
            self.checks.append(self.check_row(tpl, conv, sp_name, sp_key, cid, c, ck, path, file, text))
        # The lines the choice speaks
        reached = f"Choice {cid}"
        base_eff = eff_main
        if c.get("lines"):
            self.add_lines(conv=conv, tpl=tpl, speaker=sp_key, speaker_name=sp_name, node=node_id, block=f"c-{c['id']}", line_type="Response (ends conversation)" if ends else "Response",
                           lines=c["lines"], when=c.get("when"), extra_cond=[], effects=base_eff, reached=reached, file=file, path=path, ref=cid)
        if pass_b:
            self.add_lines(conv=conv, tpl=tpl, speaker=sp_key, speaker_name=sp_name, node=node_id, block=f"c-{c['id']}.pass", line_type="Check success" + (" (ends conversation)" if pass_b.get("ends") else ""),
                           lines=pass_b.get("lines", []), when=c.get("when"), extra_cond=["the Aspect check passes"], effects=eff_pass, reached=reached, file=file, path=path + "/pass", ref=cid)
        if fail_b:
            self.add_lines(conv=conv, tpl=tpl, speaker=sp_key, speaker_name=sp_name, node=node_id, block=f"c-{c['id']}.fail", line_type="Check failure",
                           lines=fail_b.get("lines", []), when=c.get("when"), extra_cond=["the Aspect check fails"], effects=eff_fail, reached=reached, file=file, path=path + "/fail", ref=cid)
        if ck:
            blocked = c.get("blocked")
            self.n += 1
            self.lines.append({"id": f"{cid}.blocked", "n": self.n, "conv": conv, "tpl": tpl, "speaker_key": sp_key, "speaker": sp_name, "node": node_id, "block": f"c-{c['id']}.blocked",
                               "line_type": "Check repeat (engine default)", "text": "You have nothing new to add." if not blocked else blocked["lines"][0],
                               "cond": "the check failed before and nothing has changed since (the choice is normally greyed out; this line is the engine's fallback if it is sent anyway)",
                               "cond_raw": "", "effects": "", "reached": reached, "order": None, "notes": "Engine default text (graph.run_block); the data does not define a ‘blocked’ branch",
                               "alt_of": "", "ref": cid, **self.src(file, path + "/(engine default)")})

    @staticmethod
    def _rel_req(w: dict[str, Any] | None) -> str:
        if not w or "relationship" not in w:
            return ""
        r = w["relationship"]
        return " and ".join([f"regard ≥ {r['gte']}" if "gte" in r else "", f"regard ≤ {r['lte']}" if "lte" in r else ""]).strip(" and")

    def _persona_req(self, tpl: str, w: dict[str, Any] | None) -> str:
        if not w:
            return ""
        parts = []
        if "persona" in w:
            parts += self.desc.persona(w["persona"])
        if "player_worldview" in w:
            parts.append("your strongest worldview is " + " or ".join(WORLDVIEWS.get(c, c) for c in w["player_worldview"]))
        return "; ".join(parts)

    def check_row(self, tpl: str, conv: str, sp_name: str, sp_key: str, cid: str, c: dict[str, Any], ck: dict[str, Any], path: str, file: Path, text: str) -> dict[str, Any]:
        aspect = ck["aspect"]
        th = ck.get("threshold", "demanding")
        need = THRESHOLDS[th] if isinstance(th, str) else int(th)
        start = int(START_ASPECTS[aspect])
        start_rel = START_RELATIONSHIP.get((tpl, sp_key), 0)
        b = band(start_rel)
        guaranteed, optional = 0, 0
        ev_rows = []
        own_req = set((c.get("when") or {}).get("requires", []))
        own_lessons = set((c.get("when") or {}).get("lessons", []))
        for e in ck.get("evidence", []):
            ew = e.get("when") or {}
            self.record_when(tpl, ew, "evidence of " + cid)
            sure = set(ew.get("requires", [])) <= own_req and set(ew.get("lessons", [])) <= own_lessons and not (ew.get("fact") or ew.get("facts") or ew.get("knows") or ew.get("persona") or ew.get("relationship"))
            sure = sure and (bool(ew.get("requires")) or bool(ew.get("lessons")))
            ev_rows.append({"id": e.get("id", ""), "mod": int(e.get("mod", 1)), "when": self.desc.when_text(tpl, ew), "guaranteed_when_offered": sure})
            if sure:
                guaranteed += int(e.get("mod", 1))
            else:
                optional += int(e.get("mod", 1))
        guaranteed = min(2, guaranteed)
        best_ev = min(2, guaranteed + optional)
        fresh_total = start + guaranteed + b
        best_total = start + best_ev + b
        return {"id": f"CK.{cid}", "choice": cid, "conv": conv, "tpl": tpl, "speaker": sp_name, "text": text, "aspect": aspect_label(aspect), "threshold_name": th if isinstance(th, str) else "custom",
                "threshold": need, "start_score": start, "relationship_start": start_rel, "relationship_band": b, "evidence": ev_rows, "evidence_guaranteed": guaranteed,
                "evidence_best": best_ev, "total_fresh": fresh_total, "total_best": best_total,
                "fresh_result": "passes" if fresh_total >= need else ("can pass only with extra evidence" if best_total >= need else "cannot pass until the Aspect is raised or regard improves"),
                "pass_lines": " / ".join(self.line_items_text((c.get("pass") or {}).get("lines", []))), "fail_lines": " / ".join(self.line_items_text((c.get("fail") or {}).get("lines", []))),
                "pass_effects": "; ".join(self.desc.effects(tpl, c.get("pass") or {})), "fail_effects": "; ".join(self.desc.effects(tpl, c.get("fail") or {})),
                "has_fail_branch": bool(c.get("fail")), **self.src(file, path + "/check")}

    @staticmethod
    def line_items_text(lines: list[Any]) -> list[str]:
        return [l["text"] if isinstance(l, dict) else str(l) for l in lines]

    # ------------------------------------------------------------------ everyday topics and the aftermath
    def walk_topic(self, conv: str, tpl: str, speaker_name: str, speaker_key: str, t: dict[str, Any], file: Path, path: str, prefix: str, group: str, line_type: str) -> None:
        tid = f"{prefix}.t-{t['id']}"
        w = t.get("when")
        self.record_when("occupation", w, tid)
        self.record_block("occupation", t, tid)
        ck = t.get("check")
        conds = self.desc.when("occupation", w)
        if t.get("priority"):
            conds.append("priority topic: listed before the rotating selection")
        if t.get("once"):
            conds.append("marked ‘once’ in the data, but the runtime does not enforce it for topics (see defects)")
        conds_text = "; ".join(conds) if conds else "Offered whenever the person is talked to (subject to the three-topic rotation)"
        eff = self.desc.effects("occupation", t)
        pass_b, fail_b = t.get("pass"), t.get("fail")
        self.choices.append({"id": tid, "conv": conv, "tpl": tpl, "speaker": speaker_name, "speaker_key": speaker_key, "node": group, "choice_id": t["id"], "kind": "Topic (everyday question)",
                             "text": (f"[{aspect_label(ck['aspect'])}] " if ck else "") + t["text"], "raw_text": t["text"], "cond": conds_text, "aspect": aspect_label(ck["aspect"]) if ck else "",
                             "threshold": th_label(ck.get("threshold", "demanding")) if ck else "", "evidence": "; ".join(f"+{e.get('mod', 1)}: {self.desc.when_text('occupation', e.get('when'))}" for e in ck.get("evidence", [])) if ck else "",
                             "relationship_req": self._rel_req(w), "persona_req": self._persona_req("occupation", w),
                             "success": "Check passed: the answer is given, conversation continues" if ck else "The answer is given; conversation continues",
                             "failure": "Check failed: conversation continues; greyed out until something changes" if ck else "", "other": "", "effects": "; ".join(eff),
                             "pass_effects": "; ".join(self.desc.effects("occupation", pass_b)) if pass_b else "", "fail_effects": "; ".join(self.desc.effects("occupation", fail_b)) if fail_b else "",
                             "ends": "No", "once": "Yes" if t.get("once") else "", "goto": "", "order": None, **self.src(file, path)})
        if ck:
            self.checks.append(self.check_row("occupation", conv, speaker_name, "any", tid, {"when": w, "pass": pass_b, "fail": fail_b}, ck, path, file, t["text"]))
        if t.get("lines"):
            self.add_lines(conv=conv, tpl=tpl, speaker=speaker_key, speaker_name=speaker_name, node=group, block=f"t-{t['id']}", line_type=line_type, lines=t["lines"], when=w, extra_cond=[],
                           effects=eff, reached=f"Topic {tid}", file=file, path=path, ref=tid)
        if pass_b:
            self.add_lines(conv=conv, tpl=tpl, speaker=speaker_key, speaker_name=speaker_name, node=group, block=f"t-{t['id']}.pass", line_type="Check success", lines=pass_b.get("lines", []), when=w,
                           extra_cond=["the Aspect check passes"], effects=self.desc.effects("occupation", pass_b), reached=f"Topic {tid}", file=file, path=path + "/pass", ref=tid)
        if fail_b:
            self.add_lines(conv=conv, tpl=tpl, speaker=speaker_key, speaker_name=speaker_name, node=group, block=f"t-{t['id']}.fail", line_type="Check failure", lines=fail_b.get("lines", []), when=w,
                           extra_cond=["the Aspect check fails"], effects=self.desc.effects("occupation", fail_b), reached=f"Topic {tid}", file=file, path=path + "/fail", ref=tid)
        if t.get("responses"):
            self.walk_responses(conv, tpl, speaker_name, speaker_key, t["responses"], file, path + "/responses", f"{tid}.r", tid, "occupation")

    def walk_responses(self, conv: str, tpl: str, speaker_name: str, speaker_key: str, responses: list[dict[str, Any]], file: Path, path: str, prefix: str, parent: str, ctxtpl: str,
                       scene_ctx: bool = False) -> None:
        """Belief replies: the apprentice answers with a worldview; the speaker reacts according to their own persona (agree, neutral, disagree)."""
        for ri, r in enumerate(responses):
            rid = f"{prefix}-{r['id']}"
            self.record_when(ctxtpl, r.get("when"), rid)
            self.record_block(ctxtpl, r, rid)
            wv = r.get("worldview")
            ck = r.get("check")
            conds = self.desc.when(ctxtpl, r.get("when"))
            conds.append("only one answer per topic per person (once answered, the other replies disappear)")
            self.choices.append({"id": rid, "conv": conv, "tpl": tpl, "speaker": "You (reply to " + speaker_name + ")", "speaker_key": speaker_key, "node": parent, "choice_id": r["id"],
                                 "kind": "Belief reply" if wv else "Reply", "text": (f"[{aspect_label(ck['aspect'])}] " if ck else "") + r["text"], "raw_text": r["text"],
                                 "cond": "; ".join(conds), "aspect": aspect_label(ck["aspect"]) if ck else "", "threshold": th_label(ck.get("threshold", "demanding")) if ck else "",
                                 "evidence": "; ".join(f"+{e.get('mod', 1)}: {self.desc.when_text(ctxtpl, e.get('when'))}" for e in ck.get("evidence", [])) if ck else "",
                                 "relationship_req": self._rel_req(r.get("when")), "persona_req": self._persona_req(ctxtpl, r.get("when")),
                                 "success": "The speaker reacts (agree / neutral / disagree, by their own worldview); conversation continues",
                                 "failure": "", "other": "", "effects": ("Ideology expressed: " + WORLDVIEWS[wv] + " — your worldview scores shift by that view's table row (once per answer); the speaker's regard changes +4 (agrees), 0 (neutral) or −3 (disagrees)") if wv else "; ".join(self.desc.effects(ctxtpl, r)),
                                 "pass_effects": "; ".join(self.desc.effects(ctxtpl, r.get("pass") or {})) if r.get("pass") else "", "fail_effects": "; ".join(self.desc.effects(ctxtpl, r.get("fail") or {})) if r.get("fail") else "",
                                 "ends": "No", "once": "", "goto": "", "ideology": WORLDVIEWS.get(wv, "") if wv else "", "order": ri + 1, **self.src(file, f"{path}/{ri}")})
            if ck:
                self.checks.append(self.check_row(ctxtpl, conv, speaker_name, speaker_key, rid, {"when": r.get("when"), "pass": r.get("pass"), "fail": r.get("fail")}, ck, f"{path}/{ri}", file, r["text"]))
            if r.get("lines"):
                self.add_lines(conv=conv, tpl=tpl, speaker=speaker_key, speaker_name="You", node=parent, block=f"{prefix}-{r['id']}.say", line_type="Your words", lines=r["lines"], when=r.get("when"),
                               extra_cond=[], effects=[], reached=f"Reply {rid}", file=file, path=f"{path}/{ri}", ref=rid)
            for branch in ("pass", "fail"):
                if r.get(branch):
                    self.add_lines(conv=conv, tpl=tpl, speaker=speaker_key, speaker_name="Narration", node=parent, block=f"{prefix}-{r['id']}.{branch}",
                                   line_type="Check success" if branch == "pass" else "Check failure", lines=r[branch].get("lines", []), when=r.get("when"),
                                   extra_cond=[f"the Aspect check {'passes' if branch == 'pass' else 'fails'}"], effects=self.desc.effects(ctxtpl, r[branch]), reached=f"Reply {rid}", file=file,
                                   path=f"{path}/{ri}/{branch}", ref=rid)
            for key, label in (("agree", "speaker agrees with the view"), ("neutral", "speaker is neutral to the view"), ("disagree", "speaker disagrees with the view"), ("default", "default reply")):
                ls = (r.get("reply") or {}).get(key)
                if ls:
                    cond = [f"you chose this reply and {label}" + (f" ({WORLDVIEWS[wv]} reply; the speaker's reaction depends on their own main worldview — see ‘Ideology Reactions’)" if wv else "")]
                    self.add_lines(conv=conv, tpl=tpl, speaker=speaker_key, speaker_name=speaker_name, node=parent, block=f"{prefix}-{r['id']}.reply-{key}", line_type="Reaction to your belief (" + key + ")",
                                   lines=ls, when=r.get("when"), extra_cond=cond, effects=[{"agree": "Speaker's regard for you +4", "neutral": "No regard change", "disagree": "Speaker's regard for you −3", "default": ""}[key]],
                                   reached=f"Reply {rid}", file=file, path=f"{path}/{ri}/reply/{key}", ref=rid)

    def walk_occupations(self) -> None:
        file = DIALOGUE / "occupations.json"
        d = load_json(file)
        conv = "CV-EVERYDAY"
        for role, entry in d["roles"].items():
            sp = entry["label"]
            for kind, pool in (("intro", entry["intro"]), ("hub", entry["hub"])):
                self.pools.append({"id": f"EVERYDAY.{role}.{kind}", "conv": conv, "where": f"{sp}: {kind} lines", "rule": ("Said the first time the wizard talks to this person (one is picked by a seeded draw: the same person always says the same one)" if kind == "intro"
                                                                                                                                  else "Said on later talks (one is picked by a seeded draw from the person and the number of times they have been spoken to)"), "variants": len(pool)})
                for i, txt in enumerate(pool, 1):
                    self.n += 1
                    lid = f"EVERYDAY.{role}.{kind}.{i}"
                    self.lines.append({"id": lid, "n": self.n, "conv": conv, "tpl": "occupations", "speaker_key": role, "speaker": sp, "node": kind, "block": kind,
                                       "line_type": "Introduction" if kind == "intro" else "Greeting / repeat", "text": txt,
                                       "cond": ("First conversation with this person" if kind == "intro" else "Second and later conversations with this person") + f"; one of {len(pool)} wordings chosen by a seeded draw",
                                       "cond_raw": "", "effects": "", "reached": "Automatic when the conversation opens", "order": i, "notes": "", "alt_of": "", **self.src(file, f"roles/{role}/{kind}/{i - 1}")})
            for ti, t in enumerate(entry["topics"]):
                self.walk_topic(conv, "occupations", sp, role, t, file, f"roles/{role}/topics/{ti}", f"EVERYDAY.{role}", "topics", "Answer to an everyday question")
        for ti, t in enumerate(d["shared_topics"]):
            self.walk_topic(conv, "occupations", "Any villager", "any", t, file, f"shared_topics/{ti}", "EVERYDAY.shared", "shared topics", "Answer to a shared question")
        self.n += 1
        self.lines.append({"id": "EVERYDAY.farewell", "n": self.n, "conv": conv, "tpl": "occupations", "speaker_key": "any", "speaker": "Any villager", "node": "farewell", "block": "farewell",
                           "line_type": "Response (ends conversation)", "text": d["farewell"], "cond": "You choose Goodbye", "cond_raw": "", "effects": "", "reached": "Choice ‘Goodbye’ (added to every ordinary conversation)",
                           "order": None, "notes": "", "alt_of": "", **self.src(file, "farewell")})

    def walk_aftermath(self) -> None:
        file = DIALOGUE / "aftermath.json"
        d = load_json(file)
        conv = "CV-AFTER"
        for i, r in enumerate(d["reactions"]):
            self.pools.append({"id": f"AFTER.react.{r['id']}", "conv": conv, "where": f"First reaction: {r['id']}", "rule": "The FIRST reaction in file order whose conditions hold is spoken, once per person, the first time they are talked to after the stranger is gone", "variants": 1})
            rid = f"AFTER.react.{r['id']}"
            self.record_when("occupation", r.get("when"), rid)
            self.add_lines(conv=conv, tpl="aftermath", speaker=r["id"], speaker_name=self.react_speaker(r), node="first reaction", block=f"react-{r['id']}",
                           line_type="First reaction to the attack", lines=r["lines"], when=r.get("when"),
                           extra_cond=[f"no earlier reaction in the file applied (reaction {i + 1} of {len(d['reactions'])}); spoken once per person"], effects=[], reached="Automatic: the person's first words after the stranger has gone",
                           file=file, path=f"reactions/{i}", order=i + 1)
        for ti, t in enumerate(d["topics"]):
            self.walk_topic(conv, "aftermath", "Any villager", "any", t, file, f"topics/{ti}", "AFTER", "aftermath topics", "Answer after the attack")

    @staticmethod
    def react_speaker(r: dict[str, Any]) -> str:
        role = (r.get("when") or {}).get("role")
        return ("/".join(role).capitalize() if role else "Any villager")

    # ------------------------------------------------------------------ the scenes
    def walk_scenes(self) -> None:
        file = DIALOGUE / "campaign_scenes.json"
        d = load_json(file)
        conv = "CV-STRANGER"
        speaker_names = {"narrator": "Narrator", "mentor": "Mentor", "attacker": "The stranger", "apprentice": "You"}
        for sid, sc in d["scenes"].items():
            for pi, page in enumerate(sc["pages"]):
                pid = f"p{pi + 1}"
                eff = []
                for e in page.get("effects", []):
                    eff.append(self.desc.effect("scene", e))
                    self.record_block("scene", {"effects": [e]}, f"STRANGER.{sid}.{pid}")
                ltype = "Scene page (narration)" if page.get("speaker") == "narrator" else "Scene page (spoken)"
                self.add_lines(conv=conv, tpl="campaign_scenes", speaker=page.get("speaker", "narrator"), speaker_name=speaker_names.get(page.get("speaker", "narrator"), page.get("speaker")),
                               node=f"{sid}", block=pid, line_type=ltype, lines=page["lines"], when=None, extra_cond=[f"scene ‘{sid}’, page {pi + 1} of {len(sc['pages'])}, shown after the previous page is acknowledged"
                                                                                                                 + (f"; focus: {page.get('focus')}" if page.get('focus') else "") + (f"; effect on screen: {page['fx']}" if page.get("fx") else "")],
                               effects=eff, reached="Player acknowledges the previous page" if pi else f"Scene {sid} starts", file=file, path=f"scenes/{sid}/pages/{pi}", order=pi + 1)
                resp = page.get("responses")
                if resp:
                    rs = d["response_sets"][resp[1:]] if isinstance(resp, str) else resp
                    self.walk_responses(conv, "campaign_scenes", speaker_names.get(page.get("speaker", "narrator"), "The stranger"), page.get("speaker", "attacker"), rs, file,
                                        f"response_sets/{resp[1:]}" if isinstance(resp, str) else f"scenes/{sid}/pages/{pi}/responses", f"STRANGER.{sid}.{pid}.{resp[1:] if isinstance(resp, str) else 'r'}",
                                        f"STRANGER.{sid}.{pid}", "scene", True)

    # ------------------------------------------------------------------ Mira and system text
    def walk_mira(self) -> None:
        file = DATA / "ai_wizards.json"
        d = load_json(file)
        conv = "CV-MIRA"
        used = self.mira_used_kinds()
        for key, w in d["wizards"].items():
            for kind, lines in w["lines"].items():
                for i, txt in enumerate(lines, 1):
                    self.n += 1
                    self.lines.append({"id": f"MIRA.{kind}.{i}", "n": self.n, "conv": conv, "tpl": "ai_wizards", "speaker_key": key, "speaker": w["name"], "node": kind, "block": kind,
                                       "line_type": "Companion line", "text": txt, "cond": MIRA_WHEN.get(kind, "(situation not documented)") + (" | NOT USED: nothing in net/ai_wizard.py ever says this kind" if kind not in used else ""),
                                       "cond_raw": "", "effects": MIRA_EFFECT.get(kind, ""), "reached": "Shown as a toast message (‘Mira: …’) to the human wizard", "order": i,
                                       "notes": "one wording is picked at random (seeded per AI wizard) from the lines of this situation" if len(lines) > 1 else "", "alt_of": "", **self.src(file, f"wizards/{key}/lines/{kind}/{i - 1}")})
            for k in ("start_relationship", "accept_if_relationship_at_least", "accept_after_challenges", "win_relationship", "loss_relationship", "killed_relationship", "resurrected_relationship"):
                self.pools.append({"id": f"MIRA.param.{k}", "conv": conv, "where": f"Mira parameter {k}", "rule": str(w[k]), "variants": 1})

    @staticmethod
    def mira_used_kinds() -> set[str]:
        src = (HYBRID / "wizard_rts" / "net" / "ai_wizard.py").read_text(encoding="utf-8")
        return set(re.findall(r'self\.say\([^,]+,\s*"([a-z_]+)"', src)) | set(re.findall(r'"(provoked)" if after', src)) | set(re.findall(r'"([a-z_]+)"\s*if accept else', src)) | {"decline", "accept"}

    def walk_python_text(self) -> None:
        """Dialogue-like strings written in Python: system lines, refusals, journal notes, Trial text. Each is recorded with module and line so it can be found again."""
        targets = [
            ("wizard_rts/narrative/conversation.py", "CV-SYSTEM"), ("wizard_rts/narrative/ops.py", "CV-SYSTEM"), ("wizard_rts/narrative/mother.py", "CV-MOTHER"),
            ("wizard_rts/narrative/campaign.py", "CV-SYSTEM"), ("wizard_rts/narrative/quests.py", "CV-SYSTEM"), ("wizard_rts/narrative/tutorial.py", "CV-SYSTEM"),
            ("wizard_rts/trial/run.py", "CV-TRIAL"), ("wizard_rts/trial/events.py", "CV-TRIAL"), ("wizard_rts/story.py", None),
        ]
        for relpath, conv in targets:
            file = HYBRID / relpath
            src = file.read_text(encoding="utf-8")
            tree = ast.parse(src)
            doc_ids = set()
            for n in ast.walk(tree):
                if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and n.body and isinstance(n.body[0], ast.Expr) \
                        and isinstance(getattr(n.body[0], "value", None), ast.Constant) and isinstance(n.body[0].value.value, str):
                    doc_ids.add(id(n.body[0].value))
            func_at: dict[int, str] = {}
            for n in ast.walk(tree):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for ch in ast.walk(n):
                        if hasattr(ch, "lineno"):
                            func_at.setdefault(ch.lineno, n.name)
            for n in ast.walk(tree):
                if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc_ids:
                    s = n.value
                    if len(s) >= 25 and " " in s and re.search(r"[A-Za-z]{4}", s) and not s.startswith(("wizard_rts", "slot names", "this machine", "where Wizard", "host the", "retire the", "archive the", "print HYBRID", "also write")) \
                            and "HYBRID" not in s:
                        self.python_rows.append({"file": relpath, "line": n.lineno, "function": func_at.get(n.lineno, "(module level)"), "text": s, "conv": conv or ("CV-LEGACY-MINE" if True else "")})
        self.python_rows.sort(key=lambda r: (r["file"], r["line"]))

    python_rows: list[dict[str, Any]]

    def walk_legacy_story(self) -> None:
        """The legacy story layer: the collapsed-gallery miner and the outbreak healer. Choices come from story._choices; lines from story._lines."""
        file = HYBRID / "wizard_rts" / "story.py"
        legacy = [
            ("CV-LEGACY-MINE", "Miner", "ask_cause", "What happened to the mine?", "Available until asked once.", "", "",
             "He points at the shaft mouth, choked with broken props and rubble. 'The seam is fine. We just cannot get to it.'", "You learn the cause; +1 evidence for later checks (max 2)"),
            ("CV-LEGACY-MINE", "Miner", "ask_gallery", "Is there another way in?", "Available after ‘What happened to the mine?’ and until asked once.", "", "",
             "'My grandfather's crew broke through into an old gallery behind the spoil heap. It runs round the fall. The stone there answers to a sigil, and something keeps the way.'", "You learn about the old gallery"),
            ("CV-LEGACY-MINE", "Miner", "accept_help", "I will go down the old gallery.", "Available after asking about the gallery and until the sigil is given.", "", "",
             "He presses a worn stone mark into your palm. 'Take it to the gallery mouth. Open the old way and we can work again.'", "You receive the sigil (inventory); quest accepted"),
            ("CV-LEGACY-MINE", "Miner", "persuade", "(Empathy) Tell me what the warden does.", "Available after you have the sigil, until persuaded.", "Empathy", "easy (2)",
             "PASS: He relents. 'The warden never hurries. Four colours in a row, six to choose from. Take your time, and it may give you two more tries.' | FAIL: He shrugs you off. 'You do not know what I know.'", "Pass: miner's regard +15; the warden duel gets extra casts"),
            ("CV-LEGACY-MINE", "Miner", "give_up", "I cannot help.", "Always available while the quest is open.", "", "",
             "He says nothing. The shortage stays.", "Quest fails with a consequence; miner's regard −20"),
            ("CV-LEGACY-OUTBREAK", "Healer", "accept_treat", "I will treat the region. Stand in it and hold still.", "Available while the quest is offered.", "", "",
             "'Stand anywhere in the region and send the word `treat`. It takes a few seconds, and you must not leave.'", "Quest accepted; treatment begins when the wizard uses Treat in the region"),
            ("CV-LEGACY-OUTBREAK", "Healer", "give_up", "I cannot help.", "Always available while the quest is open.", "", "",
             "(no spoken response; the quest fails with the outbreak staying)", "Quest fails; the outbreak stays"),
        ]
        for conv, who, cid, text, cond, aspect, th, resp, eff in legacy:
            self.choices.append({"id": f"LEGACY.{who.lower()}.c-{cid}", "conv": conv, "tpl": "story", "speaker": who, "speaker_key": who.lower(), "node": "hub", "choice_id": cid, "kind": "Choice (legacy runtime)",
                                 "text": text, "raw_text": text, "cond": cond, "aspect": aspect, "threshold": th, "evidence": "+1 per fact learned from the miner (max 2)" if aspect else "", "relationship_req": "", "persona_req": "",
                                 "success": "Conversation continues", "failure": "", "other": "", "effects": eff, "pass_effects": "", "fail_effects": "", "ends": "No", "once": "", "goto": "", "order": None,
                                 **self.src(file, "story.py:_choices/choose")})
            self.n += 1
            self.lines.append({"id": f"LEGACY.{who.lower()}.c-{cid}.1", "n": self.n, "conv": conv, "tpl": "story", "speaker_key": who.lower(), "speaker": who, "node": "hub", "block": f"c-{cid}",
                               "line_type": "Response", "text": resp, "cond": cond, "cond_raw": "", "effects": eff, "reached": f"Choice LEGACY.{who.lower()}.c-{cid}", "order": None,
                               "notes": "Written in Python (story.py), not in a data file", "alt_of": "", **self.src(file, "story.py:choose")})

    # ------------------------------------------------------------------ the Trial
    def walk_trial_zones(self) -> None:
        file = DATA / "trial" / "zones_wizard.json"
        from wizard_rts.trial import zones  # noqa: E402

        for zid in zones.ported():
            z = zones.zone(zid)
            for e in z["entities"]:
                text = e.get("text") or ""
                lines = e.get("lines") or []
                if not text and not lines and not e.get("intro"):
                    continue
                eid = e.get("id", "")
                kind = e.get("kind", "")
                base = f"TRIAL.{zid}.{eid or kind}"
                conds = []
                if e.get("requires_run_flag"):
                    conds.append(f"requires the Trial run flag ‘{e['requires_run_flag']}’")
                if e.get("requires_defeated"):
                    conds.append(f"requires ‘{e['requires_defeated']}’ to have been defeated")
                if e.get("choice_event"):
                    conds.append(f"opens the choice event ‘{e['choice_event']}’")
                if text:
                    self.n += 1
                    self.lines.append({"id": base + ".text", "n": self.n, "conv": "CV-TRIAL", "tpl": "trial", "speaker_key": kind, "speaker": f"{z['name']} — {kind}{(' ‘' + e['name'] + '’') if e.get('name') else ''}",
                                       "node": zid, "block": eid or kind, "line_type": "Zone text (sign / object / person)", "text": text, "cond": "; ".join(conds) or "Interact with it inside the zone", "cond_raw": "",
                                       "effects": ("Gives item: " + str(e["item"])) if e.get("item") else "", "reached": f"Interact with ‘{eid or kind}’ in zone {zid}", "order": None,
                                       "notes": "Trial zone text (legacy tables with the Wizard World overlay)", "alt_of": "", **self.src(file if (f"{zid}/{eid}" in zones.overlay().get("entities", {})) else DATA / "trial" / "legacy_zones.json", f"{zid}/{eid}")})
                for k, lt in enumerate(lines, 1):
                    self.n += 1
                    self.lines.append({"id": f"{base}.line{k}", "n": self.n, "conv": "CV-TRIAL", "tpl": "trial", "speaker_key": kind, "speaker": f"{z['name']} — {e.get('name') or kind}", "node": zid, "block": eid or kind,
                                       "line_type": "Zone person speaks", "text": lt, "cond": "; ".join(conds) or "Talk to them inside the zone", "cond_raw": "", "effects": "", "reached": f"Interact with ‘{eid}’",
                                       "order": k, "notes": "", "alt_of": "", **self.src(DATA / "trial" / "legacy_zones.json", f"{zid}/{eid}/lines")})
                for fl, variant in (e.get("text_run_flag") or {}).items():
                    self.n += 1
                    self.lines.append({"id": f"{base}.text.{fl}", "n": self.n, "conv": "CV-TRIAL", "tpl": "trial", "speaker_key": kind, "speaker": f"{z['name']} — {kind}", "node": zid, "block": eid,
                                       "line_type": "Zone text (variant)", "text": str(variant), "cond": f"the Trial run flag ‘{fl}’ is set (replaces the base text)", "cond_raw": "", "effects": "", "reached": f"Interact with ‘{eid}’",
                                       "order": None, "notes": "", "alt_of": base + ".text", **self.src(DATA / "trial" / "legacy_zones.json", f"{zid}/{eid}/text_run_flag/{fl}")})
                for fl, variant in (e.get("lines_run_flag") or {}).items():
                    for k, lt in enumerate(variant, 1):
                        self.n += 1
                        self.lines.append({"id": f"{base}.lines.{fl}.{k}", "n": self.n, "conv": "CV-TRIAL", "tpl": "trial", "speaker_key": kind, "speaker": f"{z['name']} — {e.get('name') or kind}", "node": zid,
                                           "block": eid, "line_type": "Zone person speaks (variant)", "text": lt, "cond": f"the Trial run flag ‘{fl}’ is set (replaces the base lines)", "cond_raw": "", "effects": "",
                                           "reached": f"Interact with ‘{eid}’", "order": k, "notes": "", "alt_of": base + ".line1", **self.src(DATA / "trial" / "legacy_zones.json", f"{zid}/{eid}/lines_run_flag/{fl}")})
                if e.get("intro"):
                    self.n += 1
                    self.lines.append({"id": base + ".intro", "n": self.n, "conv": "CV-TRIAL", "tpl": "trial", "speaker_key": kind, "speaker": f"{z['name']} — {e.get('name') or kind}", "node": zid, "block": eid,
                                       "line_type": "Duel introduction", "text": str(e["intro"]), "cond": "Begin the duel with this creature or person", "cond_raw": "", "effects": "A lethal Ward duel starts", "reached": f"Interact with ‘{eid}’",
                                       "order": None, "notes": "", "alt_of": "", **self.src(DATA / "trial" / "legacy_zones.json", f"{zid}/{eid}/intro")})
            for xi, e in enumerate(z["entities"]):
                if e.get("travel_text"):
                    self.n += 1
                    self.lines.append({"id": f"TRIAL.{zid}.exit{xi}.{e.get('to_area', '')}.travel", "n": self.n, "conv": "CV-TRIAL", "tpl": "trial", "speaker_key": "exit", "speaker": f"{z['name']} — exit", "node": zid,
                                       "block": "exit", "line_type": "Travel text", "text": e["travel_text"], "cond": f"Walk through the exit to {e.get('to_area', '')}", "cond_raw": "", "effects": "", "reached": "Walking through an exit",
                                       "order": None, "notes": "", "alt_of": "", **self.src(DATA / "trial" / "legacy_zones.json", f"{zid}/exit/{e.get('to_area', '')}")})

    def run_all(self) -> dict[str, Any]:
        self.python_rows = []
        for tpl in TEMPLATE_CONV:
            self.walk_template(tpl, DIALOGUE / f"{tpl}.json")
        # the opening narration
        tut = load_json(DIALOGUE / "tutorial.json")
        for i, p in enumerate(tut["opening"], 1):
            self.n += 1
            self.lines.append({"id": f"OPEN.{i}", "n": self.n, "conv": "CV-OPEN", "tpl": "tutorial", "speaker_key": "narrator", "speaker": "Narrator", "node": "opening", "block": "opening",
                               "line_type": "Narration", "text": p, "cond": "Shown once at the start of a new campaign world; placeholders {settlement} and {mentor} are filled in", "cond_raw": "", "effects": "",
                               "reached": "Automatic at the start", "order": i, "notes": "", "alt_of": "", **self.src(DIALOGUE / "tutorial.json", f"opening/{i - 1}")})
        self.walk_scenes()
        self.walk_occupations()
        self.walk_aftermath()
        self.walk_mira()
        self.walk_legacy_story()
        self.walk_trial_zones()
        self.walk_python_text()
        return self.collect()

    def assign_status(self) -> None:
        """Say, in plain words, whether each line and choice can be reached in the game as it is today."""
        fresh = {c["id"]: c for c in self.checks}
        for l in self.lines:
            st = "Playable"
            ref = l.get("ref", "")
            ck = fresh.get("CK." + ref) if ref else None
            if "NOT USED" in l["cond"]:
                st = "Never spoken (nothing in the code uses this line)"
            elif l["line_type"].startswith("Check repeat"):
                st = "Engine fallback (the button is greyed out first, so this is not normally seen)"
            elif l["line_type"].startswith("Check failure") and ck and ck["fresh_result"] == "passes":
                st = "Exists, but a normal apprentice cannot reach it (the check passes for everyone)"
            elif l["conv"] == "CV-STRANGER" and l["node"] == "confrontation_alone":
                st = "Multiplayer only (a wizard arriving during the confrontation); not reachable in single player"
            elif l["conv"].startswith("CV-LEGACY"):
                st = "Reachable only if the simulation collapses a mine / starts an outbreak"
            elif l["conv"] == "CV-PATROL" and l["speaker_key"] == "guard":
                st = "Playable if a guard is cast (the guard role is optional)"
            elif l["conv"] in ("CV-FOREST", "CV-GRANITE", "CV-PATROL"):
                st = "Playable once the quest is cast (needs the right villagers in the settlement)"
            elif l["conv"] == "CV-MOTHER" and "grounded" in l["cond"] and "at least 1" in l["cond"]:
                st = "Playable after a wizard kills a friend inside the village"
            l["status"] = st
        for c in self.choices:
            st = "Playable"
            ck = fresh.get("CK." + c["id"])
            if c["conv"].startswith("CV-LEGACY"):
                st = "Reachable only if the simulation collapses a mine / starts an outbreak"
            elif c["conv"] == "CV-STRANGER" and "confrontation_alone" in c["id"]:
                st = "Multiplayer only (late arrival)"
            elif c["conv"] in ("CV-FOREST", "CV-GRANITE", "CV-PATROL"):
                st = "Playable once the quest is cast"
            elif ck and ck["fresh_result"] == "passes":
                st = "Playable (the check always passes for a normal apprentice)"
            elif ck:
                st = "Playable (the check can fail)"
            c["status"] = st

    def collect(self) -> dict[str, Any]:
        self.assign_status()
        return {"collections": COLLECTIONS, "lines": self.lines, "choices": self.choices, "checks": self.checks, "nodes": self.nodes, "pools": self.pools, "python_text": self.python_rows,
                "setters": {f"{k[0]}::{k[1]}": v for k, v in self.setters.items()}, "readers": {f"{k[0]}::{k[1]}": v for k, v in self.readers.items()},
                "fact_setters": self.fact_setters, "fact_readers": self.fact_readers}


MIRA_WHEN = {
    "greet": "Mira comes within four tiles of the human wizard for the first time", "decline": "The human challenges Mira and has not yet asked twice before (she declines the first two requests)",
    "accept": "The human challenges Mira, asked at least twice before, and her regard for them is high enough", "provoked": "As ‘accept’, but said when she has been asked repeatedly (provoked) and her character defines provoked lines",
    "win": "Mira wins a duel against the human (and they live)", "lose": "Mira loses a duel against the human", "draw": "A duel ends in a draw", "killed_you": "Mira wins a lethal duel against the human and the human dies",
    "resurrecting": "Mira starts channelling to bring a dead human wizard back", "resurrected_you": "Mira finishes bringing the human wizard back",
    "i_died": "The human brings Mira back from the dead", "you_died_again": "(intended: the human dies again)", "rat_won": "Mira breaks a rat in a Ward duel", "rat_lost": "Mira loses to a rat",
    "trial_in": "Mira follows the human into the Trial gate", "trial_zone": "Mira enters a new Trial zone (half the time)", "trial_out": "Mira walks out of the Trial after the human", "trial_grounded": "The human is outside and Mira cannot enter because she is grounded by her mother",
}
MIRA_EFFECT = {"win": "Mira's regard for the human +3", "lose": "Mira's regard for the human −4", "killed_you": "Mira walks to the body to resurrect it", "i_died": "Mira's regard for the human +8", "decline": "Counts as a provocation",
               "accept": "The duel starts (Mira thinks 2.5–6 seconds between casts)"}


def th_label(name: str | int) -> str:
    if isinstance(name, int):
        return str(name)
    return f"{name} ({THRESHOLDS[name]})"


def main() -> None:
    ex = Extractor()
    inv = ex.run_all()
    inv["config"] = {"start_aspects": START_ASPECTS, "thresholds": THRESHOLDS, "mentor_relationship": CONFIG["campaign"]["mentor_relationship"], "mother_relationship": CONFIG["mortality"]["mother_relationship"],
                     "config_json": CONFIG}
    (GEN / "inventory.json").write_text(json.dumps(inv, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"lines={len(inv['lines'])} choices={len(inv['choices'])} checks={len(inv['checks'])} nodes={len(inv['nodes'])} python_text={len(inv['python_text'])} -> {rel(GEN / 'inventory.json')}")


if __name__ == "__main__":
    main()
