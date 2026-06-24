# QA / Release Agent Role

## Responsibility
Full verification and release checklist.

## For this project (M10)
- Run Python rules tests
- Run Godot rules tests
- Run Godot UI smoke test
- Manual playtest: run if visible window available; otherwise document scripted smoke pass + user steps
- Confirm no stale Godot processes (`tools/godot_check.sh`)
- Write `docs/RELEASE_NOTES.md` and final `README.md`

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
