# Plan: organic growth, age renewal and the shared Pandemic campaign

**Owner brief:** "God World: organic growth, age renewal and Pandemic" (24 Oct 2026, pasted), on the living-villages build at `0b627f43`. The brief's
screenshot was not attached; the headed captures of `0b627f43` are the before reference. **Decisions:** D48 to D56 in `docs/DECISION_REGISTER.md`
section 9. **Ledger:** "Renewal, growth and Pandemic" in `docs/ledger/GOD_WORLD_PROGRESS.md`.

## 1. What changes, in one paragraph each

**Renewal.** At every real age boundary (after the carry-over ranking, which uses the old tokens) the 28 productive number tokens are reshuffled with
their own saved RNG under the no-adjacent-6/8 rule; roles, deserts, graph, terrain and bindings never change. The revision number invalidates every
capacity, label and layout cache. Retired villages keep a frozen picture of what they actually built (hub, workshops, belts, streets); they produce,
claim and reserve nothing; a new settlement on the node supersedes the frozen pieces its own buildings cover, never drawing two hubs.

**Organic growth.** A village begins with a hub under construction and one seed producer per productive adjacent region, plus a small village-wide
allowance for a first processor. Each successful matching roll unlocks one further development place in that district (a receipt per epoch, roll,
village and region makes it once), up to `pips x level`; the next building is the next step of the district's mixed sequence (producer, support,
processor, second producer, ...), never producer spam. Every building passes through one saved lifecycle, PLANNED, RESERVED, FOUNDATION, BUILDING,
COMPLETED, worked by a bounded crew that walks to the site; nothing operates before it is complete. Cities raise the cap without filling it.

**Space and sight.** The command centre loses its grey rectangle for a terrain-blended apron; the modern age gets conveyor routes from drills to its
processors (trucks keep the hub runs); the island is the map resampled to 384 x 384 with coast and slope transitions smoothed and the embedding rebuilt
at twice the node separation, validated for clearance.

**Pandemic.** A contained `god_world/pandemic/` package: the published core rules (four actions, two draws, hand limit, escalation with the discard
shuffled onto the top, the rate track, outbreaks once per location per card chain, four countermeasures to win, eight outbreaks, an empty reserve or
an empty player deck to lose) adapted to the 80 strategic nodes, six manufactured responders with the six published roles, four threat families as
hostile formations in era art with enemy livery, and a cooperative coordinator that reads only public state. One responder turn every 20 game seconds
on the same clock. Advancing an age needs one faction at 10 VP and the campaign won, in either order; a loss pauses the run for a retry from the age's
checkpoint or a new world.

## 2. Improvements to the brief

1. **Commissioning, not re-planning.** The planner still lays out the whole eventual network as a blueprint (so belts, pipes and streets are routed
   once and stay stable); growth only commissions the next slot of a district. Ids never change as a village grows, which keeps labels, saves and the
   frozen histories simple.
2. **One construction lifecycle for every age** (hub, workshops, machines, posts), with native Widelands build art where the roster has it and a
   footprint-and-reveal fallback otherwise, drawn by the same code path.
3. **The campaign reuses the world's graph and units.** Locations are nodes, movement follows corridors, responders are units of the existing garrison
   system with a role marker, formations are unit records with family and location; no second world, no legacy catastrophe service.
4. **Coordinator before art.** The rules and the coordinator are tested headless on the 80-node scenario (wins and losses) before any troop is drawn.
5. **Honest corpora.** An economy-only corpus keeps the strategic regression; a combined corpus reports each age's campaign result and never forces
   a win.

## 3. Stages and evidence

| Stage | Deliverable | Evidence | Status (24 Oct 2026) |
| --- | --- | --- | --- |
| 1 Renewal and history | reshuffle transaction, revision, frozen historical villages, build-over supersession | `test_god_world_renewal.py` (P01 to P04) | done; a headed capture of a real boundary is still open |
| 2 Organic construction | development slots and receipts, mixed sequences, construction lifecycle with crews, processing in every age | `test_god_world_growth.py` (P05 to P09); `headed_ages/age2_village_close.png` | done |
| 3 Space and sight | apron, age-3 belts, 384 x 384 embedding | `test_god_world_embedding.py` (2x), `headed_ages/age3_village_close.png` | done (no device figures) |
| 4 Pandemic core | rules, decks, scenario, coordinator | `test_god_world_pandemic.py` (P15 to P21) | done; the coordinator wins about a third of crises |
| 5 Realisation | responders manufactured, formations drawn, march and effects | `headed/11_campaign_formation.png`, `12_campaign_label.png` | done |
| 6 Gate | combined age gate, loss and retry, HUD panel, corpora | `test_god_world_gate.py` (P22 to P24), `corpus_economy.json`, `corpus_combined.json` | done |

The ledger's "Renewal, growth and Pandemic" section carries the P01 to P24 table, the corpora and the honest limits.
