# Archived dialogue (not loaded in production)

`LineCatalog.load()` only reads top-level `content/source/dialogue/*.json`.

| Folder | Contents |
|--------|----------|
| `shortage/` | Retired factory-shortage / Mara / Route A–B / sluice lines |
| `aspect/` | Aspect-tagged experimental prose (requires explicit `aspect_id`) |
| `onboarding/` | Debug/onboarding instructional lines |

These remain available for FX-VILLAGE-QUEST regressions and history via
`LineCatalog.load(include_archive=True)` or `tools.content.validate --include-archive`.
