# C09 — People, semantic knowledge and dialogue

Source: GDD §§34–56, 93–98, 124–145, 167–177. A worker is a persistent person, even when their sprite is not loaded.

## Classes

| Class / logical file | Public API / owned state |
|---|---|
| `PeopleService` / `sim/dmb/people/registry.py` | `create_person`, `assign_job`, `relocate`, `displace`, `record_death`, `promote_profile`; IDs, biography/relationships/roles |
| `JobService` / `people/jobs.py` | `vacate`, `backfill_tick`, `set_modifier`; job↔person uniqueness and replacement |
| `KnowledgeService` / `narrative/knowledge.py` | `observe`, `learn`, `public_context(observer,entity)`; known facts/testimony/evidence |
| `SemanticResolver` / `narrative/semantic.py` | `label`, `inspect`, `available_actions` from observed entity, range and knowledge |
| `AspectService` / `narrative/aspects.py` | `check`, `apply_change_once`, `retry_fingerprint`, `passive_comment` |
| `DialogueResolver` / `narrative/dialogue.py` | `start`, `choices`, `choose`, `close`; ephemeral session plus persistent check/effect outcomes |
| `LocalProjectionService` / `world/projection.py` | `project(node,manifest,knowledge)`; durable layout anchors/edits, disposable views |
| `SemanticLabelController` / `client/ui/semantic_labels.gd` | Focus/nearby labels, target hit regions, observes validated view tokens |
| `DialoguePresenter` / `client/ui/dialogue.gd` | Speech attached to speaker; formal choices pause; walking away closes safely |

`PersonState`: id, name, alive/status, affiliation, cultural appearance, role, job/workplace, home/current area/position, preferences (3 typed traits initially), goal IDs, relationship map, known facts, dialogue profile, history refs; optional leadership; optional active `unit_id` when serving as a combatant. Anchor/leader/worker are flags/roles on the same person, not duplicate identities. **Soldiers are Persons** with CombatantState in `state.units` (`person_id`). One active worker per building job by default. A job change preserves identity and creates a new replacement next accounting tick. Occupations are employment; carrying/working/waiting are activities. Never mint a Person only to animate a sprite. No ageing at era transition. Every visible living Person supports Observe and Talk (fallback dialogue allowed). See `docs/CANONICAL_GAME_ONTOLOGY.md`.

`KnowledgeFact`: id, subject, predicate, typed value, observer, source/evidence, learned time, valid context/version, kind=verified/testimony/interpretation. Testimony may be false; it must remain attributed. Passive Aspect interpretation never becomes verified world fact without an explicit evidence action.

## Projection and range

Create each area's stable layout once from world/node seed, then save persistent building anchors, exits, local objects and edits. Re-entering recreates sprites by entity ID; it never generates a new settlement, rerolls inhabitants or starts another quest engine. Expand the map if buildings need space; do not omit real structures to fit a fixed visual quota. Ensure exits, centre, NPC approach points and required items are reachable. Initial layout uses a 48×48-tile area, growing in 16-tile increments as needed; this is tunable presentation, not a world-size rule.

Local movement is Godot-authoritative; snapshots preserve position. Cross an exit only after acknowledged Travel. A target outside interaction range (baseline two tiles) can be observed; within range it offers valid context actions. Visible but unknown entities remain targetable. Unknown person → occupation → faction → name/detail depends on learned facts. A discovered map displays remembered information with age, not live omniscient enemy strength.

## G04 amendment — shared interaction path

G04 owns the minimum production integration of `SemanticResolver` labels, distant observation, nearby attached choices (Observe / Buff… / Destroy / Challenge as applicable), shared tile-range validation against synchronised poses, and one input router that separates UI choice, semantic target and ground movement. Public labels use knowledge-filtered names (e.g. `Red Skirmisher`); raw internal IDs are not ordinary player text. Omitted projection fields mean no update; explicitly empty authoritative collections mean remove. Clear caches on world/save change; reject stale replies. T079/T085 extend this path rather than replacing it.

Worker work/idle/carry cues follow real route and bottleneck status. **Carry is an activity**, not a Person kind: cue existing employees on active connections; never create presentation-only People. Movement obstruction changes animation only. Soldiers are Persons with CombatantState; they use actual collision/tactics and support Observe/Talk. Destroyed buildings and people must never reappear because a fresh view was built. Era upgrades reuse building anchors; displaced important objects move to a recorded accessible location.

## Seven Aspects

Reason, Empathy, Authority, Guile, Resolve, Curiosity, Wonder. Integer 0–5, initially 1. Quest effects ±1 clamped, applied once. Check = score + authored evidence modifier (normally 0–2) + relationship modifier (−1/0/+1) ≥ threshold (easy 2/demanding 4/exceptional 6). Define relationship storage −100..100; ≤−25 maps −1, ≥25 maps +1, otherwise 0. It is an implementation default reviewed at G05.

Failed check stores a fingerprint of relevant score/evidence/relationship/quest predicates. Reopening with the same fingerprint cannot reroll or repeat a consequence. Material changes permit retry; unrelated inventory changes do not. Passive comments read only the filtered context and are rate-limited by scene/cause/fact version. Each Aspect has a fallibility tag: Reason overlooks emotion; Empathy overtrusts; Authority overvalues legitimacy; Guile suspects too much; Resolve persists unwisely; Curiosity discounts danger; Wonder overinterprets patterns.

## Offline dialogue schema

`DialogueNodeDef`: id, schema version, speaker role/profile, context tags, condition AST, text key, safe variable declarations, optional Aspect interjection, choices (choice ID, text key, condition/check, typed effect IDs, next node), fallback key, tone and attribution tags. Runtime conditions use a small allowlist of operators: all/any/not, eq/gte/lte, has_knowledge, relationship_band, entity_status, quest_state, cause_active. No arbitrary code expression or generated patch.

Line selection: exact quest/stage/cause/role/era match → role/cause/era → role/state → neutral truthful fallback. Stable ID ordering resolves equal priority; seeded binding selects reusable variation once per context so reopening does not flicker. Variables are typed IDs resolved through the speaker/player knowledge view; missing variables select fallback, never raw placeholders. Escape display markup. A line may express belief only with explicit attribution; authoritative claims must be supported by predicates.

Approximately three choices visible at once; more are paged accessibly. Selecting a choice rechecks world/quest context and requests a typed transaction. Stale context refreshes choices with a short explanation. Pausing a conversation cannot grant a turn. Walking away commits no unchosen reward; ambient speech resumes Game Time.

Tests: persistent worker replacement, one person in two jobs rejection, collapse displacement, era identity continuity, hidden-name leakage, stale choice, retry fingerprint, missing-variable fallback, contradictory cause lines, and exactly-once Aspect reward. Human review separately judges voice, readability and whether the NPC's problem matters.
