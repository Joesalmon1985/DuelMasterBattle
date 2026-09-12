# Dialogue Generation Factory — E36B vertical slice

## Status

Implementation is ready for the user's **local live-Mistral verification**.

Implemented:
- authoritative seven-worldview configuration with Python-owned score deltas;
- corrected Ollama structured-output payloads (`keep_alive` top-level, JSON Schema `format`, bounded malformed-JSON retries, model override, output-token limits);
- canonical workbook header validation and read-only Cast ID ingestion;
- E36B response-beat extraction;
- SQLite persistence with restart recovery;
- deterministic shortlist + Mistral semantic bank classification;
- seven-worldview writer, deterministic validation, reviewer and bounded repair;
- approved-only JSON/CSV export;
- `doctor`, `ingest`, `status`, `generate`, `review`, `export` CLI commands.

Verification performed without access to the user's local Ollama:
- Python test suite: 15 passed;
- source files compile successfully;
- canonical workbook E36B: 12 source rows, 41 response-beat instances, 3 consequential decisions;
- real workbook CLI ingestion/status succeeded and was idempotent;
- fake end-to-end writer/reviewer/export pipeline passed.

Not yet verified by this implementation environment:
- a real generation request against the user's `http://127.0.0.1:11434` Mistral instance;
- the resulting E36B dialogue quality;
- interruption/resume during a real local-Mistral generation run.

## Local acceptance sequence

```powershell
& ".\Run Dialogue Factory.bat" doctor
& ".\Run Dialogue Factory.bat" ingest --cast-id E36B
& ".\Run Dialogue Factory.bat" status --cast-id E36B
& ".\Run Dialogue Factory.bat" generate --cast-id E36B
& ".\Run Dialogue Factory.bat" status --cast-id E36B
& ".\Run Dialogue Factory.bat" review --cast-id E36B
& ".\Run Dialogue Factory.bat" export --cast-id E36B
```

Do not start the other 111 stories until E36B output has been manually inspected.
