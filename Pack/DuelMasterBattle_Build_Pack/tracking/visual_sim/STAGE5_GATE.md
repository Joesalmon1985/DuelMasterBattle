# Stage 5 — Bounded multi-seed soak + clustering

**Status:** PASSED  
**Date:** 2026-09-30  
**Platform:** Linux; Windows not run  

- Seeds: 507–512 (fixed set).
- Both PRODUCTION_JOURNEY slices per seed; one retry with larger budget on miss.
- Failures clustered by `scenario|assertion|entity_kind`; one representative packet per signature under `qa/visual_sim/out/soak_*/failure_packets/` (none on PASS).
- No LLM/Hermes calls; no passing screenshots exported to models.

```text
PYTHONPATH=. python3 -m pytest tests/sim/test_visual_sim_soak.py -q
```
