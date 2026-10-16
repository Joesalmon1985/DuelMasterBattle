"""Writes the branching diagrams (docs/DIALOGUE_STORY_AUDIT/diagrams/*.md): an overview of each story drawn by hand from the checked behaviour, and a detailed
choice tree GENERATED from the dialogue data so that it cannot drift from the game's files. Each file has an ASCII tree (readable anywhere) and a Mermaid
flowchart (renders on GitHub and in most Markdown viewers).

Run:  python docs/DIALOGUE_STORY_AUDIT/scripts/build_diagrams.py
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any

from common import DIALOGUE, OUT, Describer, FLAG_MEANING, LESSON_TITLES, aspect_label, load_json, rel

GEN = OUT / "generated"
DIR = OUT / "diagrams"
DIR.mkdir(exist_ok=True)
D = Describer({tuple(k.split("::")): v for k, v in FLAG_MEANING.items()})
THR = {"easy": 2, "demanding": 4, "exceptional": 6}

SPEAKER_TITLES = {"teacher": "The Mentor", "cutter": "The woodcutter", "planter": "The forester", "witness": "The witness", "mason": "The mason", "hauler": "The carrier", "ranger": "The forester (patrol)",
                  "guard": "The guard", "keeper": "The warehouse keeper", "mother": "The mother", "official": "The Rollkeeper", "knight": "Serra (knight)", "elf": "The elven contestant",
                  "throm": "Throm", "barbarian": "The barbarian", "assassin": "The figure in black"}


def short(s: str, n: int = 70) -> str:
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def mm(s: str) -> str:
    return short(s, 58).replace('"', "'").replace("[", "(").replace("]", ")").replace("{", "(").replace("}", ")").replace("<", "‹").replace(">", "›")


def first_line(block: dict[str, Any] | None) -> str:
    if not block:
        return ""
    for l in block.get("lines", []):
        return l["text"] if isinstance(l, dict) else l
    return ""


# ------------------------------------------------------------------------------------------------------------------------------------------
# The generated tree for a graph template

def build_tree(tpl: str) -> dict[str, Any]:
    data = load_json(DIALOGUE / f"{tpl}.json")
    items: dict[str, dict[str, Any]] = {}
    setters_flag: dict[str, list[str]] = defaultdict(list)
    setters_lesson: dict[str, list[str]] = defaultdict(list)
    goto_into: dict[tuple[str, str], list[str]] = defaultdict(list)
    for sp, spec in data["speakers"].items():
        for nid, node in spec["nodes"].items():
            for c in node.get("choices", []):
                key = f"{sp}.{nid}.{c['id']}"
                items[key] = {"key": key, "sp": sp, "node": nid, "c": c, "children": []}
                blocks = [c] + [c.get(b) for b in ("pass", "fail") if c.get(b)]
                for blk in blocks:
                    for f in blk.get("sets", []):
                        setters_flag[f].append(key)
                    for e in blk.get("effects", []):
                        if e["kind"] == "complete_lesson":
                            setters_lesson[e["lesson"]].append(key)
                        if e["kind"] == "begin_duel":
                            setters_lesson[e["purpose"]].append(key)
                if c.get("once"):
                    setters_flag["done:" + c["id"]].append(key)
                if c.get("goto") and c["goto"] != "hub":
                    goto_into[(sp, c["goto"])].append(key)
    roots: dict[str, list[str]] = defaultdict(list)
    for key, it in items.items():
        c, sp, nid = it["c"], it["sp"], it["node"]
        w = c.get("when") or {}
        parents: list[str] = []
        if nid != "hub":
            parents += goto_into.get((sp, nid), [])
        for f in w.get("requires", []):
            for s in setters_flag.get(f, []):
                if s != key and s not in parents and items[s]["sp"] == sp:  # only the same person's earlier choices make a branch; other people's flags are listed under ‘after:’
                    parents.append(s)
                    break
        for l in w.get("lessons", []):
            for s in setters_lesson.get(l, []):
                if s != key and s not in parents and items[s]["sp"] == sp:
                    parents.append(s)
                    break
        it["parents"] = parents
        if parents:
            items[parents[0]]["children"].append(key)
        else:
            roots[sp].append(key)
    return {"data": data, "items": items, "roots": roots}


def choice_label(it: dict[str, Any], tpl: str) -> str:
    c = it["c"]
    ck = c.get("check")
    pre = f"[{aspect_label(ck['aspect'])}, {ck.get('threshold', 'demanding')} {THR[ck.get('threshold', 'demanding')]}] " if ck else ""
    return f"{pre}“{short(c['text'], 78)}”"


def choice_notes(it: dict[str, Any], tpl: str) -> list[str]:
    c = it["c"]
    out: list[str] = []
    w = dict(c.get("when") or {})
    flags = w.pop("requires", []), w.pop("forbids", [])
    extra = D.when(tpl, w)
    if extra:
        out.append("needs: " + "; ".join(short(x, 90) for x in extra))
    if flags[0]:
        out.append("after: " + "; ".join(short(D.flag(tpl, f).strip("“”"), 70) for f in flags[0]))
    if flags[1]:
        out.append("not if: " + "; ".join(short(D.flag(tpl, f).strip("“”"), 70) for f in flags[1]))
    if c.get("once"):
        out.append("single use")
    first = first_line(c)
    if first:
        out.append("says: “" + short(first, 100) + "”")
    eff = D.effects(tpl, {k: v for k, v in c.items() if k in ("sets", "clears", "effects")})
    if eff:
        out.append("effects: " + "; ".join(short(e, 80) for e in eff))
    if c.get("check"):
        ck = c["check"]
        ev = "; ".join(f"+{e.get('mod', 1)} {short(D.when_text(tpl, e.get('when')), 60)}" for e in ck.get("evidence", []))
        out.append(f"check: {aspect_label(ck['aspect'])} {ck.get('threshold', 'demanding')} ({THR[ck.get('threshold', 'demanding')]}); evidence: {ev or 'none'}")
        p, f = c.get("pass") or {}, c.get("fail") or {}
        out.append("PASS → “" + short(first_line(p), 90) + "”" + (" · ends" if p.get("ends") else "") + (" · " + "; ".join(short(e, 60) for e in D.effects(tpl, p)) if D.effects(tpl, p) else ""))
        out.append("FAIL → “" + short(first_line(f), 90) + "” · stays in the conversation; button greyed until the score, evidence or regard changes")
    for e in c.get("effects", []):
        if e["kind"] == "begin_duel":
            out.append("→ starts a Ward duel; the conversation ends and the mentor comments afterwards")
    if c.get("goto") and c["goto"] != "hub":
        out.append(f"→ moves to node ‘{c['goto']}’")
    if c.get("ends"):
        out.append("→ conversation ends")
    return out


def ascii_tree(tpl: str, tree: dict[str, Any]) -> str:
    out: list[str] = []
    items = tree["items"]

    def walk(key: str, prefix: str, last: bool) -> None:
        it = items[key]
        branch = "└── " if last else "├── "
        out.append(prefix + branch + choice_label(it, tpl))
        pad = prefix + ("    " if last else "│   ")
        notes = choice_notes(it, tpl)
        kids = it["children"]
        for n in notes:
            out.append(pad + ("│   " if kids else "    ") + "· " + n)
        for i, k in enumerate(kids):
            walk(k, pad, i == len(kids) - 1)

    for sp, rootkeys in tree["roots"].items():
        out.append("")
        out.append(f"■ {SPEAKER_TITLES.get(sp, sp)} ({sp})")
        for i, k in enumerate(rootkeys):
            walk(k, "", i == len(rootkeys) - 1)
    return "\n".join(out)


def mermaid_tree(tpl: str, tree: dict[str, Any]) -> str:
    items = tree["items"]
    ids = {k: f"n{i}" for i, k in enumerate(items)}
    lines = ["```mermaid", "flowchart LR"]
    for sp, rootkeys in tree["roots"].items():
        lines.append(f"  subgraph S_{sp}[\"{mm(SPEAKER_TITLES.get(sp, sp))}\"]")
        lines.append("    direction TB")
        seen: set[str] = set()

        def collect(k: str) -> None:
            if k in seen:
                return
            seen.add(k)
            for ch in items[k]["children"]:
                collect(ch)

        for k in rootkeys:
            collect(k)
        for k in sorted(seen, key=list(items).index):
            c = items[k]["c"]
            label = mm(("[" + aspect_label(c["check"]["aspect"]) + "] " if c.get("check") else "") + c["text"])
            lines.append(f"    {ids[k]}[\"{label}\"]")
        lines.append("  end")
    for k, it in items.items():
        for ch in it["children"]:
            lines.append(f"  {ids[k]} --> {ids[ch]}")
    cls_check = [ids[k] for k, it in items.items() if it["c"].get("check")]
    cls_end = [ids[k] for k, it in items.items() if it["c"].get("ends")]
    cls_duel = [ids[k] for k, it in items.items() if any(e["kind"] == "begin_duel" for e in it["c"].get("effects", []))]
    if cls_check:
        lines.append("  classDef check fill:#FFF4D6,stroke:#C79100;")
        lines.append("  class " + ",".join(cls_check) + " check;")
    if cls_end:
        lines.append("  classDef ends fill:#E0E0E0,stroke:#757575;")
        lines.append("  class " + ",".join(cls_end) + " ends;")
    if cls_duel:
        lines.append("  classDef duel fill:#FDECEA,stroke:#C62828;")
        lines.append("  class " + ",".join(cls_duel) + " duel;")
    lines.append("```")
    return "\n".join(lines)


def entry_table(tpl: str, inv: dict[str, Any], conv: str) -> str:
    """The speaker's opening lines in order (the first whose conditions hold is spoken)."""
    out: list[str] = ["", "**What each person says on entry, in order (the first entry whose conditions hold is spoken; the rest are ignored)**", ""]
    bysp: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for l in inv["lines"]:
        if l["conv"] == conv and l.get("order") and not l.get("ref") and ".alt" not in l["block"]:
            bysp[l["speaker"]][l["block"]].append(l)
    for sp, blocks in bysp.items():
        out.append(f"*{sp}*")
        out.append("")
        out.append("| # | Entry | Speaks when | First line |")
        out.append("|---|-------|-------------|------------|")
        for bl, ls in sorted(blocks.items(), key=lambda kv: kv[1][0]["order"]):
            g = ls[0]
            cond = g["cond"].split("; no earlier entry")[0].replace("no earlier entry of this node applied", "otherwise")
            out.append(f"| {g['order']} | `{bl}` | {short(cond, 150).replace('|', '/')} | {short(g['text'], 90).replace('|', '/')} |")
        out.append("")
    return "\n".join(out)


def write(name: str, title: str, intro: str, overview_ascii: str, overview_mermaid: str, detail: str = "", extra: str = "") -> None:
    parts = [f"# {title}", "", intro, "", "## The story at a glance", "", "```text", overview_ascii.strip("\n"), "```", "", overview_mermaid, ""]
    if extra:
        parts += [extra, ""]
    if detail:
        parts += ["## Detailed choice tree (generated from the game's data)", "",
                  "Read each line as: **[Aspect, difficulty number]** is a skill check; `needs`/`after`/`not if` are the conditions that decide whether the choice is offered; `says` is the first line of the response; `effects` are the lasting consequences. "
                  "A child is shown under the choice that makes it available.", "", "```text", detail.strip("\n"), "```", ""]
    (DIR / name).write_text("\n".join(parts), encoding="utf-8")
    print("wrote", rel(DIR / name))


def main() -> None:
    inv = load_json(GEN / "inventory.json")
    probes = {p["id"]: p for p in load_json(GEN / "runtime_probes.json")}

    # ------------------------------------------------------------------ 01 mentor
    t = build_tree("tutorial")
    write("01_mentor_lessons.md", "The Mentor: introduction, lessons and the creed question",
          "Collection CV-MENTOR · workbook rows B_Dialogue (MENTOR.*) and C_Choices. The mentor is the only dedicated teacher. There is no failing state; the lessons end when done, after a wizard duel or death, or after 5 minutes.",
          """First talk (lesson ‘meet’)
│
├── Teach me magic ................................. lesson ‘colours’ (the three colours are already known)
│   ├── [Curiosity, demanding 4] Why three places? .. PASS for a fresh apprentice (3 +0 evidence +1 regard = 4): learns ‘ward_lore’
│   │                                                 FAIL line exists but cannot be reached in normal play
│   ├── [Wonder, demanding 4] The light on your staff  first try FAILS (2 +0 +1 = 3): button greys out
│   │                                                 PASS after +1 evidence (hidden-Ward lesson or ward_lore): learns ‘mentor_old_craft’
│   ├── [Reason, easy 2] Reading fracture and echo ..  PASS always (2 +0 +1 = 3): learns ‘ward_method’ (nothing reads it)
│   ├── Break a Ward you were told (Frost, Vine, Frost)  → practice duel → mentor comments: quick win / win / lost
│   │   └── Fight me properly (hidden Wards) ......... → practice duel → comments → lesson ‘hidden Ward’
│   │       └── What should I do now? ................ village pointer; names the Forest Dispute people if it is cast
│   │                                                  (shown twice while the quest is offered: DEF-02)
├── I know the colours. Test me. ................... shortcut, only after one earlier wizard duel
├── Why does no wizard simply rule? (single use) ... creed node: six belief replies + ‘I will think about it’
│                                                      (close the conversation here and the answers are lost: DEF-01)
├── Is there anything you need? .................... the log errand (keeper → mentor thanks, regard +5)
└── Thank you. I will go. .......................... ends""",
          """```mermaid
flowchart TD
  A["First talk: lesson 'meet'"] --> B["Teach me magic"]
  A --> C["Why does no wizard rule? (once)"]
  A --> D["Is there anything you need?"]
  A --> Z["Thank you. I will go. (ends)"]
  B --> B1["[Curiosity 4] Why three places?"]
  B --> B2["[Wonder 4] The light on your staff"]
  B --> B3["[Reason 2] Reading fracture and echo"]
  B --> B4["Break a Ward you were told (duel)"]
  B4 --> B5["Fight me properly: hidden Ward (duel)"]
  B5 --> B6["What should I do now?"]
  B6 --> Q["Forest Dispute pointer"]
  B2 -->|fail: greyed out| B2b["needs +1 evidence"]
  B2b -->|hidden-Ward lesson or ward_lore| B2c["PASS: mentor_old_craft"]
  C --> C1["Creed node: 7 replies"]
  C1 -->|closed before answering| C2["Question lost for good"]
  C1 -->|answered| C3["mentor_creed + regard +3/+1/-3"]
  D --> D1["Keeper gives a log -> mentor thanks"]
  classDef check fill:#FFF4D6,stroke:#C79100;
  class B1,B2,B3 check;
  classDef duel fill:#FDECEA,stroke:#C62828;
  class B4,B5 duel;
```""", ascii_tree("tutorial", t), entry_table("tutorial", inv, "CV-MENTOR"))

    # ------------------------------------------------------------------ 02 forest
    t = build_tree("forest_dispute")
    write("02_forest_dispute.md", "The Forest Dispute (quest)",
          "Collection CV-FOREST. A woodcutter and a forester (ordinary villagers cast from the simulation) quarrel over felling young trees; a witness saw part of it. Optional: nothing forces the player to hear it.",
          """Stories unlocked (four lessons, or 20 game-minutes) and villagers cast
│
├── Hear the woodcutter ... ‘What happened between you and <forester>?’ ........ flag: heard woodcutter
├── Hear the forester ..... ‘What happened between you and <woodcutter>?’ ...... flag: heard forester
└── The witness (soldier, else stonemason/hunter, else carrier)
    ├── ‘What did you see?’ / ‘What do people say?’ ............................ optional colour
    └── once BOTH sides are heard, choose one settlement:
        ├── Compromise:  woodcutter fells old trees, forester stakes young ones
        │                 regard woodcutter +5, forester +5 · journal note
        ├── Back the woodcutter: timber now ... woodcutter +10, forester −4 · journal note
        ├── Back the forester: let them grow ... forester +10, woodcutter −4 · journal note
        └── Stay out ................................ both −1 · journal note
              │
              └── each of the three says their own closing lines on the next talk;
                  after all three have, the quest is ‘done’ (journal objective clears)

Also: a villager dies/leaves → replaced within 60 game seconds, else ‘interrupted’ · too few villagers → never offered""",
          """```mermaid
flowchart TD
  S["Quest cast: woodcutter, forester, witness"] --> H1["Hear the woodcutter"]
  S --> H2["Hear the forester"]
  S --> W["Talk to the witness"]
  H1 --> D{"Both sides heard?"}
  H2 --> D
  D -->|yes| O["Witness offers four settlements"]
  O --> C1["Compromise: +5 / +5"]
  O --> C2["Back woodcutter: +10 / -4"]
  O --> C3["Back forester: +10 / -4"]
  O --> C4["Stay out: -1 / -1"]
  C1 --> E["Each person's closing words next talk"]
  C2 --> E
  C3 --> E
  C4 --> E
  E --> F["All three closed: quest done"]
  S -. villager gone .-> R["Replaced (60 s) or interrupted"]
```""", ascii_tree("forest_dispute", t), entry_table("forest_dispute", inv, "CV-FOREST"))

    # ------------------------------------------------------------------ 03 granite
    t = build_tree("smith_dispute")
    write("03_missing_granite.md", "The Missing Granite (quest)",
          "Collection CV-GRANITE. A mason says a load of granite never arrived; a carrier says it did. The only village decision that changes a real ware.",
          """Hear the mason ......... ‘Tell me about the stone.’
Hear the carrier ....... ‘What happened to the sixth load?’
        │ (both heard)
        ├── Mason: ‘I believe you. I will ask the keeper for a load from the store.’
        │      → ONE GRANITE leaves the home warehouse · mason +5, carrier −3 · journal note · conversation ends
        ├── Carrier: ‘I believe you. The mason can fetch the stone again.’
        │      → nothing moves · carrier +5, mason −3 · no journal note · conversation ends
        └── Carrier: [Reason, easy 2] ‘Grout sacks, you said. Where does the keeper stack grout?’
               PASS (always for a normal apprentice: 2 +1 evidence = 3) → the load was under the grout
                    both +3 · Reason +1 · ledger ‘found_the_granite’ · journal note · ends
               FAIL → ‘All over the place, that morning.’ (unreachable in normal play)
(two wizards who each back the mason cost the warehouse two loads: DEF-17)""",
          """```mermaid
flowchart TD
  A["Hear the mason"] --> C{"Both heard?"}
  B["Hear the carrier"] --> C
  C --> M["Back the mason"]
  C --> H["Back the carrier"]
  C --> R["[Reason 2] Where does the keeper stack grout?"]
  M --> M1["1 granite leaves warehouse; mason +5 carrier -3"]
  H --> H1["No ware moves; carrier +5 mason -3"]
  R -->|pass| R1["Granite found; both +3; Reason +1"]
  R -->|fail| R2["'All over the place' (cannot happen normally)"]
  classDef check fill:#FFF4D6,stroke:#C79100;
  class R check;
```""", ascii_tree("smith_dispute", t), entry_table("smith_dispute", inv, "CV-GRANITE"))

    # ------------------------------------------------------------------ 04 patrol
    t = build_tree("ranger_patrol")
    write("04_patrol.md", "The Patrol (quest)",
          "Collection CV-PATROL. A forester prepares a patrol of the valley's edge. The guard (a soldier, else hunter/lumberjack) is optional. This is where the Trial is first spoken of.",
          """Hear the forester ........ ‘Which way are you thinking?’ (north fences or east road)
        ├── ‘Why does nobody go east?’ ... the Trial gate, learns ‘trial_rumour’ (nothing reads it)
        ├── ‘Go north.’ .................. patrol_north · forester agrees · ends
        └── [Curiosity, easy 2] ‘Go east, and look at the road…’
               PASS (Curiosity 3) → agrees to count contestants; patrol_east · ends
               FAIL → ‘North, I think.’ (cannot happen: Curiosity never falls below 3)
The guard: if the patrol went east he says ‘<forester> is off east tonight on your say-so…’; otherwise he warns against the east road.
The quest NEVER reaches ‘done’ (needs two closing flags; the guard never sets one: DEF-03).""",
          """```mermaid
flowchart TD
  A["Hear the forester about the patrol"] --> B["Why does nobody go east?"]
  A --> N["Go north"]
  A --> E["[Curiosity 2] Go east"]
  E -->|pass| E1["Patrol goes east"]
  E -->|fail| E2["'North, I think' (unreachable normally)"]
  N --> X["Forester closes next talk"]
  E1 --> X
  X --> Y["Quest status stays 'active' forever"]
  classDef check fill:#FFF4D6,stroke:#C79100;
  class E check;
```""", ascii_tree("ranger_patrol", t), entry_table("ranger_patrol", inv, "CV-PATROL"))

    # ------------------------------------------------------------------ 05 warehouse
    t = build_tree("warehouse")
    write("05_warehouse_keeper_rats.md", "The warehouse keeper and the rats",
          "Collection CV-WAREHOUSE. Five rats (one big) live in the home warehouse and eat its food. The keeper's words follow what the rats and the wizards have done.",
          """Rats alive (5, one big)
│
├── Ask ‘What's the matter with the warehouse?’ .. keeper's complaint is recorded; Mira (single player) starts helping
├── ‘Those are not rats. They are machines.’ ..... once; then ‘Six legs. Metal. It clicked at me.’ (once)
├── Fight a rat (stand within 2 tiles): win → rat gone; lose → one cast fewer next duel, rat scurries off
│
└── Keeper's greeting changes with the facts:
      burned warehouse · duelling instead of fighting · cleared together · cleared alone · cleared by others · cleared (any)
      · wave 2+ returns (smaller, 3 rats, 20 game-minutes after clearing, up to 6 waves) · progress report · first complaint · quiet
Also: the mentor's log (see the mentor diagram) · with no logs in the store two identical buttons appear (DEF-04)""",
          """```mermaid
flowchart TD
  S["5 rats in the warehouse"] --> Q["Keeper: what's the matter"]
  S --> F["Fight rats: Ward duels"]
  F -->|win| K["Rat broken"]
  F -->|lose| L["Wounded: one cast fewer; rat flees"]
  K --> C{"All rats gone?"}
  C -->|you alone| A1["Keeper: cleared alone"]
  C -->|two wizards| A2["Keeper: cleared together"]
  C -->|others did| A3["Keeper: cleared by others"]
  C --> W["20 game-min later: wave of 3 (max 6 waves)"]
  S -. warehouse burned .-> B["Keeper's rebuke"]
```""", ascii_tree("warehouse", t), entry_table("warehouse", inv, "CV-WAREHOUSE"))

    # ------------------------------------------------------------------ 06 mother
    t = build_tree("mother")
    write("06_mother_death_resurrection.md", "Death, resurrection and the mother",
          "Collections CV-MOTHER and CV-SYSTEM. Apprentices are mortal. A wizard who loses a lethal duel dies and leaves a body; a living wizard standing beside it can channel for 6 seconds to bring them back. A wizard who kills a friend inside the village is grounded by their mother.",
          """Wizard duel (to the death)
│
├── Loser dies: body, tombstone, ledger deaths+1 ... the dead can only watch
├── Killer's ledger kills+1 ... mother.on_death:
│     ├── death INSIDE 20 tiles of the village → mother walks over and speaks; GROUNDED
│     │     ├── ‘It was a duel. They agreed to it.’ → ‘I don't care who started it. Resurrect them.’ (protest counted)
│     │     ├── ‘And if I just walk off?’ → ‘…every road out of this village has me standing in it.’ (protest counted)
│     │     └── ‘I'll put them back.’ → ends
│     │     Every step beyond 20 tiles, and the Trial gate, is refused in her words (three lines, changing every 3 attempts)
│     └── death OUTSIDE → she only hears of it; no grounding
└── Resurrection: stand within 2 tiles, channel 6 s; walking away abandons it
      ├── friend returns with spells, lessons, facts, regard · grounding ends
      ├── the resurrector's mother: ‘There. Was that so hard?’
      └── the victim's mother: ‘You died. I want you to know that I knew.’
Dying to the stranger's duel: game over (a private session ends; in company the others go on).""",
          """```mermaid
flowchart TD
  D["Lethal wizard duel"] --> V["Loser dies, body left"]
  D --> K{"Killed inside the village?"}
  K -->|yes| G["Mother grounds the killer"]
  K -->|no| H["Mother hears of it"]
  G --> P["Protest / walk off / put them back"]
  G --> R["Steps beyond 20 tiles refused"]
  V --> Z["Friend channels 6 s beside the body"]
  Z --> U["Alive again: grounding ends"]
  U --> T["Mother: 'Was that so hard?'"]
```""", ascii_tree("mother", t), entry_table("mother", inv, "CV-MOTHER"))

    # ------------------------------------------------------------------ 07 stranger
    sc = load_json(DIALOGUE / "campaign_scenes.json")
    write("07_stranger.md", "The stranger: arrival, confrontation, duel and retreat",
          "Collection CV-STRANGER. Scripted scenes: pages the player acknowledges one at a time. The world keeps running until a page needs the player; the clock pauses only during scenes and the duel.",
          """Exploring (3 min + 3 contacts, or 7 min whatever happened; nothing else open)
│
▼
NOTICE (1 page) ‘A stranger in a dark travelling cloak is walking into <village>…’ → he walks in
│
▼
CONFRONTATION (11 pages)                               [or ALONE (5 pages) if the mentor is already gone]
  1 narrator: the mentor takes up the staff            (multiplayer: a wizard arriving mid-scene)
  2-6 mentor and stranger argue (Harrowmere, power as a licence, ‘No.’)
  7 narrator: the light opens like a door
  8 narrator: the mentor falls                         ← THE MENTOR IS KILLED (a real death, once, even if nobody reads it)
  9 narrator: ‘For the first time he sees you.’
 10 stranger speaks to you (line chosen by your history: kills, duels, deaths, lessons, Mira)
      your answer:
        ├── [Resolve, demanding 4] ‘Try it.’ ... PASS needs hidden-Ward lesson +1 and creed answer +1 (2+1+1=4): fact ‘stood_firm’
        │                                         FAIL: ‘Your voice shakes…’ (no penalty); his reply is the same either way
        └── six belief replies (S A R D G M) + C with the mentor's old-craft secret
              he agrees with S; neutral to A, G, C; disagrees with R, D, M
 11 stranger: ‘I am not a butcher, and you are not enough…’
        ├── ‘Then prove it. Ward against Ward, here, now.’ ──► LETHAL DUEL (3 colours, 3 places; you get 12 casts, he gets 8)
        │       ├── you break his Ward ──► VICTORY (4 pages): he retreats alive · Resolve +1 · journal note · others spared
        │       └── you lose / draw / leave the board ──► YOU DIE (a draw counts as defeat)
        └── ‘(Say nothing. Let him go.)’ ──► he leaves; no duel; no Resolve gain
▼
AFTERMATH: villagers react (see the aftermath diagram); after 2 conversations or 150 s:
  journal ‘Objective: seek greater magical power.’  → stage ‘complete’""",
          """```mermaid
flowchart TD
  X["Exploring"] --> N["Notice: he walks in"]
  N --> C["Confrontation: 11 pages"]
  C --> K["Page 8: the mentor is killed"]
  K --> A["Page 10: your answer"]
  A --> R["[Resolve 4] Try it"]
  A --> B["Six belief replies (+ C)"]
  R --> F["Page 11"]
  B --> F
  F -->|challenge| Du["Lethal Ward duel"]
  F -->|say nothing| L["He leaves; aftermath"]
  Du -->|win| V["Victory scene; he retreats alive"]
  Du -->|lose, draw or leave| M["You die"]
  V --> AF["Aftermath"]
  L --> AF
  AF --> Z["Objective: seek greater magical power"]
  classDef check fill:#FFF4D6,stroke:#C79100;
  class R check;
  classDef duel fill:#FDECEA,stroke:#C62828;
  class Du,M duel;
```""", "", "\n".join(["", "## Pages and answers (exact order)", "", *[f"- **{sid}** ({len(s['pages'])} pages, then ‘{s.get('final')}’)" for sid, s in sc["scenes"].items()]]))

    # ------------------------------------------------------------------ 08 aftermath + everyday
    aft = load_json(DIALOGUE / "aftermath.json")
    react_lines = ["| # | Reaction id | Trade | Knowledge | Personality needed |", "|---|-------------|-------|-----------|--------------------|"]
    for i, r in enumerate(aft["reactions"], 1):
        w = r.get("when", {})
        react_lines.append(f"| {i} | `{r['id']}` | {', '.join(w.get('role', ['any']))} | {', '.join(w.get('knows', ['any']))} | {'; '.join(D.persona(w['persona'])) if w.get('persona') else '—'} |")
    write("08_aftermath_and_everyday.md", "After the stranger, and everyday talk",
          "Collections CV-AFTER and CV-EVERYDAY. Dynamic dialogue: what an ordinary villager says depends on their trade, personality, what they saw, the live simulation, and how often you have spoken to them.",
          """Talk to any villager
│
├── first time ever ........ introduction (1 of 2 wordings, seeded draw)
├── later .................. greeting (1 of 3-4 wordings, seeded draw)
├── after the stranger has gone, FIRST talk only:
│     the first matching REACTION (table below) by trade → knowledge (saw him / heard of him) → personality
└── topics (up to 3 priority + 3 rotating; hidden if their conditions fail)
      ├── ‘What happened here today?’ (witnessed vs rumour wording)
      ├── ‘How are you taking it?’ + six belief replies: they agree/neutral/disagree by their own worldview
      ├── [Curiosity 4] ‘Did anyone know him?’ → PASS (needs +1 evidence: you witnessed, or know the old craft): Harrowmere clue
      ├── [Empathy 2] sympathy topic (fond villagers) → PASS: regard +6
      ├── [Authority 2] ‘Report, soldier.’ (soldiers who saw him) → needs +1 (stood_firm)
      ├── [Guile 2] ‘Confirm it for me’ → needs +1 (Harrowmere clue); FAIL: regard −2
      ├── [Reason 2] ‘Tell me exactly what you saw.’ (proud/blunt rumour-bearers) → PASS
      ├── ‘Where could I learn more?’ → advice by the villager's worldview (D grove, R cloister, G guild-school, M court-mage, S master, A open road, C the pattern)
      └── trade questions (trees, timber, stone, game, cargo, soldiers, barracks…) that appear only when true in the world""",
          """```mermaid
flowchart TD
  T["Talk to a villager"] --> F{"First time?"}
  F -->|yes| I["Introduction"]
  F -->|no| G["Greeting"]
  T --> S{"Stranger gone and first talk since?"}
  S -->|yes| R["First matching reaction: trade, knowledge, personality"]
  T --> P["Topics: 3 priority + 3 rotating"]
  P --> K["Curiosity / Empathy / Authority / Guile / Reason checks"]
  P --> V["Belief reply -> agree / neutral / disagree"]
```""", "", "\n".join(["", "## The first reactions, in the order they are tried", "", *react_lines, "",
                      "A reaction line can itself carry sub-lines that appear only for certain personalities (for example a ‘wary’ remark when regard is 5 or less)."]))

    # ------------------------------------------------------------------ 09 Trial
    t = build_tree("trial_gate")
    ev = probes["P38"]["observed"]["events"]
    lines = []
    for name, cases in ev.items():
        lines.append(f"■ {name}")
        for c in cases:
            sit = "" if not c.get("setup") else f" [{'; '.join(f'{k}={v}' for k, v in c['setup'].items())}]"
            lines.append(f"   ├── {c.get('choice') or '(open)'}{sit}: " + short((c.get('text') or c.get('error') or '').replace('\n', ' '), 110) +
                         (f"   ⟶ condition: {', '.join(c['conditions'])}" if c.get("conditions") else "") + (f"   ⟶ FIGHT {c['fight'][1]}" if c.get("fight") else ""))
    write("09_trial_gate_and_events.md", "The Trial of Champions: the gate and the choice events",
          "Collections CV-TRIALGATE and CV-TRIAL. The Rollkeeper registers contestants at the gate; inside, 15 choice events (ported from the book) shape the run. Run state is shared by every wizard in the run.",
          """Gate: the Rollkeeper (reads your history)        Inside the Trial (17 zones)
 ├── ‘What is the Trial?’ (once)                    Throm at the pit ........ lowered / lower him / jump / alone → ally, betrayed, wounded
 ├── [Empathy] ‘Any advice?’                         Black book vial ......... drink (poisoned) / rub (heals a wound) / leave
 ├── ‘I am going in.’ (if unprepared)                Dwarf Trialmaster ....... accept or attack with Throm → dice (no consequence) → cobra → map, learn Stone
 ├── ‘Why write it down at all?’ (fourth wall)       Dying elf ............... stay or take the charm → ‘the real diamond is cold’
 └── warnings for killers, unprepared, returners     Idol's false eye ........ take (wakes the second guardian)
                                                     False diamond ........... take (wound, vault locks)
Contestants (talk only): knight Serra,               Starved man ............. free (Bloodbeast hates Vine)
 elven woman, Throm, barbarian, figure in black      Poison Ivy's toll ....... torch / leave / attack (lethal duel)
                                                     Basket man .............. needs Ivy paid or the prisoner freed
                                                     Mirrors ................. smash (no duel) / leave
                                                     Boulder ................. run / brace with Stone / hold (wound)
                                                     Trapped chest ........... jam with Stone / side / head-on (wound)
                                                     Troglodyte rite ......... join / run / attack (duel)
                                                     Igbut's door ............ place gems; SED wins; 3 wrong orders scatter the gems""",
          """```mermaid
flowchart TD
  G["Gate: Rollkeeper"] --> E["Enter the Trial"]
  E --> P["Throm's pit"]
  P --> D["Dwarf Trialmaster"]
  D --> L["Lower Trial: idol, grotto, vaults, service tunnels, mirrors, blood, grub tunnels, troglodytes"]
  L --> M["Manticore (hates light)"]
  M --> I["Igbut's door: gems in order SED"]
  I --> C["Champion of the Trial"]
  E -. dead .-> X["Body in the zone; a friend can resurrect"]
```""", ascii_tree("trial_gate", t), "\n".join(["", "## Every choice event, branch by branch (from runtime check P38)", "", "```text", *lines, "```"]))

    # ------------------------------------------------------------------ 10 Mira
    write("10_mira.md", "Mira, the AI fellow apprentice",
          "Collection CV-MIRA. A second wizard seat in a single-player game; she is not a villager and has no conversation card (talk and inspect are refused). Her voice is short messages.",
          """Mira follows you (2 to 6 tiles) and greets you once when close ............. ‘I learned my colours here a season ago…’
│
├── You challenge her (pvp_challenge)
│     ├── 1st and 2nd request ... declines with a line (counted as a provocation); a duel never starts
│     └── 3rd request ........... accepts with a ‘provoked’ line (‘Three times…’)
│            ├── she wins ... ‘Your Ward held that time…’ · her regard for you +3
│            ├── she loses .. ‘Well cast. You read my Ward faster…’ · her regard −4
│            └── draw ....... ‘Neither of us broke through.’
├── She kills you in a lethal duel .. ‘Oh no. Stay exactly there, I know the words.’ → walks to your body and resurrects you
├── You kill her ................... she stays dead until brought back; when you do: ‘You brought me back. I remember exactly who put me there.’ (regard +8)
├── Rats ........................... helps once the keeper has complained: ‘One rat fewer…’ / ‘It got away.’
└── The Trial ...................... follows in (‘Wait for me…’), comments on zones, leaves when you do; if grounded by her mother she cannot enter
NEVER SPOKEN: ‘you_died_again’ (2 lines)""",
          """```mermaid
flowchart TD
  F["Mira follows"] --> G["Greets once"]
  G --> C{"You challenge"}
  C -->|1st or 2nd| D["Declines"]
  C -->|3rd| A["Accepts: provoked line"]
  A --> W["Win / lose / draw lines"]
  F --> T["Follows into the Trial"]
  F --> R["Helps with rats"]
  W -->|she kills you| Z["Resurrects you"]
```""", "", "\n".join(["", "## Her parameters (ai_wizards.json)", "", "- thinks 2.5 to 6 seconds between casts; guesses with the candidate-filter solver; mistake rate 0",
                      "- starts with regard 25; accepts if regard ≥ −10 and she has been asked at least twice; win +3, loss −4, killed −12, resurrected +8"]))

    # ------------------------------------------------------------------ 11 legacy
    write("11_legacy_story_layer.md", "Legacy story layer: the collapsed gallery and the outbreak healer",
          "Collections CV-LEGACY-MINE and CV-LEGACY-OUTBREAK. These older quests are still wired into the live simulation. They appear only when the simulation produces a trigger; the player cannot start them.",
          """MINE COLLAPSES (tremor, war damage or age)                    OUTBREAK (2+ marks in a settlement's region)
│                                                               │
└── A miner stands beside the mine                              └── A healer stands in the settlement
      ├── ‘What happened to the mine?’ → cause (+1 evidence)           ├── ‘I will treat the region…’ → stand in the region and use Treat
      ├── ‘Is there another way in?’ → the old gallery                 └── ‘I cannot help.’ → the outbreak stays
      ├── ‘I will go down the old gallery.’ → a sigil                  Outcomes: treated · passed by itself · settlement destroyed
      ├── [Empathy, easy 2] ‘Tell me what the warden does.’
      │       PASS → miner's regard +15; the warden duel gets extra casts
      │       FAIL → ‘You do not know what I know.’
      └── ‘I cannot help.’ → quest fails, regard −20
   Then: the old gallery (a puzzle dungeon) and the warden's Mastermind duel:
        win → the gallery reopens now ‘full’ · lose → ‘thin’: the crew finishes the dig in a few minutes""",
          """```mermaid
flowchart TD
  C["Mine collapses"] --> M["Miner appears"]
  M --> Q1["What happened?"]
  Q1 --> Q2["Another way in?"]
  Q2 --> Q3["Go down the old gallery: sigil"]
  Q3 --> E["[Empathy 2] What does the warden do?"]
  Q3 --> G["Puzzle gallery, warden duel"]
  E -->|pass| X["Extra casts"]
  M --> N["I cannot help: fails"]
  O["Outbreak 2+ marks"] --> H["Healer appears"]
  H --> T["Treat the region"]
  H --> N2["I cannot help"]
```""", "", "")

    # ------------------------------------------------------------------ 12 campaign
    write("12_campaign_flow.md", "The whole opening at a glance",
          "How the stages of the campaign follow each other, with the actual timing from config.json.",
          """NEW WORLD
 ▼ opening narration (3 paragraphs)
TRAINING  — the mentor's lessons (meet → colours → told Ward → hidden Ward)
 │  ends: four lessons done  OR  a wizard duel / death has happened  OR  5 min of game time
 ▼
EXPLORE   — free play; quests unlock (4 lessons or 20 min); rats; Mira (single player); mother; Trial gate
 │  the stranger comes: 3 min AND 3 contacts, or 7 min regardless, only if no conversation / duel / dungeon is open
 ▼
ARRIVAL → CONFRONTATION (mentor killed) → [challenge] DUEL → VICTORY      or      [let go] ─┐
                                              └── defeat → GAME OVER / death              ▼
AFTERMATH — villagers react; ends after 2 conversations or 150 s ◄───────────────────────┘
 ▼
COMPLETE  — journal: ‘Objective: seek greater magical power.’ (the next chapter is not built)""",
          """```mermaid
flowchart LR
  T["Training"] --> X["Explore"] --> A["Arrival"] --> C["Confrontation"]
  C --> D["Duel"] --> V["Victory"] --> AF["Aftermath"] --> CO["Complete"]
  C --> AF
  D --> GO["Game over / death"]
```""")

    (DIR / "README.md").write_text("\n".join([
        "# Branching diagrams", "",
        "One file per substantial story. Each has an ASCII picture of the actual branches (readable in any editor), a Mermaid flowchart (renders on GitHub), and where the story is made of choices, a",
        "detailed choice tree that is generated from the game's data files by `scripts/build_diagrams.py`, so it cannot disagree with the game.", "",
        "| File | Story |", "|------|-------|",
        "| [12_campaign_flow.md](12_campaign_flow.md) | The whole opening in one picture |",
        "| [01_mentor_lessons.md](01_mentor_lessons.md) | The mentor: lessons, skill questions, the creed |",
        "| [02_forest_dispute.md](02_forest_dispute.md) | Forest Dispute (4 endings) |",
        "| [03_missing_granite.md](03_missing_granite.md) | Missing Granite (3 solutions) |",
        "| [04_patrol.md](04_patrol.md) | The Patrol |",
        "| [05_warehouse_keeper_rats.md](05_warehouse_keeper_rats.md) | Keeper and the rats |",
        "| [06_mother_death_resurrection.md](06_mother_death_resurrection.md) | Death, resurrection, the mother |",
        "| [07_stranger.md](07_stranger.md) | The stranger: arrival to retreat |",
        "| [08_aftermath_and_everyday.md](08_aftermath_and_everyday.md) | Villagers after the attack; everyday talk |",
        "| [09_trial_gate_and_events.md](09_trial_gate_and_events.md) | The Trial: gate and 15 choice events |",
        "| [10_mira.md](10_mira.md) | Mira |",
        "| [11_legacy_story_layer.md](11_legacy_story_layer.md) | Miner and healer (simulation-triggered) |", ""]), encoding="utf-8")
    print("diagrams done")


if __name__ == "__main__":
    main()
