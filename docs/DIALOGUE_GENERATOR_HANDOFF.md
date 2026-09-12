# Dialogue Generator Handoff — Current State

**Repository:** Duel Master Battle  
**Updated:** 2026-09-12  
**Replaces:** the older pre-implementation `DIALOGUE_GENERATOR_HANDOFF.md`

## 1. Current status

The Dialogue Generator is no longer a proposed subsystem. A development-time Dialogue Factory is implemented under:

```text
tools/dialogue_generation/
```

The current vertical slice is E36B.

Do not rebuild the dialogue-generation architecture from scratch.

## 2. Existing pipeline

```text
canonical 112-story workbook
  -> workbook ingestion
  -> semantic bank classification
  -> seven-worldview dialogue writing
  -> deterministic validation
  -> reviewer / bounded repair
  -> SQLite persistence
  -> approved-only export
  -> fixture builder
  -> Godot village fixture data
```

The local model is accessed through Ollama. The current E36B design uses the local model only during development/content generation.

**Ollama is not a Godot runtime dependency.**

## 3. Important implementation files

```text
Run Dialogue Factory.bat

tools/dialogue_generation/
  cli.py
  config.py
  database.py
  exporter.py
  fixture_builder.py
  normalize.py
  ollama_client.py
  pipeline.py
  validator.py
  workbook_reader.py
  worldviews.py
  worldviews.json
  prompts/
  tests/
```

The canonical complete workbook is already present under `docs/`.

## 4. Persistence and repeatability

The factory uses SQLite to preserve progress.

Generation/review work is fingerprinted/versioned using relevant model/prompt/worldview/source information so accepted work can be reused and stale work can be deliberately regenerated.

Interrupted work has explicit recovery behaviour.

Retain this. Do not replace it with repeated stateless LLM calls.

## 5. Model authority boundary

The LLM generates language.

Python/Godot owns:

- canonical characters and IDs;
- story structure;
- story state;
- worldview score effects;
- quest completion;
- village/world state;
- items;
- outcomes and consequences.

Do not infer canonical game state from model prose.

## 6. Current acceptance status

Repository documentation records the following implementation-side verification for the E36B vertical slice:

- model-free Python tests;
- source compilation;
- canonical workbook ingestion;
- idempotent ingestion/status;
- fake end-to-end generation/review/export.

The key outstanding acceptance work is **local live-Ollama verification on the user's machine**, including manual review of the resulting dialogue quality.

Do not scale generation across the remaining stories until the E36B path has been accepted.

## 7. Existing local acceptance sequence

From the repository root:

```powershell
& ".\Run Dialogue Factory.bat" doctor
& ".\Run Dialogue Factory.bat" ingest --cast-id E36B
& ".\Run Dialogue Factory.bat" status --cast-id E36B
& ".\Run Dialogue Factory.bat" generate --cast-id E36B
& ".\Run Dialogue Factory.bat" status --cast-id E36B
& ".\Run Dialogue Factory.bat" review --cast-id E36B
& ".\Run Dialogue Factory.bat" export --cast-id E36B
```

Manual inspection follows.

## 8. Current Godot integration

Village fixtures live under:

```text
godot_project/content/village_tests/<profile>/
```

Each contains:

```text
village.json
cast.json
quest.json
dialogue.json
```

`VillageTestCatalog` validates and loads them.

`VillageQuestRunner` indexes dialogue semantically using:

```text
npc_id | quest_id | node_id | variant
```

This is a strong candidate for the permanent runtime dialogue key.

The E36B quest format is richer than the current production settlement quest UI and should inform the shared story/runtime contract.

## 9. Required integration work

The next work is not “make an LLM dialogue generator.”

It is:

1. converge the fixture story/dialogue format with the shared production story runtime;
2. make Dialogue Factory exports target that shared contract;
3. preserve approved-only deterministic exported content;
4. retain model-free tests for almost all dialogue integration;
5. run only a small number of real local-model calls at manual acceptance gates.

The generator should not have to know whether the consuming village was:

- authored;
- generated from a simulated world settlement;
- loaded in Village Test Mode;
- encountered through normal campaign play.

It should receive a stable canonical story/dialogue request or source pack and produce dialogue for stable semantic IDs.

## 10. Relationship to `village_test_dialogue.gd`

`VillageTestDialogue` currently provides a simple checked-in/user override JSON path and fallback lines.

That is useful development behaviour, but it is not the authoritative long-term story/dialogue architecture.

When the village paths are unified:

- keep a developer override mechanism if useful;
- keep safe fallback behaviour;
- route it through the same stable dialogue lookup contract;
- do not allow it to own quest state.

## 11. Testing policy

Run frequently without a live LLM:

```powershell
$env:PYTHONPATH = "$PWD\tools"
.\.venv\Scripts\python -m pytest tools\dialogue_generation\tests -q
```

Use fake responses for:

- valid output;
- malformed JSON;
- validation failure;
- reviewer rejection;
- repair;
- cache/reuse;
- interruption/recovery;
- export gating.

Real local-model generation is a phase-gate test, not a routine regression test.

## 12. Documentation ownership

Keep these documents aligned:

- `DIALOGUE_GENERATOR_STATUS.md` — concise current acceptance/status;
- `DIALOGUE_E36B_VERTICAL_SLICE.md` — how to run the pilot;
- `DIALOGUE_GENERATOR_HANDOFF.md` — this architecture/integration handoff.

Once the unified village/story runtime replaces the vertical-slice boundaries, update all three so they describe the real production data contract rather than preserving obsolete test-only architecture.
