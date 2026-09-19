# G04 retained reuse map (U01)

| Component | Retained | New caller / adapter |
|---|---|---|
| `godot_project/client/scenes/game_board.tscn` + `game_board.gd` | Yes | `DmbDuelLeaseAdapter` via `configure_from_lease` before `add_child` |
| `godot_project/sim/battle_sim.gd` (`DmbBattleSim`) | Yes | Lease Challenge; `export_checkpoint` / `restore_checkpoint` |
| `godot_project/client/ui/attached_choice_card.gd` | Appearance preserved | `DmbTargetSession` |
| `godot_project/client/world/world_interaction_label.gd` | Presentation | `DmbBridgeInteractionPresenter` + `bind_bridge` |
| `sim/dmb/adventure/mastermind.py` | Reference scoring only | `begin_mastermind_reference`; not production Challenge |
| Quick duel (`main_menu` → empty `pending_battle`) | Unchanged | — |
| Adventure `pending_battle` | Unchanged | — |

Ensemble follow-up (not on this branch): `58ea2d2`, `6f7be0f` on `BuildPackV03-ensemble-depth-pass`.
