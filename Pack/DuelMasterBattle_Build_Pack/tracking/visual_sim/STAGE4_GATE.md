# Stage 4 — Save/load + gallery

**Status:** PASSED  
**Date:** 2026-09-30  

- Independent field inventory (not to_dict-only) for formations/buildings/orders/units/battles/roads/people/carts/rng/ids/clock/player/research/tech_draft/diplomacy/leases/command_receipts.
- Seed nonempty research/tech_draft/diplomacy before snapshot.
- Restore via `WorldSim(state=WorldState.from_dict(...))` (router rebound); next Wait ACCEPTED.
- Gallery: `qa/visual_sim/contracts/gallery_selected.json` — capped, each entry labeled ARRANGED_STATE or PRODUCTION_JOURNEY.
