# G03 reset

The G03 save is isolated as `g03_playtest`.

1. Close the G03 window so its Python sidecar exits.
2. Remove only `.dmb_saves/g03_playtest.json` and its matching backup, if
   present. Do not remove G01/G02 saves.
3. Relaunch with `bash tools/play_g03.sh`; FX-INDUSTRY starts from seed 303.

The automated smoke uses `g03_smoke`, not the human playtest slot.
