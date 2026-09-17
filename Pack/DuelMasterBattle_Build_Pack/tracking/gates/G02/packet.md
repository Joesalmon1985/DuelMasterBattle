# G02 playtest handoff — FX-CARGO factions, cargo and construction

**Status:** AWAITING_HUMAN (do not start T049)  
**Scenario:** FX-CARGO · **Seed:** 202  
**Tested revision:**   
**Save slot:** `g02_playtest` · recovery: `_recovery`

## Launch (verified)

```bash
cd /home/joe/Projects/DuelMasterBattle
bash tools/play_g02.sh --direct
```

Portrait default **450×800**. Economy debug panel shows warehouse/cart/order fields from the Python `economy` view (not release UI).

## Fixture

- Seed **202**
- Warehouse store + named cart from `fx_cargo` (see economy panel)
- Road N0–N1–N2; Place route block / Clear route block buttons use Interact (`place_route_block` / `clear_hazard`)
- Wait/Travel advances World Turns and cart movement (≤1 road edge/turn)

## Automated

- FX-CARGO scenario via `python3 tools/run_scenario.py --fixture FX-CARGO --seed 202` — PASS (`block_cleared`, in-transit cargo preserved)
- Tasks T038 / T045–T047 mapped checks — PASS
- Godot: `res://client/tests/run_g02_smoke.gd` → `G02_SMOKE_OK seed=202 cart=cart:1`
- Screenshots under `tracking/gates/G02/` and `screenshots/`

## 15–20 minute checklist

| Step | Expect |
| --- | --- |
| Launch portrait `--direct` | Economy panel lists store timber and cart id; wizard still moves on pad |
| Inspect warehouse + cart | Labels show real available/reserved/escrow and cart node/cargo |
| Place route block, Wait after cargo is assigned | Cart parks/blocked; goods remain on cart (no teleport) |
| Clear route block, Wait/Travel | Same cart resumes; cargo arrives at destination store |
| Construction | Settlement only after costs delivered to staging |
| Faction seats + tech | Full seat round yields one tech pick per faction (draft) |
| Save with cargo aboard (`g02_playtest`), reload | Same cargo lots / node / quantities |

**Experience question:** Can you see why goods and construction are delayed?

Reply `G02 PASS — <build/commit>` or `G02 FIX_REQUIRED — <symptom>`.

**Not claimed as human gate PASS.**
