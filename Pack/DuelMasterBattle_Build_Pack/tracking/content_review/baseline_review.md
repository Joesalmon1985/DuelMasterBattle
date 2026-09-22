# Baseline dialogue review (T137)

**Corpus:** `godot_project/content/source/dialogue/baseline/g08_baseline.json` (+ production top-level)
**Compiled:** `godot_project/content/compiled/dialogue/baseline_pack.json`
**Integrity:** `python3 -m tools.content.validate --include-baseline --integrity`

## Stratified sample reviewed

| Slice | Observation |
|---|---|
| shortage / prehistoric / worker | Distinct cause language; offer choices have outcomes |
| military / historic / soldier | Raid vs deserter causes differ |
| discovery / modern / watch | Signal vs ruin map not rename-only |
| conflict / future / leader | Water rights vs labour strike trade-offs |
| dead_target / displaced / world_resolved / full_cycle | Truthful absent/late wording; no UNKNOWN_FACT leaks |
| rival samples (4) | Distinct strategies; no hidden-secret reads |

## Remaining quality flags

- Generated baseline lines are functional and unique; literary polish deferred to owner review.
- Aspect tags are coverage metadata on baseline lines (not G05 production bank).
- Repetitive structural brackets `[era/family/role/aspect]` are intentional for review tracing.

## Defects to optionally revise

- Human writing pass for tone consistency across eras.
- Replace semantic placeholder art when final assets arrive (G10 policy).
