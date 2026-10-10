# OpenRA system map

Source pin: bleed `e7e9e4ad270221d7fb9725b348c75504d48c1ebd`. Licence GPL-3.0-or-later.

Built on this machine with `dotnet build OpenRA.slnx -c Debug` (.NET SDK 10.0.401). `dotnet test OpenRA.Test` passed 508, skipped 2. The game window was not left running as a played skirmish. See `docs/original_runs/OPENRA.md`.

## Damage (traced, ported)

| | |
| --- | --- |
| Entry | `DamageWarhead.InflictDamage` |
| Files | `OpenRA.Mods.Common/Warheads/DamageWarhead.cs`; `OpenRA.Mods.Common/Util.cs` `ApplyPercentageModifiers`; `OpenRA.Mods.Common/Traits/Health.cs` `InflictDamage` |
| Types | warhead, health trait, percentage modifiers |
| Upstream | Versus values are percentage modifiers. `ApplyPercentageModifiers` multiplies with `decimal` and truncates toward zero via `(int)`. Health clamps to `0..max_hp`. A dead actor (`hp <= 0`) takes no further damage in the port. |
| Sim tick | OpenRA's world tick was not hosted. The hybrid calls the port from `military_quantum`. |
| State write | Actor HP in OpenRA. The port returns the new HP integer. |
| Visible result | Not observed in an OpenRA skirmish. `tests/test_openra_damage.py` checks the arithmetic. |
| Existing test | `OpenRA.Test` includes `OrderTest` and `CoordinateTest` among 508 passing tests. There is no standalone warhead integration test in that assembly. |
| Reuse | Source-derived adapted port in `wizard_rts/openra_damage.py`. |
| Coupling | The original `InflictDamage` searches actors and hit shapes in the OpenRA world. The port drops that search and applies one integer to one HP value. |

## Order, path, and AI (not executed)

| Pathway | What was read | Why it is not in the hybrid |
| --- | --- | --- |
| Order generator | Orders are the engine's command objects. `OrderTest` passed inside `OpenRA.Test`. | Issuing an order needs a mod, an actor, and the world. |
| Locomotor and pathfinder | `OpenRA.Mods.Common/Pathfinder/PathFinder.cs` `FindPathToTargetCell` | It takes the OpenRA cell world, locomotor, and actor map. OpenRA cells are square. The hybrid soldier step is a Manhattan step and is marked provisional scaffolding. |
| Target acquisition | Weapon and attack traits | Not called. The hybrid attacks when two soldiers are one tile apart. |
| Death | Health reaching zero removes or changes the actor in OpenRA | The hybrid sets `alive` false. It does not run OpenRA's death types. |
| Military AI | Modular bot modules | Not called. An `ai_military` event on a fixed quantum is not the OpenRA bot. |

## Mod SDK

Pin: master `df103939c7e472e715b9fce7cbaf7e35b54dc037`. `make.ps1` fetches the engine named in `mod.config` (`ENGINE_VERSION`, currently `release-20250330`) into the SDK's engine directory and builds the example mod with `dotnet build`. A mod adds rules, weapons, and sequences as data plus optional assemblies. It does not require a fork of the engine. The example mod build result is in `docs/original_runs/OPENRA_MOD_SDK.md`.
