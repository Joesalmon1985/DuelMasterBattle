# Spellbook UI

Reusable animated spellbook interface for DuelMasterBattle gate playtests and
shared gameplay/dialogue presentation.

## Branch facts (verified 2026-09-18)

| Ref | Commit |
|-----|--------|
| `feature/spellbook-ui` base (was `BuildPackV03` HEAD) | `d265f60` |
| `origin/BuildPackV03` | `d265f60` (identical) |
| `origin/main` | `441899b` (PR #8 merge; **5 ahead / 2 behind** vs BuildPackV03) |
| local `main` | `687290e` (**stale**, 266 behind `origin/main`) |

`origin/main` includes G01–G04 via PR #8, but is missing the G04 playable fix commits
(`67c7580`, `d265f60`) that are on BuildPackV03. This feature branch was created from
BuildPackV03 HEAD so those fixes remain available. Local untracked Spellbook JPEGs were
preserved; no reset/rebase of the gate stack.

Project stretch: `canvas_items` + `expand`, logical viewport **720×1280**, window override
often 450×800. A 360-wide **window** must not be treated as a 360-wide **UI layout** —
controls are authored in logical pixels.

## Launch

```bash
bash tools/play_g01.sh --direct          # G01 FX-CLOCK
bash tools/play_g02.sh --direct          # G02 FX-CARGO
bash tools/play_g03.sh                   # G03 FX-INDUSTRY
bash tools/play_g04_battle.sh            # G04 battle
bash tools/play_g04_hazard.sh            # G04 hazard
```

Village dialogue through the book (existing overworld path):

```bash
DMB_SPELLBOOK_DIALOGUE=1   # then launch village / adventure overworld as usual
```

Reduced motion / text scale:

```bash
export DMB_REDUCED_MOTION=1
# or ProjectSettings dmb/spellbook/reduced_motion, dmb/spellbook/text_scale
```

## G01 control mapping

| Original control | Spellbook location |
|------------------|--------------------|
| Status / Counters / Prompt | Status page + compact card summary |
| Wait | Actions → Wait |
| Invalid exit | Actions → Invalid exit |
| Pause / Resume | Actions (preserves Game Time freeze semantics) |
| Save / Load | Actions (Load confirms) |
| Bridge fail | Troubleshoot (confirms) |
| Dev panel log | Troubleshoot → Toggle Dev log panel; Log page |
| Menu | **Exit to menu** (always on open book; not Classic-only) |
| Close / return to test | **Close book** (separate from Exit to menu) |
| Classic bottom bar | Troubleshoot → Toggle Classic HUD |

## G02–G04 additions

| Mode | Section | Controls |
|------|---------|----------|
| G02 | Economy | Start delivery, Block route, Clear hazard |
| G03 | Industry | Damage 25%, Strike, Clear strike, Paid repair, Path block (presentation) |
| G04 battle | Spells | Destroy / Shield / Atk Spd / Range — **needs world target** |
| G04 hazard | Hazard | Treat (target), Channel, Falter (confirm) |

### Targeting lifecycle

Selecting a spell/action that needs a world target:

1. Expanded book collapses to a compact **targeting card**.
2. Card shows selected action, guidance, and **Cancel targeting** (no effect).
3. The selecting press is ignored for ~220 ms so it cannot also pick a world target.
4. Player taps a valid world object; command runs through the existing `_cmd` / Interact /
   CastDestroy / CastBuff / StartHazardDuel path.
5. Result shows only after acknowledgement (`pending` → `success`/`rejected`/`timeout`/
   `disconnected`). Tokens correlate replies; stale tokens are ignored. Open/close does
   not resend.

## Architecture

- Presentation: `client/ui/spellbook/spellbook_host.gd` (+ margins)
- Data / lifecycle: `spellbook_model.gd`
- Gate adapters: `spellbook_gate_binder.gd`, `spellbook_non_g01_attach.gd`
- Gameplay info: `spellbook_info_binder.gd` (plain dictionaries; Status page uses live
  `RequestView` fields)
- Dialogue: `spellbook_dialogue_presenter.gd` — compatible with `DialogueBox`
  `say` / `say_async` / `choose_async` / `advance`; reveal ≠ advance; wired when
  `DMB_SPELLBOOK_DIALOGUE=1` on overworld. Proven against `VillageQuestRunner` E17A
  conversation for NPC `a` without applying choice consequences on close.

Python remains authoritative for durable gate state via `WorldClient`. The book never
owns simulation rules.

## Assets

Originals preserved:

- `godot_project/assets/sprites/Spellbook/Spellbook.jpeg`
- `spellpage.jpeg`, `spellcard.jpeg`

Transparent PNGs (white exterior keyed; parchment/borders/shadows kept):

- `Spellbook.png`, `spellpage.png`, `spellcard.png`

Light/dark composites: `docs/spellbook_captures/preview_*_{light,dark}.png`.

Page-turn limitation: single JPEG frames only — transitions are crossfade/slide, not a
fake multi-frame flip.

## Tests run

| Check | Result | Kind |
|-------|--------|------|
| `run_spellbook_model.gd` | OK | Automated |
| `run_g01_spellbook_slice.gd` | OK (Wait ack) | Automated live sidecar |
| `run_spellbook_dialogue_village.gd` | OK (E17A) | Automated |
| `run_spellbook_capture.gd` | OK (stretch/layout) | Automated |
| `run_g01_smoke.gd` / `run_g04_smoke.gd` | OK | Automated |
| Layout composites 360/390/720/1280 | See `docs/spellbook_captures/` | Offline visual |
| Headless viewport screenshot | Not available (dummy renderer) | Limitation |
| Emulated touch / physical device | Not run | Limitation |

## Remaining limitations

- No physical-device or desktop touch-emulation pass in this run.
- Headless Godot cannot capture final GPU frames; use interactive play + offline layout
  composites for size review.
- `assets/animations/Anim_Spellbook.png` is included for future page-flip work; current
  transitions remain crossfade/slide over the static book/page art.
- Spellbook work does **not** clear the G04 human gate.
- Ensemble dialogue tooling remains on side branches; live dialogue authority for village
  is still Godot `VillageQuestRunner`.
