# Deploy to Cloudflare Pages

## Prerequisites
- Web export built locally: `tools/export_web.sh`
- Output folder: `godot_project/build/web/` (contains `index.html`, `.wasm`, `.pck`, etc.)
- Cloudflare account

## Build
```bash
tools/export_web.sh
ls godot_project/build/web/
```

Re-export after encounter UI changes — local `build/web/` is gitignored and may be stale.

## Cloudflare Pages setup
1. Log in to [Cloudflare Dashboard](https://dash.cloudflare.com/) → **Workers & Pages** → **Create** → **Pages** → **Connect to Git** (or **Direct Upload**).
2. **Direct Upload** (simplest for static export):
   - Run `tools/export_web.sh`
   - Upload the contents of `godot_project/build/web/` (not the folder itself — all files inside).
3. **Git integration**:
   - Add a build command that runs Godot headless export (requires Godot + templates in CI).
   - Set **Build output directory** to `godot_project/build/web`.
4. Deploy. Pages serves `index.html` as the entry point.

## Headers (recommended)
In Cloudflare Pages → **Settings** → **Functions** or `_headers` file:
```
/*
  Cross-Origin-Embedder-Policy: require-corp
  Cross-Origin-Opener-Policy: same-origin
```
Godot 4 web builds often need COOP/COEP for threads; if the game fails to load, add these headers.

## Verification
- Open the deployed URL in a desktop browser.
- Confirm main menu loads with **encounter select** and **Start duel** is playable.
- Try **Blue Apprentice** (1 slot) and **Archmage Duel** (4 slots) if verifying encounter build.
- **This document does not claim deployment succeeded** — verify after upload.

## Local preview
```bash
cd godot_project/build/web
python3 -m http.server 8080
# Open http://localhost:8080
```
