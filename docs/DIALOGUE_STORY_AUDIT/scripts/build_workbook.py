"""Builds the Excel workbook from generated/inventory.json, runtime_probes.json, static_findings.json and curated.py.

Run:  python docs/DIALOGUE_STORY_AUDIT/scripts/build_workbook.py
Writes: docs/DIALOGUE_STORY_AUDIT/Wizard_World_Dialogue_Workbook.xlsx

Every row keeps a stable identifier and the source file and path it was read from. Nothing is hand-copied: re-running the extractor and this script
reproduces the workbook (the hand-written sheets come from curated.py).
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import curated
from common import DATA, FACT_DOC, FLAG_MEANING, LEARNED_FACT_DOC, OUT, WORLDVIEWS, load_json, rel
from extract_inventory import CONV_SHORT

GEN = OUT / "generated"
XLSX = OUT / "Wizard_World_Dialogue_Workbook.xlsx"

NAVY = "1F3A5F"
HEAD = PatternFill("solid", fgColor=NAVY)
BAND = PatternFill("solid", fgColor="EEF3F9")
SOFT = PatternFill("solid", fgColor="F7F7F7")
WARN = PatternFill("solid", fgColor="FDECEA")
GOOD = PatternFill("solid", fgColor="E8F5E9")
AMBER = PatternFill("solid", fgColor="FFF4D6")
THIN = Side(style="thin", color="D0D7E2")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
LINK = Font(name="Calibri", size=10, color="0563C1", underline="single")
BASE = Font(name="Calibri", size=10)
BOLD = Font(name="Calibri", size=10, bold=True)

SHEETS = {
    "README": "README", "A": "A_Index", "B": "B_Dialogue", "C": "C_Choices", "D": "D_Outcomes", "E": "E_Characters", "F": "F_Rules", "G": "G_Checks", "H": "H_Flags_Facts",
    "I": "I_Selection", "J": "J_Ideology", "K": "K_Trial", "L": "L_System_Text", "M": "M_Runtime_Checks", "N": "N_Defects", "O": "O_Legacy",
}
DIAGRAMS = {"CV-MENTOR": "diagrams/01_mentor_lessons.md", "CV-FOREST": "diagrams/02_forest_dispute.md", "CV-GRANITE": "diagrams/03_missing_granite.md", "CV-PATROL": "diagrams/04_patrol.md",
            "CV-WAREHOUSE": "diagrams/05_warehouse_keeper_rats.md", "CV-MOTHER": "diagrams/06_mother_death_resurrection.md", "CV-STRANGER": "diagrams/07_stranger.md",
            "CV-AFTER": "diagrams/08_aftermath_and_everyday.md", "CV-EVERYDAY": "diagrams/08_aftermath_and_everyday.md", "CV-TRIALGATE": "diagrams/09_trial_gate_and_events.md",
            "CV-TRIAL": "diagrams/09_trial_gate_and_events.md", "CV-MIRA": "diagrams/10_mira.md", "CV-LEGACY-MINE": "diagrams/11_legacy_story_layer.md", "CV-LEGACY-OUTBREAK": "diagrams/11_legacy_story_layer.md"}


def link(sheet: str, row: int, col: str = "A") -> str:
    return f"#'{sheet}'!{col}{row}"


class Book:
    def __init__(self) -> None:
        self.wb = Workbook()
        self.wb.remove(self.wb.active)

    def sheet(self, name: str, headers: list[str], widths: list[int], freeze: str = "B2", tab: str | None = None, filt: bool = True):
        ws = self.wb.create_sheet(name)
        ws.append(headers)
        for i, h in enumerate(headers, 1):
            c = ws.cell(row=1, column=i)
            c.fill, c.font, c.border = HEAD, Font(name="Calibri", size=10, bold=True, color="FFFFFF"), BORDER
            c.alignment = Alignment(wrap_text=True, vertical="center")
            ws.column_dimensions[get_column_letter(i)].width = widths[i - 1]
        ws.row_dimensions[1].height = 32
        ws.freeze_panes = freeze
        if tab:
            ws.sheet_properties.tabColor = tab
        ws._filter = filt  # noqa: SLF001
        return ws

    @staticmethod
    def add(ws, values: list[Any], fill=None, bold_first: bool = False) -> int:
        ws.append(values)
        r = ws.max_row
        for i in range(1, len(values) + 1):
            c = ws.cell(row=r, column=i)
            c.font = BOLD if (bold_first and i == 1) else BASE
            c.alignment = Alignment(wrap_text=True, vertical="top")
            c.border = BORDER
            if fill is not None:
                c.fill = fill
        return r

    @staticmethod
    def put_link(ws, row: int, col: int, target: str) -> None:
        c = ws.cell(row=row, column=col)
        c.hyperlink = target
        c.font = LINK

    @staticmethod
    def finish(ws, widths: list[int] | None = None) -> None:
        if getattr(ws, "_filter", True) and ws.max_row > 1:
            ws.auto_filter.ref = f"A1:{get_column_letter(ws.max_column)}{ws.max_row}"


def short_probe(pid: str, probes: dict[str, dict[str, Any]]) -> str:
    return curated.PROBE_SUMMARY.get(pid, "")


def main() -> None:
    inv = load_json(GEN / "inventory.json")
    probes = {p["id"]: p for p in load_json(GEN / "runtime_probes.json")}
    static = load_json(GEN / "static_findings.json")
    colls = {c["id"]: c for c in inv["collections"]}
    order = [c["id"] for c in inv["collections"]]
    cidx = {cid: i for i, cid in enumerate(order)}
    lines = sorted(inv["lines"], key=lambda l: (cidx.get(l["conv"], 99), l["n"]))
    choices = sorted(inv["choices"], key=lambda c: (cidx.get(c["conv"], 99), inv["choices"].index(c)))
    b = Book()

    # ---------------------------------------------------------------- B Dialogue (built first: other sheets link into it)
    wsB = b.sheet(SHEETS["B"], ["Line ID", "Collection", "Collection name", "Speaker", "Node / scene", "Entry", "Line type", "Dialogue text (exact)", "Conditions for this line to appear (plain English)",
                                "Effects when heard", "Reached from (choice / topic)", "Status today", "Source file", "Source path", "Raw condition (data)"],
                  [34, 12, 26, 20, 18, 22, 24, 70, 60, 42, 30, 34, 38, 34, 30], freeze="E2", tab="2E7D32")
    row_B: dict[str, int] = {}
    first_B_conv: dict[str, int] = {}
    first_B_ref: dict[str, int] = {}
    first_B_node: dict[tuple[str, str, str], int] = {}
    first_B_prefix: dict[str, int] = {}
    for l in lines:
        fill = BAND if cidx.get(l["conv"], 0) % 2 == 0 else None
        r = b.add(wsB, [l["id"], l["conv"], colls[l["conv"]]["title"], l["speaker"], l["node"], l["block"], l["line_type"], l["text"], l["cond"], l["effects"], l.get("ref", "") or l["reached"],
                        l.get("status", "Playable"), l["source_file"], l["source_path"], l["cond_raw"]], fill=fill, bold_first=True)
        row_B[l["id"]] = r
        first_B_conv.setdefault(l["conv"], r)
        if l.get("ref"):
            first_B_ref.setdefault(l["ref"], r)
        first_B_node.setdefault((l["tpl"], l["speaker_key"], l["node"]), r)
        # block prefix (id minus the trailing line number) for outcome links
        prefix = ".".join(l["id"].split(".")[:-1])
        first_B_prefix.setdefault(prefix, r)
        for k in range(1, len(prefix.split("."))):
            first_B_prefix.setdefault(".".join(prefix.split(".")[:k]) if k >= 3 else prefix, r)
        if "Never spoken" in l.get("status", "") or "cannot reach" in l.get("status", ""):
            wsB.cell(row=r, column=12).fill = AMBER
    b.finish(wsB)

    # ---------------------------------------------------------------- C Choices
    wsC = b.sheet(SHEETS["C"], ["Choice ID", "Collection", "Speaker", "Node", "Kind", "What the player sees (response text)", "Conditions to see it", "Skill (Aspect)", "Difficulty", "Evidence bonuses",
                                "Regard needed", "Personality / ideology needed", "If it succeeds / goes ahead", "If a skill check fails", "Other / broken destinations", "Effects", "Extra effects on success",
                                "Extra effects on failure", "Ends the conversation?", "Single use?", "Ideology expressed", "Status today", "Goes to node (link)", "Source file", "Source path"],
                  [38, 12, 18, 14, 18, 56, 50, 12, 14, 40, 18, 34, 38, 40, 22, 52, 36, 36, 16, 10, 18, 30, 16, 34, 30], freeze="F2", tab="1565C0")
    row_C: dict[str, int] = {}
    for c in choices:
        fill = BAND if cidx.get(c["conv"], 0) % 2 == 0 else None
        r = b.add(wsC, [c["id"], c["conv"], c["speaker"], c["node"], c["kind"], c["text"], c["cond"], c["aspect"], c["threshold"], c["evidence"], c["relationship_req"], c["persona_req"],
                        c["success"], c["failure"], c["other"], c["effects"], c["pass_effects"], c["fail_effects"], c["ends"], c["once"], c.get("ideology", ""), c.get("status", ""),
                        c["goto"] if c["goto"] not in ("", "hub") else "", c["source_file"], c["source_path"]], fill=fill, bold_first=True)
        row_C[c["id"]] = r
        if c["id"] in first_B_ref:
            b.put_link(wsC, r, 1, link(SHEETS["B"], first_B_ref[c["id"]]))
        if c["goto"] not in ("", "hub"):
            tgt = first_B_node.get((c["tpl"], c["speaker_key"], c["goto"]))
            if tgt:
                b.put_link(wsC, r, 23, link(SHEETS["B"], tgt))
    b.finish(wsC)
    # back-links from B to C
    for l in lines:
        if l.get("ref") and l["ref"] in row_C:
            b.put_link(wsB, row_B[l["id"]], 11, link(SHEETS["C"], row_C[l["ref"]]))

    # ---------------------------------------------------------------- G Checks
    wsG = b.sheet(SHEETS["G"], ["Check ID", "Collection", "Speaker", "The choice", "Aspect tested", "Difficulty", "Needed total", "Aspect score at the start", "Speaker's regard at the start", "Regard bonus",
                                "Evidence that can add", "Evidence you always have when offered", "Best evidence possible", "Total for a fresh apprentice", "Best total possible", "Verdict for a fresh apprentice",
                                "Success text (exact)", "Failure text (exact)", "Success effects", "Failure effects"],
                  [38, 12, 18, 52, 12, 14, 8, 10, 12, 8, 54, 12, 10, 10, 10, 30, 56, 44, 40, 36], freeze="E2", tab="C62828")
    row_G: dict[str, int] = {}
    for ck in inv["checks"]:
        ev = "; ".join(f"+{e['mod']} if {e['when']}" + (" (always true when offered)" if e["guaranteed_when_offered"] else "") for e in ck["evidence"]) or "none"
        r = b.add(wsG, [ck["id"], ck["conv"], ck["speaker"], ck["text"], ck["aspect"], ck["threshold_name"], ck["threshold"], ck["start_score"], ck["relationship_start"], ck["relationship_band"],
                        ev, ck["evidence_guaranteed"], ck["evidence_best"], ck["total_fresh"], ck["total_best"], ck["fresh_result"], ck["pass_lines"], ck["fail_lines"], ck["pass_effects"], ck["fail_effects"]],
                  fill=(GOOD if ck["fresh_result"] == "passes" else AMBER), bold_first=True)
        row_G[ck["id"]] = r
        if ck["choice"] in row_C:
            b.put_link(wsG, r, 1, link(SHEETS["C"], row_C[ck["choice"]]))
    b.finish(wsG)

    # ---------------------------------------------------------------- A Index
    wsA = b.sheet(SHEETS["A"], ["Collection ID", "Story / conversation", "Kind", "Status today", "Where it happens", "How the player starts it", "Prerequisites", "Characters", "Summary", "Possible endings",
                                "Lines", "Choices", "Skill checks", "Diagram", "Source"], [14, 34, 22, 34, 32, 42, 44, 34, 60, 60, 8, 8, 8, 28, 32], freeze="C2", tab="F9A825")
    for cid in order:
        c = colls[cid]
        n_l = sum(1 for l in lines if l["conv"] == cid)
        n_c = sum(1 for x in choices if x["conv"] == cid)
        n_k = sum(1 for x in inv["checks"] if x["conv"] == cid)
        r = b.add(wsA, [cid, c["title"], c["kind"], c["status"], c["where"], c["how"], c["prereq"], c["characters"], c["summary"], curated.ENDINGS.get(cid, ""), n_l, n_c, n_k,
                        DIAGRAMS.get(cid, ""), c["file"]], bold_first=True, fill=(AMBER if c["status"].startswith("Partially") else None))
        if cid in first_B_conv:
            b.put_link(wsA, r, 1, link(SHEETS["B"], first_B_conv[cid]))
        if DIAGRAMS.get(cid):
            wsA.cell(row=r, column=14).hyperlink = DIAGRAMS[cid]
            wsA.cell(row=r, column=14).font = LINK
    b.finish(wsA)

    # ---------------------------------------------------------------- D Outcomes
    wsD = b.sheet(SHEETS["D"], ["Outcome ID", "Collection", "Outcome", "How you reach it", "Conditions", "What happens now", "Lasting consequences", "Dialogue (first link; all ids listed)", "Ends the conversation / story?",
                                "Runtime check", "Notes"], [16, 12, 38, 46, 30, 52, 56, 60, 14, 12, 40], freeze="D2", tab="6A1B9A")
    for o in curated.OUTCOMES:
        ids = [x for x in o["lines"].split(";") if x]
        r = b.add(wsD, [o["id"], o["conv"], o["name"], o["how"], o["when"], o["result"], o["lasting"], "; ".join(ids), o["ends"], o["probe"], o["notes"]], bold_first=True,
                  fill=(AMBER if "never" in o["name"].lower() or "unfinish" in o["name"].lower() else None))
        for pref in ids:
            tgt = first_B_prefix.get(pref)
            if tgt:
                b.put_link(wsD, r, 8, link(SHEETS["B"], tgt))
                break
    b.finish(wsD)

    # ---------------------------------------------------------------- E Characters
    wsE = b.sheet(SHEETS["E"], ["Character ID", "Who", "Kind", "Worldviews", "Traits", "Attitude to magic", "Starting regard for the apprentice", "Special dialogue conditions and notes", "Appears in"],
                  [14, 40, 30, 40, 26, 30, 22, 90, 28], freeze="C2", tab="00838F")
    for ch in curated.CHARACTERS:
        b.add(wsE, [ch["id"], ch["name"], ch["kind"], ch["worldviews"], ch["traits"], ch["magic"], ch["regard"], ch["special"], ch["where"]], bold_first=True,
              fill=(None if ch["kind"].startswith("Authored") else SOFT))
    # examples of generated villagers
    p33 = probes.get("P33", {}).get("observed", {})
    b.add(wsE, ["", "", "", "", "", "", "", "", ""])
    r = b.add(wsE, ["EXAMPLES", "Generated villagers in the seed-507 test world (one per trade)", "Name", "Main / second worldview", "Traits", "Attitude to magic", "Attitude to the mentor", "Worldview scores (M A R G S D C)", "Trade"], fill=AMBER, bold_first=True)
    for v in p33.get("one_per_trade", []) + p33.get("four_lumberjacks", []):
        sc = v.get("scores") or {}
        b.add(wsE, ["", "example", v["name"], f"{WORLDVIEWS.get(v['main'], v['main'])} / {WORLDVIEWS.get(v['second'], v['second'])}", ", ".join(v["traits"]), v["attitude_to_magic"], v["attitude_to_mentor"],
                    " ".join(str(sc.get(k, "")) for k in "MARGSDC") if sc else "", v.get("role", "lumberjack")])
    b.finish(wsE)

    # ---------------------------------------------------------------- F Rules
    wsF = b.sheet(SHEETS["F"], ["Section", "Term", "What it means (plain English)", "Where it lives in the game"], [18, 34, 120, 44], freeze="C2", tab="455A64")
    for rr in curated.RULES:
        b.add(wsF, [rr["section"], rr["term"], rr["meaning"], rr["where"]], bold_first=True)
    b.add(wsF, ["", "", "", ""])
    b.add(wsF, ["Glossary", "Kinds of condition a line or choice can have", "", ""], fill=AMBER, bold_first=True)
    from common import CONDITION_KINDS, EFFECT_KINDS

    for k, v in CONDITION_KINDS.items():
        b.add(wsF, ["Condition", k, v, "wizard_rts/narrative/graph.py holds()"])
    b.add(wsF, ["Glossary", "Kinds of effect", "", ""], fill=AMBER, bold_first=True)
    for k, v in EFFECT_KINDS.items():
        b.add(wsF, ["Effect", k, v, "wizard_rts/narrative/graph.py EFFECTS / campaign._SCENE_EFFECTS"])
    b.add(wsF, ["Glossary", "The seven worldviews and the table row added when you choose that reply", "", ""], fill=AMBER, bold_first=True)
    wv = load_json(DATA / "narrative" / "worldviews.json")["worldviews"]
    for w_ in wv:
        d = ", ".join(f"{k} {v:+d}" for k, v in w_["delta"].items() if v)
        b.add(wsF, ["Worldview", f"{w_['code']} — {w_['name']}", d, "data/narrative/worldviews.json"])
    b.finish(wsF)

    # ---------------------------------------------------------------- H Flags & facts
    wsH = b.sheet(SHEETS["H"], ["Kind", "Template", "Name", "Plain meaning", "Set by", "Read by (count)", "Read by (examples)", "Note"], [10, 16, 28, 62, 60, 10, 60, 40], freeze="D2", tab="795548")
    keys = sorted(set(inv["setters"]) | set(inv["readers"]))
    for k in keys:
        tpl, flag = k.split("::")
        meaning = FLAG_MEANING.get(k, "")
        if flag.startswith("done:"):
            meaning = f"you already took the single-use choice ‘{flag[5:]}’"
        setters = sorted(set(inv["setters"].get(k, [])))
        readers_ = sorted(set(inv["readers"].get(k, [])))
        note = ""
        if not setters:
            note = "Set by the engine (tutorial duel results), not by the dialogue data" if tpl == "tutorial" else "Never set"
        elif not readers_ and not flag.startswith("done:"):
            note = "Set but never read by any line"
        b.add(wsH, ["Flag", tpl, flag, meaning, "; ".join(setters[:6]), len(readers_), "; ".join(readers_[:4]), note], bold_first=False, fill=(AMBER if note.startswith("Set but") or note == "Never set" else None))
    allfacts = sorted(set(inv["fact_setters"]) | set(inv["fact_readers"]) | set(LEARNED_FACT_DOC))
    for f in allfacts:
        sset = sorted(set(inv["fact_setters"].get(f, [])))
        rd = sorted(set(inv["fact_readers"].get(f, [])))
        import re
        code_reads = []
        for p in (DATA.parent).rglob("*.py"):
            try:
                t = p.read_text(encoding="utf-8")
            except Exception:  # noqa: BLE001
                continue
            if re.search(r'knows_fact\([^,]+,\s*"%s"' % re.escape(f), t):
                code_reads.append(rel(p))
        note = "" if (rd or code_reads) else "Learned but nothing reads it"
        b.add(wsH, ["Learned fact", "", f, LEARNED_FACT_DOC.get(f, ""), "; ".join(sset[:4]) or "(trial/events.py)", len(rd) + len(code_reads), "; ".join(rd[:3] + code_reads[:2]), note],
              fill=(AMBER if note else None))
    for name, doc in sorted(FACT_DOC.items()):
        b.add(wsH, ["World fact", "", name, doc, "read live from the simulation or the behaviour ledger", "", "", ""], fill=SOFT)
    b.finish(wsH)

    # ---------------------------------------------------------------- I Selection
    wsI = b.sheet(SHEETS["I"], ["Where", "Order", "Entry", "Speaks when (plain English)", "Number of lines", "First line (exact)", "Selection rule"], [34, 7, 34, 90, 8, 80, 60], freeze="C2", tab="AD1457")
    bynode: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for l in lines:
        if l.get("order") and not l.get("ref") and ".alt" not in l["block"] and l["conv"] not in ("CV-STRANGER", "CV-EVERYDAY", "CV-OPEN", "CV-MIRA", "CV-TRIAL"):
            bynode[(l["conv"], l["speaker"], l["node"])].append(l)
    for (conv, spk, node), ls in bynode.items():
        blocks: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for l in ls:
            blocks[l["block"]].append(l)
        for bl, group in sorted(blocks.items(), key=lambda kv: kv[1][0]["order"]):
            g = group[0]
            rule = "The first entry in this list whose conditions hold is spoken; later entries are ignored" if conv != "CV-AFTER" else "First matching reaction, spoken once per person"
            if any(".alt" in x["block"] for x in lines if x["block"].startswith(bl + ".alt") and x["conv"] == conv):
                rule += "; alternate wordings rotate each time it is heard"
            r = b.add(wsI, [f"{colls[conv]['title']} — {spk} / {node}", g["order"], bl, g["cond"], len(group), g["text"], rule])
            b.put_link(wsI, r, 3, link(SHEETS["B"], row_B[g["id"]]))
    # reactions to the attack and pools
    for pl in inv["pools"]:
        if pl["id"].startswith("MIRA.param"):
            continue
        b.add(wsI, [pl["where"], "", pl["id"], pl["rule"], pl["variants"], "", "Seeded random draw (the same person always gives the same draw)" if "EVERYDAY" in pl["id"] else ""], fill=SOFT)
    b.add(wsI, ["Everyday topics (all trades)", "", "rotation", "Hidden topics first (conditions false); up to three ‘priority’ topics are always listed first; then three more from the rest, starting at position 2 × (times already spoken to) and wrapping around; a question already asked in this conversation is dropped; two topics with identical text show only the first.", "", "", "occupations.view"], fill=AMBER)
    b.add(wsI, ["Mira's lines", "", "random pick", "Each situation has one to four wordings; one is picked at random (seeded per AI wizard).", "", "", "net/ai_wizard.py say()"], fill=SOFT)
    b.finish(wsI)

    # ---------------------------------------------------------------- J Ideology
    wsJ = b.sheet(SHEETS["J"], ["Speaker's main worldview ↓ / your reply →", *[f"{c} {WORLDVIEWS[c]}" for c in "MARGSDC"], "Note"], [34, 14, 14, 14, 14, 14, 14, 14, 60], freeze="B2", tab="6D4C41")
    mat = probes.get("P32", {}).get("observed", {}).get("matrix_primary_by_reply", {})
    for p_ in "MARGSDC":
        row = [f"{p_} {WORLDVIEWS[p_]}"] + [mat.get(p_, {}).get(c_, "") for c_ in "MARGSDC"] + [""]
        r = b.add(wsJ, row, bold_first=True)
        for i, c_ in enumerate("MARGSDC", 2):
            v = mat.get(p_, {}).get(c_, "")
            wsJ.cell(row=r, column=i).fill = GOOD if v == "agree" else (WARN if v == "disagree" else SOFT)
    b.add(wsJ, [""] * 9)
    b.add(wsJ, ["Effect of the reaction", "agree: the speaker's regard for you +4", "neutral: no change", "disagree: the speaker's regard for you −3", "", "", "", "", "Each person answers one reply per topic."], fill=AMBER)
    b.add(wsJ, ["If the speaker's SECOND worldview equals your reply's view, one extra point is added:", "", "", "", "", "", "", "",
                "Upgrades: " + ", ".join(f"{k.replace('/', ' main, reply ')}: {v[0]} → {v[1]}" for k, v in probes.get("P32", {}).get("observed", {}).get("changed_when_second_worldview_equals_the_reply", {}).items())])
    b.add(wsJ, [""] * 9)
    b.add(wsJ, ["The stranger", "Main S, second C: S agree · M disagree · A neutral · R disagree · G neutral · D disagree · C neutral (his second view C adds 1: neutral rather than neutral)", "", "", "", "", "", "", "Verified by probe P22."])
    b.add(wsJ, ["The mentor", "Main D, second M: choosing D, M or R (+3 regard) or A, G (+1) or S (−3) in the creed question is a fixed table, not the reaction rule.", "", "", "", "", "", "", "tutorial.json creed node."])
    b.finish(wsJ)

    # ---------------------------------------------------------------- K Trial
    wsK = b.sheet(SHEETS["K"], ["Event", "Where in the Trial", "Situation (run state tested)", "Choice", "What the text says", "Condition added", "Run flags set", "Fight starts?", "Notes"],
                  [18, 30, 36, 18, 100, 16, 36, 22, 40], freeze="C2", tab="37474F")
    zmap: dict[str, str] = {}
    try:
        from wizard_rts.trial import zones

        for zid in zones.ported():
            for e in zones.zone(zid)["entities"]:
                if e.get("choice_event"):
                    zmap[e["choice_event"]] = f"{zones.zone(zid)['name']} ({zid}) — {e.get('id', '')}"
    except Exception:  # noqa: BLE001
        pass
    ev_tree = probes.get("P38", {}).get("observed", {}).get("events", {})
    for name, cases in ev_tree.items():
        for c in cases:
            setup = c.get("setup") or {}
            sit = "fresh run" if not setup else "; ".join(f"{k}: {v}" for k, v in setup.items())
            fight = ""
            if c.get("fight"):
                fight = f"Yes: {c['fight'][1]}"
            b.add(wsK, [name, zmap.get(name, ""), sit, c.get("choice") or "(opens the event)", c.get("text") or c.get("error", ""), ", ".join(c.get("conditions", [])), ", ".join(c.get("run_flags_added", [])), fight, ""],
                  bold_first=True)
    bestiary = load_json(DATA / "trial" / "legacy_bestiary.json")["opponents"]
    b.add(wsK, [""] * 9)
    b.add(wsK, ["BESTIARY", "Creatures and people you can duel", "", "", "", "", "", "", ""], fill=AMBER, bold_first=True)
    for bid, bo in bestiary.items():
        b.add(wsK, [bid, bo.get("kind", ""), f"Ward of {bo.get('ward_size')}, {bo.get('max_casts')} casts", bo.get("display_name", ""), bo.get("description", ""), "", "", "", ""], fill=SOFT)
    b.finish(wsK)

    # ---------------------------------------------------------------- L System text
    wsL = b.sheet(SHEETS["L"], ["Module", "Line", "Function", "Where it shows", "Text (exact)"], [34, 8, 26, 44, 110], freeze="B2", tab="546E7A")
    where_for = {"campaign.py": {"_kill_mentor": "Journal note", "on_duel_resolved": "Journal note", "_spare_others": "Journal note", "complete": "Journal note (the objective)", "welcome_back": "Journal note for a late or returning wizard",
                                 "scene_next": "Journal note", "objective": "Objective shown on the screen"},
                 "conversation.py": {"talk": "Stock reply when you cannot talk to someone"}, "mother.py": {"(module level)": "The mother's refusal when a grounded wizard steps away"},
                 "ops.py": {"resolve": "Reply when a lesson duel is abandoned"}, "quests.py": {"_substitute": "Journal note", "_interrupt": "Journal note", "objective": "Objective shown in the journal", "where_text": "Directions in the mentor's pointer"},
                 "tutorial.py": {"next_lesson_hint": "Hint shown on the screen", "objective": "Objective shown on the screen", "(module level)": "Lesson title"}}
    for pr in inv["python_text"]:
        fn = pr["file"].split("/")[-1]
        wh = where_for.get(fn, {}).get(pr["function"], "")
        if not wh:
            wh = "Trial: a choice event (see K_Trial)" if fn == "events.py" else ("Trial: outcome or description text" if fn == "run.py" else ("Legacy story layer text template" if fn == "story.py" else ""))
        b.add(wsL, [pr["file"], pr["line"], pr["function"], wh, pr["text"]])
    b.finish(wsL)

    # ---------------------------------------------------------------- M Runtime checks
    wsM = b.sheet(SHEETS["M"], ["Check ID", "What was checked", "What the audit expected", "Result", "What the game actually did (plain English)", "How to re-run"], [10, 52, 70, 22, 110, 50], freeze="C2", tab="00695C")
    for pid, p in sorted(probes.items()):
        r = b.add(wsM, [pid, p["title"], p["claim"], p["verdict"], short_probe(pid, probes), "python docs/DIALOGUE_STORY_AUDIT/scripts/probe_runtime.py  (raw results: generated/runtime_probes.json)"], bold_first=True,
                  fill=(WARN if "defect" in p["verdict"] else (AMBER if "failed" in p["verdict"] else None)))
    b.add(wsM, ["", "Existing automated tests run before the audit", "tests/test_narrative_conversation.py, test_narrative_quests.py, test_narrative_characters.py, test_wizard_tutorial.py, test_wizard_campaign.py, test_wizard_aspects_worldviews.py, test_mortality.py, test_village.py, test_trial.py, test_mira_trial.py, test_free_opening.py, test_ai_wizard.py, test_wizard_party.py, test_narrative_isolation.py",
                "209 passed", "All passed in 100 seconds on 16 Oct 2026 before any audit file was written.", "python -m pytest WizardRTSHybrid/tests/<those files> -q"], fill=GOOD)
    b.finish(wsM)

    # ---------------------------------------------------------------- N Defects
    wsN = b.sheet(SHEETS["N"], ["ID", "Severity", "Category", "Where (dialogue ids)", "What happens (plain English)", "Evidence", "Possible direction (NOT applied)", "Status"], [10, 10, 34, 52, 100, 22, 46, 18], freeze="D2", tab="B71C1C")
    for d in curated.DEFECTS:
        r = b.add(wsN, [d["id"], d["severity"], d["category"], d["where"], d["what"], d["evidence"], d["direction"], "Not fixed (audit only)"], bold_first=True,
                  fill=(WARN if d["severity"] == "Medium" else (SOFT if d["severity"] == "Info" else None)))
    b.add(wsN, [""] * 8)
    b.add(wsN, ["AUTO", "", "Automated static findings (every one is also summarised above where it matters)", "", "", "", "", ""], fill=AMBER, bold_first=True)
    for f in static:
        b.add(wsN, [f["id"], f["severity"].capitalize(), f["kind"], f["where"], f["what"], f["evidence"][:200], "", "Not fixed (audit only)"], fill=SOFT)
    b.add(wsN, [""] * 8)
    b.add(wsN, ["IDEAS", "", "Opportunities for improvement (not defects)", "", "", "", "", ""], fill=AMBER, bold_first=True)
    for o in curated.OPPORTUNITIES:
        b.add(wsN, [o["id"], "Idea", "Opportunity", "", o["idea"], "", "", ""])
    b.finish(wsN)

    # ---------------------------------------------------------------- O Legacy
    wsO = b.sheet(SHEETS["O"], ["ID", "System", "What it is", "Status", "Reachable in Wizard World?", "How this was established", "Files"], [9, 46, 80, 32, 36, 60, 56], freeze="C2", tab="9E9E9E")
    for lg in curated.LEGACY:
        b.add(wsO, [lg["id"], lg["name"], lg["what"], lg["status"], lg["reach"], lg["evidence"], lg["files"]], bold_first=True, fill=(None if lg["reach"].startswith("Partially") else SOFT))
    b.finish(wsO)

    # ---------------------------------------------------------------- README (first)
    wsR = b.wb.create_sheet(SHEETS["README"], 0)
    wsR.sheet_properties.tabColor = NAVY
    wsR.column_dimensions["A"].width = 24
    wsR.column_dimensions["B"].width = 120
    rows = [
        ("Wizard World — Dialogue and Story Workbook", ""),
        ("What this is", "Every conversation, choice, skill check and consequence that the current Wizard World game can produce, extracted from the game's own data and code on 16 Oct 2026 (branch analysis/dialogue-story-audit). Nothing in the game was changed."),
        ("How to read it like a book", "Start at A_Index (one row per story). Click a Collection ID to jump to its first spoken line in B_Dialogue. Follow ‘Reached from’ to the choice that leads to a line, and the choice's ID to the line it triggers. Read docs/DIALOGUE_STORY_AUDIT/STORIES_SUMMARY.md first for the plain-English walk-through, and diagrams/ for the branching pictures."),
        ("How to edit it later", "Every row has a stable ID (for example FOREST.cutter.hub.c-what_happened) built from the story, speaker, node and choice. Source file and path tell you where the text lives in the game's files. Edit nothing here expecting the game to change: this workbook is a reading copy; there is no importer yet."),
        ("Filters", "Every table has filters and a frozen header. Filter Collection to one story; filter Status today to see what is playable, never spoken, multiplayer-only or reachable only by the simulation."),
        ("", ""),
    ]
    for i, (a, bb) in enumerate(rows, 1):
        wsR.cell(row=i, column=1, value=a).font = Font(name="Calibri", size=16 if i == 1 else 11, bold=True)
        wsR.cell(row=i, column=2, value=bb).alignment = Alignment(wrap_text=True, vertical="top")
        wsR.cell(row=i, column=2).font = BASE
    wsR.row_dimensions[3].height = 62
    wsR.row_dimensions[4].height = 62
    r = len(rows) + 1
    wsR.cell(row=r, column=1, value="Sheet").font = BOLD
    wsR.cell(row=r, column=2, value="What it holds").font = BOLD
    desc = {
        "A": "Story and quest index: status, where, how it starts, prerequisites, characters, endings, counts, diagram links.", "B": f"Dialogue: {len(lines)} lines with exact text, speaker, node, conditions, effects, status and source.",
        "C": f"Player choices: {len(choices)} choices, topics and belief replies with skill, difficulty, destinations and effects.", "D": f"Branches and outcomes: {len(curated.OUTCOMES)} outcomes with consequences and what people say afterwards.",
        "E": "Characters and attributes: fixed and generated characters, worldviews, traits, starting regard, special conditions, examples.", "F": "Rules and glossary in plain English: Aspects, checks, regard, worldviews, reactions, flags, availability, stages, multiplayer.",
        "G": f"Skill checks: {len(inv['checks'])} checks with the arithmetic for a fresh apprentice.", "H": "Flags and facts: what each flag means, who sets and reads it, learned facts that nothing reads, live world facts.",
        "I": "Dynamic selection: which variant is spoken first, the order of entries, rotation rules.", "J": "Ideology reactions: how each kind of person takes each belief reply.", "K": "The Trial: every choice event branch, and the creatures and people you can duel.",
        "L": "System text written in Python: journal notes, objectives, refusals, Trial outcome text, legacy story text.", "M": f"Runtime checks: {len(probes)} small tests that drove the real game code, with what they showed.",
        "N": "Defects, confusing logic and ideas (nothing was fixed).", "O": "Older and experimental systems, and whether Wizard World can reach them.",
    }
    for k in "ABCDEFGHIJKLMNO":
        r += 1
        wsR.cell(row=r, column=1, value=SHEETS[k]).hyperlink = f"#'{SHEETS[k]}'!A1"
        wsR.cell(row=r, column=1).font = LINK
        wsR.cell(row=r, column=2, value=desc[k]).alignment = Alignment(wrap_text=True)
        wsR.cell(row=r, column=2).font = BASE
    r += 2
    for t_, d_ in (("Colours", "Amber = something to look at (never spoken, cannot be reached by a normal apprentice, or has no failure). Red tint = confirmed defect. Green = passes."),
                   ("Status today", "Playable · Playable once the quest is cast · Playable if a guard is cast · Multiplayer only · Reachable only if the simulation… · Never spoken · Engine fallback · Exists but cannot be reached by a normal apprentice."),
                   ("Placeholders", "{name}, {mentor}, {attacker}, {settlement}, {cutter}… are filled in by the game with the real names of the people in your world. Lines with {logs} or {saplings} use live numbers."),
                   ("Reproducing", "python docs/DIALOGUE_STORY_AUDIT/scripts/run_all.py   (extract → analyse → probe → build workbook and diagrams → validate)")):
        wsR.cell(row=r, column=1, value=t_).font = BOLD
        wsR.cell(row=r, column=2, value=d_).alignment = Alignment(wrap_text=True)
        wsR.cell(row=r, column=2).font = BASE
        r += 1

    b.wb._sheets.sort(key=lambda w: list(SHEETS.values()).index(w.title))  # noqa: SLF001
    b.wb.active = 0
    b.wb.save(XLSX)
    print("saved", rel(XLSX), {ws.title: ws.max_row - 1 for ws in b.wb.worksheets})


if __name__ == "__main__":
    main()
