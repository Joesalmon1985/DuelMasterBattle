# E36B local dialogue generation vertical slice

This development-time pipeline reads the canonical 112-story workbook, extracts one cast, groups reusable dialogue situations, asks the local Ollama `mistral` model for seven worldview replies plus NPC reactions, validates/reviews them, persists progress in SQLite, and exports approved JSON/CSV.

It does **not** add Ollama to the Godot runtime.

## Commands

From the repository root in PowerShell:

```powershell
& ".\Run Dialogue Factory.bat" doctor
& ".\Run Dialogue Factory.bat" ingest --cast-id E36B
& ".\Run Dialogue Factory.bat" status --cast-id E36B
& ".\Run Dialogue Factory.bat" generate --cast-id E36B
& ".\Run Dialogue Factory.bat" status --cast-id E36B
& ".\Run Dialogue Factory.bat" review --cast-id E36B
& ".\Run Dialogue Factory.bat" export --cast-id E36B
```

The canonical E36B source has 12 Dialogue Matrix rows and 41 response-beat instances: 3 decisions, 3 after-A, 3 after-B, 9 openings, 12 normal endings and 11 non-dead tragic endings.

The generator intentionally treats each contextual beat separately before semantic bank classification. E36B contains repeated source utterances spoken by NPCs with different personalities; text equality alone is therefore not enough to force the same generated exchange.

## Resume behaviour

SQLite commits bank assignments and generation results bank-by-bank. Approved banks with the same model, prompt version, worldview version and source fingerprint are skipped on rerun. Interrupted `generating`/`reviewing` statuses are recovered to `pending` at startup.

## Output

A complete approved export creates:

- `generated/dialogue/E36B.json`
- `generated/dialogue/E36B_review.csv`

Export refuses to write a supposedly complete story while any bank is not approved.

## Tests

```powershell
$env:PYTHONPATH = "$PWD\tools"
.\.venv\Scripts\python -m pytest tools\dialogue_generation\tests -q
```

The tests do not require a live LLM. `doctor` and `generate` are the live local-Ollama checks.
