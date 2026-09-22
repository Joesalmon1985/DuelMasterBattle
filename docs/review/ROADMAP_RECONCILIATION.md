# ROADMAP RECONCILIATION — G05 re-scope

**Baseline:** G01–G04 PASS; G05 `AWAITING_HUMAN` on `refactor/canonical-ontology-g05`; T097+ `NOT_STARTED`.  
**This document does not renumber tasks or clear gates.**

---

## G05 current definition (authoritative)

**Fully explorable Prehistoric world** — not the shortage quest.

| Requirement | Meaning |
|---|---|
| Board | 19 hexes / 54 nodes / 72 edges from normal world setup |
| LocalArea | Every ordinary strategic node → same size (48×48) |
| Projection | One `project_node` / `export_overworld_area` path |
| Travel | Graph-reachable; Travel +1 turn; reciprocal exits |
| Settlements | Shared projector; visit other faction cores |
| Quest | **None active** in baseline; frameworks retained |
| Stop | AWAITING_HUMAN; do **not** start T097 / G06 |

Archived prototype: `FX-VILLAGE-QUEST` + `content/source/quests/shortage/` + sluice dungeon content.

Human criterion:

> Starting inside a real settlement, I can walk out and explore the entire
> generated board. Every strategic node becomes a same-sized, persistent local
> area whose geography and population reflect the real board state.

---

## Sequence (unchanged numbering)

| Phase | Tasks | Gate | Intended player experience |
|---|---|---|---|
| P08 Living world presentation | T077–T096 | **G05** | Full Prehistoric board exploration via LocalAreas |
| P10 Immediate era transformation | T097–T106 | — | Capacity ranking, collapse/split, Historic conversion |
| P11 Integrated MVP | T107–T114 | **G06** | Two-era sandbox as one game |
| … | … | … | … |

T077–T096 historical task cards still mention shortage/demon/sluice. Those
implementations remain as **archived infrastructure**. Gate G05 acceptance no
longer requires playing that quest. Future narrative milestones may re-bind
quest content after the base world is enjoyable to explore.

---

## What automated G05 proves

- Topology 19/54/72; ≥2 core settlements; roads vs trails
- All 54 nodes same LocalArea size; exits match adjacency; reciprocal passages
- BFS Travel reaches all 54 nodes
- Baseline has no demon / sluice / factory_shortage bind
- G01–G04 regression smokes still pass

---

## Explicitly deferred

- Era transition (T097+)
- Re-enabling shortage quest as active content
- Place-naming polish / city density authoring
