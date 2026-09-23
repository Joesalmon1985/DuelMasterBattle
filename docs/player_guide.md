# Duel Master Battle — Player Guide (G10 functional baseline)

**Build scope:** Functionally complete **placeholder-art** baseline.
Semantic placeholders are permitted; finished production art is deferred.

## Launch (Linux)

From a checkout with Godot 4.4.1 available:

```bash
bash tools/play_g10_release.sh
# or
bash tools/play_mvp.sh
```

Windows packaged ZIP acceptance requires a Windows machine/runner. Linux
packaging does **not** certify Windows.

## Controls (core verbs)

| Verb | Notes |
|------|--------|
| Move | Local movement in the current node |
| Wait / Travel | Advance strategic time (Travel/Wait only) |
| Talk / Inspect | Dialogue and inspection overlays |
| Inventory | Items and stock |
| Magic | Spellbook during leased encounters |
| Save / Load | Coordinated Python saves; corrupt slots restore from backup |

Use one pointer on touch-like viewports. Settings persist under `user://dmb_settings.json`
(volume, reduce motion, label scale).

## Saves and recovery

- Saves are written atomically; a failed write does not replace a good slot.
- If the primary slot is corrupt or its content hash mismatches, the previous
  backup is restored with an honest recovery message.
- Prototype/user saves are not deleted by recovery checkpoints.
- Quitting Godot should stop the Python sidecar.

## Offline

No internet, LLM, or API key is required at runtime. Loopback is used for the
local sidecar only.

## Known limits (honest)

- **Art:** semantic placeholders, not production art polish.
- **Policies:** three qualified trained faction policies depend on G09; do not
  assume they are present until G09 is `AUTO_READY_FOR_OWNER_REVIEW` or PASS.
- **Windows:** clean-machine Windows evidence is blocked until a Windows runner
  executes the packaged bundle (see `tracking/gates/G10/windows_status.md`).
- **Optional deferred:** mobile, Utopia, full voice.

## Evidence

See `docs/release_notes.md` and `Pack/DuelMasterBattle_Build_Pack/tracking/release_evidence.json`.
