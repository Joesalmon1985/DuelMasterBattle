# Dialogue Generation Factory — Handoff Document

**Date:** 2026-09-10  
**Branch:** `puzzle-system-pass` (DuelMasterBattle repo)  
**Status:** Phase 0 — Inspection complete, ready for implementation

---

## Current State Summary

### What Was Investigated

1. **Reference Project (Glen's Game — `Joesalmon1985/Glen-s-game`)**
   - Ollama + Mistral integration confirmed working via `diagnostics.py`
   - API pattern: `http://127.0.0.1:11434` with `/api/tags` and `/api/generate`
   - JSON mode with `stream=false`, `format=json`, `num_ctx=4096`, `keep_alive=10m`
   - Temperatures: classifier=0.1, reviewer=0.1, writer=0.45
   - Launch pattern: `Play Puca.bat` → `.venv/Scripts/python.exe -m puca_dungeon.gui`

2. **Duel Master Battle Repository**
   - Location: `C:\Users\joesa\Documents\Cursor\DuelMaster\DuelMasterBattle`
   - Branch: `puzzle-system-pass` (has uncommitted changes)
   - Python prototype exists in `python_prototype/` (pytest-based tests)
   - No existing dialogue generation infrastructure
   - No `requirements.txt` — dependencies managed elsewhere

3. **Source Workbook Found**
   - File: `docs/Duel_Master_Battle_Village_Cast_Matrix_WORLDVIEW_DIALOGUE_PILOT_3_STORIES (1).xlsx` (829 KB)
   - This is a **pilot workbook** (3 stories), not the full 112-village workbook
   - Full workbook (`Duel_Master_Battle_Village_Cast_Matrix_Dialogue_COMPLETE_112.xlsx`) NOT found in repo

4. **Worldview Definitions — NOT FOUND in Repository**
   - The 7 worldviews (Monarchist, Anarchist, Religious, Guildist, Arcane, Druidic, Cracked) are **not defined** in any DMB docs
   - Only "Arcane" appears as a spell essence, not a worldview
   - **Gate 0 blocker**: Authoritative worldview definitions must be supplied before generation can proceed

5. **Existing Tools Conventions**
   - `tools/` contains Python scripts (build_pixel_assets.py, generate_draft_sprites.py, etc.)
   - Scripts use standard library + project-specific modules
   - Batch files for launchers (Play Duel Master Battle.bat, Play Puzzle Test Menu.bat)

---

## Files Changed During Investigation (Uncommitted)

| File | Status |
|------|--------|
| `godot_project/project.godot` | Modified |
| `godot_project/sim/world/items.gd` | Modified |
| 13 untracked files | New (puzzle test menu, QA images, pilot workbook) |

---

## Implementation Plan (Per Original Requirements)

### Phase 0 ✓ — Inspect Before Changing
**COMPLETE** — See findings above.

### Phase 1 — Create Generator as Isolated Tool
**TODO** — Create structure:
```
tools/
    dialogue_generation/
        __init__.py
        cli.py
        config.py
        ollama_client.py
        database.py
        workbook_reader.py
        normalize.py
        candidates.py
        classifier.py
        writer.py
        reviewer.py
        validator.py
        exporter.py
        prompts/
            classify_bank.txt
            write_exchange.txt
            review_exchange.txt
        tests/
Generate Village Dialogue.bat
docs/DIALOGUE_GENERATOR.md
```

### Phase 2 — Ollama Client
**TODO** — Implement reusable client with `check_service()`, `list_models()`, `model_ready()`, `generate_json()`, `generate_text()`

### Phase 3 — SQLite Persistence
**TODO** — Model: source_beats, dialogue_banks, bank_memberships, exchanges, reviews, jobs, runs, metadata

### Phase 4 — Workbook Ingestion
**TODO** — Read-only ingestion with provenance tracking

### Phase 5 — Exact Deduplication
**TODO** — Normalize + hash, collapse exact duplicates

### Phase 6 — Candidate Retrieval
**TODO** — SQLite FTS5/BM25 for deterministic shortlist

### Phase 7 — Semantic Classifier
**TODO** — Mistral judges bank membership (JSON mode)

### Phase 8 — Seven-Worldview Writer
**TODO** — Generate all 7 worldviews in one request (BLOCKED: needs definitions)

### Phase 9 — Deterministic Validation
**TODO** — Python-side structural checks before AI review

### Phase 10 — Mistral Reviewer
**TODO** — Independent review at low temperature

### Phase 11 — Resumable Batch Runner
**TODO** — Commands: doctor, ingest, dedupe, banks, generate, review, status, retry, export

### Phase 12 — Windows Launcher
**TODO** — `Generate Village Dialogue.bat` with menu

### Phase 13 — Unattended Operation Protections
**TODO** — Timeouts, retries, logging, CTRL+C safety

### Phase 14 — Export
**TODO** — CSV/XLSX (human) + JSON (game)

### Phase 15 — Tests
**TODO** — Mocked unit tests for all components

### Phase 16 — Real Integration Test (5 banks)
**TODO** — Pilot with actual Mistral

### Phase 17 — Larger Pilot (50 banks)
**TODO** — QA report, prompt tuning

### Phase 18 — Full Batch
**TODO** — Only after all gates pass

---

## Critical Blockers for Next Agent

1. **Worldview Definitions Missing** — The 7 worldviews (Monarchist, Anarchist, Religious, Guildist, Arcane, Druidic, Cracked) are specified in requirements but **do not exist in the DMB repository**. They must be provided as external configuration before Phase 8 can proceed.

2. **Full Workbook Not Present** — Only a 3-story pilot workbook exists. The complete 112-village workbook (`Duel_Master_Battle_Village_Cast_Matrix_Dialogue_COMPLETE_112.xlsx`) needs to be located or confirmed.

3. **No Python Environment** — No `.venv` exists in DMB repo. The Glen's Game venv is separate. A new venv or shared approach needs decision.

4. **openpyxl Not Installed** — Required for workbook reading. Must be added as dependency.

---

## Recommended Next Steps for Next Agent

1. **Create feature branch** for dialogue generation work (e.g., `feature/dialogue-generation-factory`)
2. **Resolve worldview definitions** — Ask user for authoritative definitions or locate them
3. **Locate full 112-village workbook** — Confirm path with user
4. **Set up Python venv** with `openpyxl`, `requests` (for Ollama), `pytest`
5. **Begin Phase 1 implementation** — Create tool structure and Ollama client
6. **Implement `doctor` command first** — Validate Ollama + Mistral connectivity before building further

---

## Key Reference Files to Study

- `/c/Users/joesa/Documents/Cursor/GlenGame/diagnostics.py` — Ollama health check pattern
- `/c/Users/joesa/Documents/Cursor/GlenGame/puca_dungeon/interpret.py` — LLM interaction pattern
- `/c/Users/joesa/Documents/Cursor/GlenGame/puca_dungeon/narrate.py` — JSON generation pattern
- `/c/Users/joesa/Documents/Cursor/GlenGame/Play Puca.bat` — Launcher UX pattern

---

## Git Commands to Preserve Work

```bash
# Stage and commit current investigation state (optional)
cd /c/Users/joesa/Documents/Cursor/DuelMaster/DuelMasterBattle
git add docs/DIALOGUE_GENERATOR_HANDOFF.md
git commit -m "docs: handoff document for dialogue generation factory implementation"

# Create feature branch for implementation
git checkout -b feature/dialogue-generation-factory
```

---

## Contact / Context

- User: Joe Salmon
- Primary repo: `Joesalmon1985/DuelMasterBattle` (core-mvp-duel branch is MVP)
- Reference repo: `Joesalmon1985/Glen-s-game` (working Ollama+Mistral)
- Ollama endpoint: `http://127.0.0.1:11434` (confirmed working)
- Model: `mistral` (confirmed available)