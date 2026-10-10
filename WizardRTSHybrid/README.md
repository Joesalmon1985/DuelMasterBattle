# WizardRTSHybrid

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
