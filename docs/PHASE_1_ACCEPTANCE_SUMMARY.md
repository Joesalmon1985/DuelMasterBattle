# Phase 1 Manual Acceptance Summary — VillageQuestRunnerTry2

**Branch:** `VillageQuestRunnerTry2`  
**Commit tested:** `7a04e0db42a1c5c2f586b30be0450f060097c247`  
**Tester:** Fish  
**Date:** 2026-09-12  
**Decision:** **ACCEPT WITH DESIGN OBSERVATIONS**

## Automated verification

- Current automated tests pass.
- The game launches and behaves normally.
- No visible regression was found in normal play.
- Phase 1's deterministic world -> settlement profile -> production projection path is therefore accepted as the baseline.

## Manual acceptance conclusion

The settlement **data** is coherent enough to use as the canonical input for future village generation.

Representative examples from seed 5 / turn 30 show meaningful differences:

- forest/pasture settlements produce wood/wool and appropriate processing;
- field-heavy settlements produce grain and mills;
- mixed mountain/forest/pasture settlements expose ore/wood/wool and corresponding industries;
- uninfected pasture settlements can select `missing_flock`;
- infected settlements frequently select `tainted_well`;
- towns expose higher housing/development and additional civic functions such as halls, markets and gate towers.

The answer to the Phase 1 manual gate question is therefore:

> **YES — the reported settlement facts make sense as canonical facts from which a much richer playable village and local story can be generated.**

## Important design observation for Phase 2

The current **playable projection is not an acceptable final village representation**.

The production data contains useful economic, terrain, faction, infection and quest variation, but the projected settlements are still very small, highly templated spaces. In normal gameplay, entering a settlement does not yet feel like entering a coherent village or town.

This is not a reason to reject Phase 1. Phase 1 certified the *source facts*. It is the central problem Phase 2 must now solve.

### Phase 2 must therefore do more than expose the existing projection in Village Test Mode.

It must establish a reusable **large-village projection/generation layer** that:

- consumes the existing canonical `DmbSettlementProfile`;
- produces a substantially larger, navigable settlement layout;
- visibly reflects terrain, resources, industries, settlement/town scale, faction and civic development;
- places buildings and NPCs in coherent districts/relationships rather than fixed small slots;
- retains deterministic seed/node reproduction;
- still feeds the production `Overworld`;
- is testable through Village Test Mode using real production data;
- uses simple geometric placeholders where new visuals are needed;
- does not create a separate game/runtime path.

The first Phase 2 manual gate should therefore be visual and practical:

> **Can I launch 2–3 production-generated settlements in Village Test Mode, walk around them as John, and clearly see that they are larger, coherent places whose layouts and contents reflect their underlying simulated context?**

## Known non-blocking observation

Some projected mustered hero/unit NPCs currently have blank names. Record this for later correction if it remains visible in the expanded village system, but it does not block Phase 2.

## Deferred non-village note

Enemy ward configuration and training-battle settings would benefit from a separate gameplay-tuning guide later. This is useful documentation work but should not interrupt the village programme.

## Instruction to agent

**Phase 1 is accepted. Begin Phase 2 only.**

Treat the existing world simulation and settlement-profile facts as certified input.

Do not spend time re-auditing Phase 1 architecture unless a concrete implementation contradiction is found.

The primary Phase 2 product requirement is now explicit: replace the current tiny/template-like settlement representation with a substantially larger, deterministic, context-driven production village/town layout, and make that layout directly launchable through Village Test Mode for manual inspection.

Stop at the Phase 2 manual acceptance gate.
