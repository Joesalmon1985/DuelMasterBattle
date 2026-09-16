# C13 — Content production, art, audio and developer tools

Source: GDD §§124–153, 167–186, 193–212. Runtime consumes compiled local files. Authoring tooling may use an LLM offline but never becomes a gameplay dependency.

## Content schemas and compiler

Logical tools: `tools/content/validate.py`, `compile.py`, `make_batch.py`, `quality_report.py`. `ContentCompiler` API: `load_sources`, `validate_schema`, `resolve_references`, `validate_conditions`, `compile_manifest`, `report`. Source definitions/prose live under `content/source/`; compiled immutable packs under `content/compiled/`. Build writes a new pack, validates it and atomically switches the manifest. Preserve original IDs and source provenance.

`GenerationBatch`: id, requested templates/profiles/roles, known world/culture facts, allowed vocabulary/effects, variable types, examples, expected output schema, maximum lines, provenance and validator version. `GenerationResult`: batch id, definition IDs, lines/branches, source prompt hash and review status. Batches contain 25–50 lines for low-context authoring; do not request a 100,000-line monolith. Development agents can author output files directly; a paid API is not required by the compiler contract. If an API is later configured, cap cost/time explicitly and keep credentials out of shipped data.

Deterministic checks reject unknown IDs, duplicated effects, broken condition ASTs, wrong-era references, missing variables, unsupported facts, missing invalid-target routes, impossible prerequisites and unreachable mandatory outcomes. Knowledge validation builds observer views and attempts to render each line against allowed/disallowed fact sets. It cannot prove literary coherence: sample manual review remains necessary. Optional LLM critique consumes compiler reports and proposes edits without directly committing state or weakening checks.

## Data inventory and acceptance floor

| Pack | Required baseline |
|---|---|
| Resources/recipes | 5 Catan goods, 48 industrial raws, 240 unique cross-terrain processors/outputs from included catalogue |
| Buildings | 6 primary types + 3 factories + civic/warehouse per era; processor variants data-driven, not subclasses |
| Units/cultures | 3 military archetypes ×4 eras; one default all-recipe culture per era; workers/cart/wizard/rival/hazard actors |
| Technology | 6 per era, 24 total, explicit predecessor pairs and scopes |
| Quest templates | 2 each across 8 families: shortage, transport, catastrophe, diplomacy, military threat, personal, discovery, conflicting interests |
| Dungeon layouts | 8: cave, mine, sluice, temple, bunker, industrial works, alien site, machine complex; common persistent mechanisms |
| Recurring rivals | 4 profiles with distinct dialogue and legal deduction strategies/difficulty, all saved across relevant appearances |
| Dialogue | MVP ≥300 useful lines; full baseline ≥1,200, branch/role/era coverage first, not padded synonyms |
| Presentation | 4 era tile/building families, shared character/worker/unit animations, 5 hazard presentations, magic/duel/puzzle/UI effects and 4 audio palettes |

Resource and recipe JSON in this pack is reference input, not a claim that a runtime schema/compiler exists. Normalize the prior workbook's alternate display labels as documented in `reference/catalogue_notes.md`. Preserve distinct building/output names. Workbook gameplay-role metadata cannot introduce extra population/hunger/upkeep mechanics.

The full catalogue validator proves each era has 60 unordered pairs, every pair crosses terrains, each raw appears ten times, and all processor/output IDs are unique. Culture access includes all 60. Installation remains limited to useful local routes and delivered costs.

## Content variation requirements

Each quest template needs at least two supported interventions, a world-resolved outcome, a destruction/death/displacement contingency and era/full-cycle behaviour. Vary real causes, stakeholders and trade-offs. Do not create variation solely by renaming a mine. Across the two templates per family, one should include a conflict of interests or an explicit cost borne by another person/faction. All consequences remain typed and legal.

Every production building has a persistent anchor with role, preferences, goal and reactive fallback. Deep profiles are for recurring/important people; ordinary workers share reusable voices while retaining identity. Culture changes presentation without rewriting the person's remembered history.

Create a coverage grid by era × family × cause/status × speaker role. Lines tied to a remembered past event must distinguish past from current world facts. A collapse-displaced worker cannot claim an intact owned workplace unless the text is clearly a memory. Full cycle must not replace all person IDs to make new prose easier.

## Godot presentation contract

Logical scene root `client/main.tscn`: launcher/client service, local world root, player controller, focused semantic labels, speech/choices, transient contextual controls and pause screens. No permanent strategy-management HUD. Developer inspectors are accessible only in development builds or explicit debug mode.

Terrain 16×16 pixels, character baseline 16×24, four directions, integer 4× rendering with optional 3×/5×, scalable independent UI. Use 48-logical-pixel minimum pointer/touch hit areas. All actions must work with one pointer: move, observe/interact, choose, use/drop/give/equip, grimoire, target/cancel cast, Wait, pause, save/load and discovered map/history. No hover/right-click/keyboard-only essential action. Label only focused/nearby entities; use silhouettes and faction patterns/colours for groups.

Sprites reuse animation families: idle, four-frame walk, work, attack, hit, death/displacement and magic. Worker paths illustrate state; soldier paths affect tactics. Make legacy/new-era buildings distinguishable while preserving footprints and people. Responsive layout tests include 1280×720 and 960×540 desktop windows and a narrow touch-like viewport; actual Android packaging is deferred.

Audio buses: master, music, world, UI. Provide volume controls and mute persistence, subtitles/text equivalents for informational cues, local priority/rate limiting for alarms, reduced-motion options and non-colour cues. Full voice acting is excluded. Store provenance/licence/source for every imported/generated asset; missing rights or missing files block release. Placeholder shapes are acceptable only through prototype gates, not final readability acceptance.

## Developer tools

Use simple validated JSON forms and read-only graph views initially, not a general editor framework. Required screens: economy routes/constraints and cargo ledger; technology prerequisites; culture/era definitions; quest/dialogue graph with context preview; semantic knowledge inspector; puzzle layout/state/solution trace; era-plan before/after inspector; faction legal candidate scores/policy; catastrophe deck/cascade explanation. Edits target authoring files in a workspace, never arbitrary live save fields. Validate before compile/preview and record manifest changes.

Village test panel loads seed/fixture + content manifest through normal `WorldSim` and local projection. Controls reset scenario, replay commands, save failure bundle, select knowledge view and inspect cause/quest bindings. There must be no `TestQuestEngine` with independent logic. A fixture may set starting state; all subsequent outcomes use production commands.
