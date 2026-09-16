# C06 — Industrial flow and military manufacture

Source: GDD §§78–86, 93–103. Python is the sole economic owner. This is a capacity simulation, not physical ware-by-ware Widelands transport.

## Classes and records

| Class / file under `sim/dmb/industry/` | Responsibility / public API |
|---|---|
| `ResourceLayerService` / `layers.py` | Shared finite layer per hex/cycle/era; `create_layer`, `balance`, `consume_plan`, `restore_explicitly` |
| `PrimaryCapacity` / `primary.py` | `node_slots(numbers)`, `channels(building,view)`; uses best pip value, not sum |
| `RouteSelector` / `routes.py` | `candidates(factory,view)`, `select_installed_route`; chooses era-compatible real facilities/sources |
| `RateAllocator` / `allocation.py` | `solve(requests,constraints) -> AllocationPlan`; pure deterministic progressive filling |
| `FactoryService` / `factories.py` | Saved fractions/carries; `apply_allocations(plan,dt) -> completed_unit_requests` |
| `IndustryService` / `service.py` | Coordinates global 100 ms accounting, consumption and unit creation transaction |
| `IndustryProjection` / `projection.py` | Read-only rates, active route and bottleneck reason → visible work cues |

`LayerState`: hex_id, resource_id, era, cycle, finite_balance/carry, retired flag. Initially each finite resource has 600 extraction units; renewable resources have capacity without a balance. Old layers remain distinct. Resource names never determine compatibility.

`PrimaryBinding`: building_id, adjacent hex, layer era/cycle, finite channel and renewable channel. Each building provides both of its terrain's channels, 0.1 units/second each. Node capacity is best adjacent pips: 6/8→5; 5/9→4; 4/10→3; 3/11→2; 2/12→1. Cities double channel flow, not building slots.

`ProcessorBinding`: building_id, recipe_id, exact source channel ID for input A and input B, active/status/modifiers. Baseline binds each input to one eligible primary channel; different installed processors may use other channels. The selector can rebind to another eligible channel when available, but does not invent source pooling or import. Every valid route uses two different terrains in the same era and 1 unit of each input per output, capped at 0.1 output/second.

`FactoryRoute`: factory_id, processor_id, unit_def_id, processed_units_per_unit (2 skirmisher / 3 line / 5 heavy), requested weight (1 by default). One selected processor route per factory. Each of three factory slots caps at one unit/minute. Compatible legacy stock may be an explicit alternative input route only if it is a stored material, never a non-storable service.

## Constraint model

One request variable r[f] is manufactured units/second for a factory. Each route contributes `unit_cost × r[f]` processed output/second, the same amount to each raw input channel and to its finite layer if finite. Construct constraints for each factory ceiling, each processor, each channel, each shared finite layer and any explicit stock route. A finite layer capacity for this tick is remaining balance / 0.1 seconds, shared across every extracting node. A route with missing facility, wrong era, exhausted input, zero health, strike or source catastrophe requests zero with a reason.

Start active requests at zero. Increase `r[f]/weight[f]` equally until the minimum remaining-capacity / active-coefficient sum binds. Raise every active request by that increment, freeze all requests using a saturated constraint, then continue the rest. Positive weights and nonnegative coefficients only. Stable IDs order ties and carry allocation. Stop when all are frozen or satisfy their request ceilings. Use exact rational arithmetic for the allocation/carry path; quantize only when committing conserved quantities. Never round every factory independently upward.

The same route/rate code supplies theoretical ranking. That mode restores finite availability, removes temporary catastrophe/damage/buffs/cart blockage, and retains installed facilities, city status and permanent compatible tech. It does not mutate or refill the real deposit. Cache plans only while their structural inputs are unchanged.

## Numerical oracle

Three factories share one undamaged processor capped at 0.1 output/s, with plentiful primary inputs. Their conversion costs are 2, 3 and 5. Equal-weight max-min allocation gives each **0.01 unit/s**, since (2+3+5)×0.01=0.1. After 60 seconds their meters are **0.6 each**, with no completed units. After 100 seconds, each has completed one unit and meter 0: exactly **3 unique unit IDs**. Processor consumption is 10 of each raw input; one finite input beginning at 600 ends at 590. The 1/minute factory ceiling is not reached.

Two identical settlements sharing the same finite layer, with only 0.01 input left and otherwise unconstrained channels, must collectively consume exactly at most 0.01 in the next 100 ms. Their compatible output/progress is split fairly, not duplicated. Test both insertion orders. A 25%-health processor has capacity 0.025 output/s; the shared-route factory rates become 0.0025 each under otherwise identical conditions.

## Commit ordering

At each C02/C03 boundary apply accepted encounter damage/destruction first. Read current channels/routes. Solve all occupied nodes together; reserve shared finite usage; commit depletion, stock consumption and meter fractions atomically. For each meter crossing 1, create one unit via MilitaryService and subtract the completed integer count. Preserve overflow/remainder. Emit rates/shortage causes and unit IDs after commit. A locally active battle receives a versioned reinforcement, not a second spawn request from animation.

Ordinary vacant jobs are backfilled with new people on the accounting tick without reducing output. Worker pathfinding, the wizard's position, local render culling and industrial crate animations cannot affect accounting. Explicit strike/sabotage modifiers may. Source catastrophe blocks both raw channels and the separate matching Catan grant; it does not erase the finite deposit. Clearing the cause resumes from the same balance/meters.

Damaged buildings multiply their capacity by health/max health. Permanent tech applies after city/source baseline; source, processor and factory modifiers affect only their own stage. Do not multiply all three stages together into free output. Legacy primary/factory definitions stay in their layer; upgraded slots change binding in place and reset only the new-era factory meter. Extra legacy processors remain real.

## Catalogue and route defaults

The included 240 recipe records are normalized from the prior workbook, with GDD v0.3 resource names authoritative. Historical workbook columns such as Population supply are descriptive metadata; they do not introduce hunger, population consumption or technology costs. All processor outputs are eligible for baseline military supply.

MVP manifest enables all 15 renewable+renewable terrain pairs per implemented era and the Woodland-renewable/Ore-Mountains-finite route used by the shortage fixture: 16 per era. This ensures any cross-terrain node can bootstrap legally while preserving a finite-source example. Full manifest enables all 60 per era. Culture access references the full era catalogue even when the demonstration manifest enables a subset. Every raw type must appear ten times in the full catalogue.

Verify meter/deposit continuation across save/load, 60 seconds under varied render chunks, off-screen/visible equality, global shared scarcity, service non-storage, zero/one/five primary slots, destruction mid-boundary and legacy sources after transition. Do not write tests that assert worker animation arrival as a prerequisite for a unit.
