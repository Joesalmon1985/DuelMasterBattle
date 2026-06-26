# QA / Release Agent Role

## Responsibility
Full verification and release checklist.

## For this project (M10 / per branch)
- Run Python rules tests (53+ typical on encounter branch)
- Run Godot rules tests (7 modules)
- Run Godot UI smoke (dual encounter flows)
- Manual playtest: run if visible window available; otherwise document scripted smoke pass + user steps in `MANUAL_PLAYTEST.md` (13-step encounter checklist)
- Confirm no stale Godot processes (`tools/godot_check.sh`)
- Write `docs/RELEASE_NOTES.md` and update `README.md`

## Final report template
```
Branch:
Summary:
Tests run:
Results:
Manual playtest: passed | partial | failed | not performed
Known issues:
Unimplemented (deferred):
Stale Godot processes:
```
