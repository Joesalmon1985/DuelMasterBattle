# Architecture / ontology review (2026-09-21)

**Status:** READY FOR JOE DESIGN DECISIONS — not approved, not implemented.

**Checkout reviewed:** branch `feature/g05-village-quest`, HEAD `ff23066e76b6c950c5f76478d0597a44ba042291`, plus local uncommitted G05 UX/travel/projection work that is newer than remote.

**Hard stop:** Do not start T097, G06, era migration, or ontology refactor until Joe decides the items in [`JOE_DESIGN_DECISIONS.md`](JOE_DESIGN_DECISIONS.md).

## Documents

| Document | Purpose |
|---|---|
| [../CANONICAL_GAME_ONTOLOGY.md](../CANONICAL_GAME_ONTOLOGY.md) | **CANONICAL** ontology (Joe 2026-09-21) — required agent reading |
| [ONTOLOGY_IMPLEMENTATION_REPORT.md](ONTOLOGY_IMPLEMENTATION_REPORT.md) | Consolidation progress / migration table |
| [CURRENT_GAME_ONTOLOGY.md](CURRENT_GAME_ONTOLOGY.md) | Pre-consolidation snapshot (historical audit) |
| [PLAYER_WORLD_MODEL.md](PLAYER_WORLD_MODEL.md) | What the player should believe exists |
| [DESIGN_CONTRADICTIONS.md](DESIGN_CONTRADICTIONS.md) | Contradictions / ambiguities with evidence |
| [PROPOSED_CANONICAL_ONTOLOGY.md](PROPOSED_CANONICAL_ONTOLOGY.md) | Pre-decision proposal (superseded by CANONICAL) |
| [ENTITY_PRESENTATION_CONTRACT.md](ENTITY_PRESENTATION_CONTRACT.md) | Entity → projection → actor → verbs |
| [ROADMAP_RECONCILIATION.md](ROADMAP_RECONCILIATION.md) | G05 onward options (Option 1 accepted) |
| [JOE_DESIGN_DECISIONS.md](JOE_DESIGN_DECISIONS.md) | Decision register (accepted for consolidation) |

## Source classification used in this review

| Class | Meaning |
|---|---|
| `USER_LOCKED` | Explicit Joe / GDD locked decision |
| `USER_RECENT` | Recent Joe guidance or gate feedback |
| `BUILD_PACK_DEFINED_DEFAULT` | Contracts / BUILD_SEQUENCE defaults |
| `CURRENT_ARCHITECTURE` | Live Python+Godot ownership rules |
| `OLD_BUT_USEFUL` | Older doc with reusable intent |
| `STALE` | Contradicts current ownership; keep for history |
| `IMPLEMENTATION_ACCIDENT` | Exists in code without clear design intent |

## Related current docs

- [`../INTEGRATED_RUNTIME_ARCHITECTURE.md`](../INTEGRATED_RUNTIME_ARCHITECTURE.md) — current runtime ownership
- [`../../Pack/DuelMasterBattle_Build_Pack/AGENT_START_HERE.md`](../../Pack/DuelMasterBattle_Build_Pack/AGENT_START_HERE.md)
- [`../../Pack/DuelMasterBattle_Build_Pack/EXECUTION_AMENDMENTS.md`](../../Pack/DuelMasterBattle_Build_Pack/EXECUTION_AMENDMENTS.md)
