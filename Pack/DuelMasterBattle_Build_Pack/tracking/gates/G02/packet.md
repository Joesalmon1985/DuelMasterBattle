# G02 playtest handoff — FX-CARGO factions, cargo and construction

**Status:** AWAITING_HUMAN (do not start T049)  
**Scenario:** FX-CARGO · **Seed:** 202  
**Tested revision:** `6194c2c4c9389732fcf2570695a4650c1c26d2e3`  
**Save slot:** `g02_playtest` · recovery: `_recovery`

## Launch (verified)

```bash
cd /home/joe/Projects/DuelMasterBattle
bash tools/play_g02.sh --direct
```

Portrait **450×800**. Economy panel is collapsible top-right.

## Controls checklist

| Control | Where | Use for |
| --- | --- | --- |
| **D-pad** | bottom-left | Local walk (does **not** spend seats / tech picks) |
| **Observe / ✦** | bottom-right | Observe selected entity; Interact when in range |
| Approach + **✦** on **Timber Warehouse** | yard | Stock a/r/e for the real store |
| Approach + **✦** on **Hauler Cart** | yard | Cart id, phase (idle/travelling/blocked/delivered), cargo, dest |
| **Start delivery** | Economy panel | Loads the **pre-reserved** haul onto the cart |
| **Wait** | bottom bar | One World Turn / one faction seat; cart moves ≤1 edge |
| **Block** / **Clear** | Economy panel | Place / clear route hazard on `node:2` |
| **Save** / **Load** | bottom bar | Slot `g02_playtest` |

## Suggested play sequence

1. Inspect warehouse + cart (✦). Note `delivery_res=reservation:fx-cargo-delivery` in Economy (reserved haul survives exploration).
2. Optionally explore all three rooms and press **Wait** several times — **Start delivery** must still work.
3. **Start delivery** → cargo loads immediately; label becomes **Hauler Cart (travelling)**.
4. **Wait** once → cart advances one road edge (legitimate delay: move happens on strategic Wait/Travel, not the Start press).
5. **Block** → **Wait** → cart **blocked**, cargo retained.
6. **Clear** → **Wait** → resume → arrive at staging → construction commits only after goods land.
7. Tech: after **two** Waits (both seats), Economy shows **last picks** for `faction:1` and `faction:player`. Local walking alone never triggers picks.

## Screenshots (actual capture sizes)

| File | Size |
| --- | --- |
| `screenshot_450x800.png` / `screenshot_wizard.png` | **450×800** |
| `screenshot_720x1280.png` (clamped alias of `720x1011`) | **720×1011** |
| `screenshot_1280x720.png` | **1280×720** |
| `screenshots/warehouse_cart.png` | **450×800** |
| `screenshots/blocked_route.png` | **450×800** (`Hauler Cart (blocked)`) |

## Automated

- `python3 tools/check.py --gate G02` PASS
- Explore/Wait-then-Start, double-Start conservation, inspect bind, tech-after-full-round covered in pytest + `run_g02_smoke.gd`

Reply `G02 PASS — <build/commit>` or `G02 FIX_REQUIRED — <symptom>`.

**Not claimed as human gate PASS.**
