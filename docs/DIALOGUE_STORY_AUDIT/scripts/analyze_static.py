"""Static consistency checks over the dialogue data (read-only).

Run:  python docs/DIALOGUE_STORY_AUDIT/scripts/analyze_static.py     (after extract_inventory.py)
Writes: docs/DIALOGUE_STORY_AUDIT/generated/static_findings.json

Looks for: flags that are read but never set, flags set but never read, learned facts that nothing reads, facts a line tests that the game never provides in
that conversation, placeholders no one fills, variants hidden behind an unconditional earlier variant, identical buttons that can be offered together,
`once` on topics (not enforced), and skill checks that cannot fail for a fresh apprentice.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from common import DATA, DIALOGUE, HYBRID, OUT, load_json, rel
from extract_inventory import ENGINE_FLAGS, TEMPLATE_CONV, TEMPLATE_SHORT

GEN = OUT / "generated"
FINDINGS: list[dict[str, Any]] = []


def finding(fid: str, severity: str, kind: str, where: str, what: str, evidence: str, source: str = "static analysis") -> None:
    FINDINGS.append({"id": fid, "severity": severity, "kind": kind, "where": where, "what": what, "evidence": evidence, "source": source})


def provider_fact_sets() -> dict[str, set[str]]:
    """The fact names the game really provides, per conversation context (computed by calling the providers on a live world)."""
    import _nh as nh
    from wizard_rts.narrative import conversation, ledger, mortality, mother, pests, residents, tutorial

    w = nh.world(unlock=True)
    nh.adv(w, 5)
    seat = mortality.me(w)
    led = set(ledger.facts(w, seat))
    sp = None
    for kind, table in (("worker", w.workers), ("carrier", w.carriers), ("unit", w.units)):
        for eid, row in sorted(table.items()):
            if row["faction_name"] == "Red":
                sp = conversation.resolve(w, eid)
                break
        if sp:
            break
    occ_facts = set(conversation._ctx(w, sp)[1]["facts"])
    t = tutorial.state(w)["teacher"]
    res_t = set(conversation._ctx(w, conversation.resolve(w, t))[0]["facts"])
    from _party import Table

    tb = Table(humans=1)
    mom = mother.pid_of(tb.world, tb.people[0].id)
    with tb.people[0].seat_state():
        res_m = set(conversation._ctx(tb.world, conversation.resolve(tb.world, mom))[0]["facts"])
    keeper = next(k for k, v in residents.table(w).items() if v["role"] == "keeper")
    res_k = set(conversation._ctx(w, conversation.resolve(w, keeper))[0]["facts"])
    return {"ledger": led, "occupation": occ_facts, "teacher": res_t, "mother": res_m, "keeper": res_k, "scene": led | {"lessons_done", "mira_present"}}


def ledger_keys_bumped() -> set[str]:
    keys = set()
    for p in list((HYBRID / "wizard_rts").rglob("*.py")):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        keys |= set(re.findall(r'ledger\.bump\([^,()]+,\s*"([a-z_]+)"', txt))
        keys |= set(re.findall(r'ledger\.bump\([^,()]+,\s*f?"?([a-z_]+)"?\s*,', txt))
        keys |= set(re.findall(r'"trial_(?:entries|champion|betrayals|mercies|haste|wits|riddles_right|declared_unprepared)"', txt))
    for p in DIALOGUE.glob("*.json"):
        keys |= set(re.findall(r'"kind":\s*"ledger",\s*"key":\s*"([a-z_]+)"', p.read_text(encoding="utf-8")))
    return {k.strip('"') for k in keys}


def main() -> None:
    inv = load_json(GEN / "inventory.json")
    setters = {tuple(k.split("::")): v for k, v in inv["setters"].items()}
    readers = {tuple(k.split("::")): v for k, v in inv["readers"].items()}
    fact_set = inv["fact_setters"]
    fact_read = inv["fact_readers"]
    providers = provider_fact_sets()
    bumped = ledger_keys_bumped()

    # 1. flags read but never set
    n = 0
    for (tpl, flag), who in sorted(readers.items()):
        if (tpl, flag) not in setters and flag not in ENGINE_FLAGS.get(tpl, set()) and not flag.startswith("done:") and flag not in ("done",):
            n += 1
            finding(f"S-FLAG-READ-{n:02d}", "high", "Condition that can never be satisfied", f"{tpl}", f"Flag ‘{flag}’ is tested but nothing in the data or engine ever sets it.", "; ".join(sorted(set(who))[:4]))
    # 2. flags set but never read
    n = 0
    for (tpl, flag), who in sorted(setters.items()):
        if (tpl, flag) not in readers and not flag.startswith("done:"):
            n += 1
            finding(f"S-FLAG-UNUSED-{n:02d}", "low", "Flag that nothing reads", f"{tpl}", f"Flag ‘{flag}’ is set but no line, choice or quest rule ever tests it.", "set by " + "; ".join(sorted(set(who))[:3]))
    # 3. learned facts nothing reads (data + python)
    py_reads: dict[str, list[str]] = defaultdict(list)
    for p in (HYBRID / "wizard_rts").rglob("*.py"):
        txt = p.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r'knows_fact\([^,]+,\s*"([a-z_]+)"', txt):
            py_reads[m.group(1)].append(rel(p))
    n = 0
    for fid, who in sorted(fact_set.items()):
        if fid not in fact_read and fid not in py_reads:
            n += 1
            finding(f"S-FACT-UNUSED-{n:02d}", "medium", "Learned fact that nothing reads", fid, f"The wizard ‘learns’ {fid}, but no condition, check or rule ever uses it.", "learned in " + "; ".join(sorted(set(who))[:3]))
    for fid in sorted(set(py_reads) | set(fact_read)):
        if fid not in fact_set and fid not in {"manticore_hates_light", "diamond_is_cold", "bloodbeast_hates_vine", "dwarf_map", "champion_of_the_trial"}:
            finding(f"S-FACT-NEVER-{fid}", "high", "Condition that can never be satisfied", fid, f"Fact ‘{fid}’ is tested but never learned anywhere.", "; ".join(sorted(set(fact_read.get(fid, []) + py_reads.get(fid, [])))[:3]))
    for fid in ("dwarf_map", "champion_of_the_trial"):
        if fid not in py_reads and fid not in fact_read:
            finding(f"S-FACT-UNUSED-{fid}", "low", "Learned fact that nothing reads", fid, f"The wizard learns ‘{fid}’ in the Trial, but nothing tests it (it is a record only).", "trial/events.py")

    # 4. fact names a conversation never receives
    ctx_for_tpl = {"tutorial": providers["teacher"], "mother": providers["mother"], "warehouse": providers["keeper"], "trial_gate": providers["teacher"],
                   "forest_dispute": providers["occupation"], "smith_dispute": providers["occupation"], "ranger_patrol": providers["occupation"],
                   "occupations": providers["occupation"], "aftermath": providers["occupation"], "campaign_scenes": providers["scene"]}
    n = 0
    seen = set()
    for src in sorted((DIALOGUE).glob("*.json")):
        raw = src.read_text(encoding="utf-8")
        tpl = src.stem
        for m in re.finditer(r'"name":\s*"([A-Za-z_]+)"', raw):
            name = m.group(1)
            if (tpl, name) in seen:
                continue
            seen.add((tpl, name))
            allowed = ctx_for_tpl.get(tpl, set())
            if name in allowed:
                continue
            if name.startswith("my_") and name[3:] in providers["ledger"]:
                continue
            if name in bumped or name.replace("my_", "") in bumped:
                continue  # a ledger key that is counted only after the first event (absent = false): fine
            n += 1
            finding(f"S-FACTNAME-{n:02d}", "high", "Condition that can never be satisfied", src.name, f"Fact ‘{name}’ is tested in {src.name} but this conversation is never given it.", f"provided here: {len(allowed)} names; ‘{name}’ is not among them")
    # 5. variants shadowed by an unconditional earlier variant; duplicate ids; same-text buttons
    for tpl, conv in TEMPLATE_CONV.items():
        data = load_json(DIALOGUE / f"{tpl}.json")
        for sp, spec in data["speakers"].items():
            for nid, node in spec["nodes"].items():
                vs = node.get("variants", [])
                for i, v in enumerate(vs[:-1]):
                    if not v.get("when"):
                        finding(f"S-SHADOW-{tpl}-{sp}-{nid}-{i}", "medium", "Dialogue unreachable", f"{tpl}/{sp}/{nid}", f"Entry {i + 1} of {len(vs)} has no condition, so the {len(vs) - i - 1} later entries can never be spoken.", "")
                ids = [c["id"] for c in node.get("choices", [])]
                for d in {x for x in ids if ids.count(x) > 1}:
                    finding(f"S-DUPID-{tpl}-{sp}-{d}", "medium", "Duplicate identifier", f"{tpl}/{sp}/{nid}", f"Two choices share the id ‘{d}’; only the first can ever be chosen.", "")
                by_text: dict[str, list[dict[str, Any]]] = defaultdict(list)
                for c in node.get("choices", []):
                    by_text[c["text"]].append(c)
                for text, cs in by_text.items():
                    if len(cs) > 1:
                        finding(f"S-SAMETEXT-{tpl}-{sp}-{cs[0]['id']}", "medium", "Identical buttons", f"{tpl}/{sp}/{nid}", f"Choices {', '.join(c['id'] for c in cs)} all read “{text}”; they can be offered together unless their conditions exclude each other.",
                                json.dumps([c.get("when") for c in cs], ensure_ascii=False)[:300])
    # 6. `once` on topics
    for src in ("occupations", "aftermath"):
        d = load_json(DIALOGUE / f"{src}.json")
        topics = []
        if src == "occupations":
            topics = [t for r in d["roles"].values() for t in r["topics"]] + d["shared_topics"]
        else:
            topics = d["topics"]
        for t in topics:
            if t.get("once"):
                finding(f"S-ONCE-{t['id']}", "medium", "Setting that is ignored", f"{src}.json topic ‘{t['id']}’", "The topic is marked ‘once’, but everyday topics are not checked for ‘once’ (only graph choices are).",
                        "wizard_rts/narrative/occupations.py has no handling of the ‘once’ key")
    # 7. checks that cannot fail for a fresh apprentice
    for ck in inv["checks"]:
        if ck["fresh_result"] == "passes" and ck["has_fail_branch"]:
            finding(f"S-CHECK-{ck['id']}", "medium", "Skill check without a reachable failure", ck["id"], f"{ck['aspect']} check ‘{ck['text'][:60]}’ needs {ck['threshold']}; a fresh apprentice already has {ck['total_fresh']} (score {ck['start_score']} + guaranteed evidence {ck['evidence_guaranteed']} + regard {ck['relationship_band']:+d}). Aspects never go down, so the failure lines cannot be reached unless regard falls below −24.",
                    "fail lines: " + (ck["fail_lines"][:120] or "(none)"))
    # 8. regard changes vs bands: where a ‘relationship’ condition exists
    for src in sorted(DIALOGUE.glob("*.json")):
        raw = src.read_text(encoding="utf-8")
        cnt = len(re.findall(r'"relationship":\s*\{', raw))
        if cnt:
            finding(f"S-REGARD-{src.stem}", "info", "Where regard is read", src.name, f"{cnt} condition(s) read the speaker's regard for you; every other regard change is only visible through the ±25 bands used by skill checks.", "")
    worldview_cond = sum(len(re.findall(r'"player_worldview"', p.read_text(encoding="utf-8"))) for p in DIALOGUE.glob("*.json"))
    aspect_cond = sum(len(re.findall(r'"aspect":\s*\{\s*"id"', p.read_text(encoding="utf-8"))) for p in DIALOGUE.glob("*.json"))
    finding("S-WORLDVIEW-UNREAD", "medium", "Decision that changes nothing visible", "your worldview scores", f"Your answers add to seven worldview scores, and the engine can test them (player_worldview), but {worldview_cond} lines in the data do. The scores are shown in the journal snapshot only.",
            "data/narrative/dialogue/*.json contains no ‘player_worldview’ condition")
    finding("S-ASPECT-COND-UNREAD", "info", "Engine feature never used", "aspect conditions", f"The engine can hide a line unless an Aspect is at least N; {aspect_cond} lines use it. Aspects matter only through checks.", "")
    # 9. aspects never decrease
    neg = 0
    for src in DIALOGUE.glob("*.json"):
        for m in re.finditer(r'"kind":\s*"aspect"[^}]*"delta":\s*(-?\d+)', src.read_text(encoding="utf-8")):
            if int(m.group(1)) < 0:
                neg += 1
    finding("S-ASPECT-NEVER-DOWN", "info", "Rule", "Aspect scores", f"{neg} effects lower an Aspect. Scores only rise (Reason +1 in the Granite quest, Resolve +1 for beating the stranger), so a check that passes at the start can never become failing.", "")
    # 10. placeholders
    ok_names = {"name", "mentor", "attacker", "settlement"}
    n = 0
    for tpl in list(TEMPLATE_CONV) + ["campaign_scenes", "occupations", "aftermath"]:
        raw = load_json(DIALOGUE / f"{tpl}.json")
        cast = set()
        for role in (raw.get("cast") or {}):
            cast |= {role, role + "_role", role + "_where"}
        if tpl == "tutorial":
            cast |= {"cutter", "planter", "witness", "cutter_where", "planter_where", "witness_where", "cutter_role", "planter_role", "witness_role"}
        allowed = ok_names | cast | ctx_for_tpl.get(tpl, providers["occupation"]) | {"minutes_since_complaint", "killed_total", "eaten_total", "pests_left", "pests_total", "child", "victim", "previous"}
        text = json.dumps(raw, ensure_ascii=False)
        for tok in sorted(set(re.findall(r"\{([a-z_]+)\}", text))):
            if tok not in allowed:
                n += 1
                finding(f"S-PLACEHOLDER-{n:02d}", "medium", "Placeholder nobody fills", tpl + ".json", f"Placeholder {{{tok}}} appears in the text but is not provided to this conversation (it would print as ‘...’).", "")
    (GEN / "static_findings.json").write_text(json.dumps(FINDINGS, ensure_ascii=False, indent=1), encoding="utf-8")
    sev: dict[str, int] = defaultdict(int)
    for f in FINDINGS:
        sev[f["severity"]] += 1
    print(f"{len(FINDINGS)} static findings", dict(sev), "->", rel(GEN / "static_findings.json"))


if __name__ == "__main__":
    main()
