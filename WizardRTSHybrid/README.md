# WizardRTSHybrid

**One world, two ways to play.** Six factions (five Widelands tribes) run civilian economies on a square-grid terrain built from Widelands rules and maps, with OpenRA units, buildings, combat and ships on top. **God Mode** is an RTS over all six factions; **Wizard Mode** walks the same world as the DuelMasterBattle wizard, with the retained Ward Duel. Press G to switch; nothing resets. The Python simulation is the only world and also runs without Godot (`wizard_rts/sim_api.py`).

Quick start: `Play Hybrid God Mode.bat` / `Play Hybrid Wizard Mode.bat` (Windows), `scripts/launch_hybrid.sh god|wizard` (Ubuntu). Maps: `HYBRID_MAP=standard|small|large|wmf:The_Big_Lake|wmf:Egyptian_Mandala_v1.2`, seed `HYBRID_SEED`. Status and what is missing: `docs/STATE_OF_PLAY.md`; for the Windows machine: `docs/WINDOWS_HANDOVER.md`.

---

The original prototype description follows.

A continuous Overworld map with a Widelands-derived warehouse ledger and an OpenRA-derived damage step, plus the retained DuelMasterBattle duel.

The wizard is the existing Overworld avatar. Hex crossings do not reload a scene and do not spend a Travel or Wait turn. Economy and military advance on game time while the wizard walks or stands still. The duel pause token stops that clock.

## Run

1. `py -3 -m wizard_rts.server` from this directory. It listens on `127.0.0.1:8765`.
2. Open `res://client/scenes/hybrid_world.tscn` in Godot 4.5 with the Forward+ renderer.

`scripts/launch_hybrid.ps1` does both. `scripts/setup_external.ps1` recreates the gitignored source labs from `sources/manifest.json`.

## Tests

```
py -3 -m pytest WizardRTSHybrid/tests -q --ignore=WizardRTSHybrid/tests/test_five_minutes.py
py -3 WizardRTSHybrid/tests/test_five_minutes.py
```

The five-minute script is wall-clock time. The quick suite guards the same stock invariant with a direct `advance()`.

## Provenance

Stock add and remove follow Widelands `WareList` and `WarehouseSupply` at the commit in the manifest. Damage follows OpenRA `ApplyPercentageModifiers`, `DamageWarhead.InflictDamage`, and `Health.InflictDamage`. Carrier routes and soldier steps are provisional scaffolding. Those labels are on the world snapshot. See `docs/SOURCE_REUSE.md` and `docs/LICENSES.md`.

Play does not open `external/`.
