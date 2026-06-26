# Deployment Plan

## Scope
Deployment is **deferrable** until rules tests, UI smoke, and encounter regression (Archmage Duel) pass on the target branch.

## Web (M8 — deferrable)
- Engine: Godot 4.4.1 (templates installed at `~/.local/share/godot/export_templates/4.4.1.stable/`)
- Export preset: Web
- Output: `godot_project/build/web/index.html`
- Script: `tools/export_web.sh`
- Hosting: Cloudflare Pages (static) — see `DEPLOY_CLOUDFLARE_PAGES.md` when built
- **Do not claim deployment succeeded unless export is built and verified**
- Re-export required after encounter UI changes

## Android (M9 — deferrable)
- Requires Android export templates (may need download)
- See `ANDROID_EXPORT.md` when attempted
- **Mark honestly if not built**

## Local play (primary)
```bash
export GODOT=$HOME/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64
export GODOT_USER_DATA_DIR="$(pwd)/godot_project/.godot_user"
"$GODOT" --path godot_project
```
Main menu → select encounter → **Start duel**.

## Pre-deploy checklist (when M8/M9 attempted)
- [ ] Python pytest green (53+ typical)
- [ ] Godot rules tests pass (7 modules)
- [ ] UI smoke passes (Blue Apprentice + Archmage)
- [ ] Manual playtest passed (or documented for user)
- [ ] No stale Godot processes (`tools/godot_check.sh`)
- [ ] Export build completes without errors
- [ ] Exported build launches in target browser/device
