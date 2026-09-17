# G02 playtest handoff — FX-CARGO factions, cargo and construction

**Status:** AWAITING_HUMAN (do not start T049)  
**Scenario:** FX-CARGO · **Seed:** 202  
**Tested revision:** `1223e3919845cbfe6b300235da415b1e2b508f8e`  
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
| **Start delivery** | Economy panel | Loads the **pre-reserved** haul; cart **walks to the exit** on Game Time (World Turn unchanged) |
| **Wait** | bottom bar | One World Turn / one faction seat; cart advances ≤1 road edge; departure plays at the exit |
| **Travel** (follow) | exit / action | Enter the next room; see entrance + onward walk (another seat also advances logistics) |
| **Block** / **Clear** | Economy panel | Place / clear route hazard on `node:2` |
| **Pause** / focus loss | bottom bar | Freezes Game Time and local cart motion together |
| **Save** / **Load** | bottom bar | Slot `g02_playtest` — mid-journey resume keeps progress (no replayed entrance) |

## Cart journey rule (presentation)

Python owns node, cargo and stock. Game-Time local walks never load, deliver, credit or advance turns. One legal road edge per World Turn. See contract `C05_logistics.md` § Local cart journeys.

## Suggested play sequence

1. Inspect warehouse + cart (✦). Note `delivery_res=reservation:fx-cargo-delivery` in Economy.
2. Optionally explore rooms and **Wait** — **Start delivery** must still work (reserved haul).
3. **Start delivery** → cargo loads; cart **visibly walks toward Exit · Road** while World Turn stays put.
4. **Wait** once → departure through the correct exit (or wait at exit if you Start without Wait).
5. **Follow** through the exit → corresponding entrance and onward movement on the next node.
6. **Block** → **Wait** → cart **blocked**, same cargo; **Clear** → **Wait** → resume.
7. Leave/re-enter or Save/Load mid-walk: no duplicate carts, no restarted entrance for an already-progressed leg.
8. Rapid **Wait** / **Pause**: transitions play once in order; logistics outcomes match whether the cart’s area is on-screen.
9. Tech: after **two** Waits (both seats), Economy shows **last picks**. Local walking alone never triggers picks.

## Screenshots / recording

| File | Notes |
| --- | --- |
| `screenshot_450x800.png` / `screenshot_wizard.png` | **450×800** |
| `screenshot_720x1280.png` | **720×1011** alias |
| `screenshot_1280x720.png` | **1280×720** |
| `screenshots/warehouse_cart.png` | yard + cart |
| `screenshots/blocked_route.png` | blocked label |
| `recordings/cart_journey.webm` | short actual gameplay: depart → cross → arrive |
| `recordings/depart_*.png`, `crossing.png`, `arrive_*.png` | still frames from the same capture |

Rebuild recording: `bash tools/capture_g02_cart_journey.sh` (uses `timeout` if hung on quit).

## Automated

- `python3 tools/check.py --gate G01` PASS
- `python3 tools/check.py --gate G02` PASS (includes G01 regressions + `run_g02_smoke.gd`)
- `pytest tests/sim/test_presentation_journeys.py` PASS
- Journey demo: `G02_JOURNEY_DEMO_OK` with `cart_visible=true`

Reply `G02 PASS — <build/commit>` or `G02 FIX_REQUIRED — <symptom>`.

**Not claimed as human gate PASS.** **T049 remains NOT_STARTED.**
