# Deployment Plan

## Scope for this run
Deployment is **deferrable** until the playable Godot Human vs Bot vertical slice and UI smoke test pass.

## Web (M8 — deferrable)
- Engine: Godot 4.4.1 (templates installed at `~/.local/share/godot/export_templates/4.4.1.stable/`)
- Export preset: Web
- Output: `build/web/index.html`
- Script: `tools/export_web.sh`
- Hosting: Cloudflare Pages (static) — see `DEPLOY_CLOUDFLARE_PAGES.md` when built
- **Do not claim deployment succeeded unless export is built and verified**

## Android (M9 — deferrable)
- Requires Android export templates (may need download)
- See `ANDROID_EXPORT.md` when attempted
- **Mark honestly if not built**

## Local play (primary)
```bash
export GODOT=/home/joe/Documents/Godot/Godot_v4.4.1-stable_linux.x86_64
"$GODOT" --path godot_project
# Or press Play in Godot editor with godot_project as project root
```

## Pre-deploy checklist (when M8/M9 attempted)
- [ ] All rules tests pass
- [ ] UI smoke test passes
- [ ] Manual playtest passed (or documented for user)
- [ ] No stale Godot processes
- [ ] Export build completes without errors
- [ ] Exported build launches in target browser/device
