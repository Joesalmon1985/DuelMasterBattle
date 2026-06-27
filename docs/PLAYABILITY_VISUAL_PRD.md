# PRD — Duel Master Battle: Playability & Visual Controls

## 1. Purpose

Define mobile-first interaction, ergonomics, and visual-feedback standards for the duel loop.

This document complements:

* [`docs/PRD.md`](PRD.md) — rules, real-time duel model, and product scope
* [`docs/PRD — Duel Master Battle Visual Polish, Screenshot QA and Composite Sprite System.md`](PRD%20%E2%80%94%20Duel%20Master%20Battle%20Visual%20Polish,%20Screenshot%20QA%20and%20Composite%20Sprite%20System.md) — asset system, layout zones, screenshot QA, and composite sprites
* [`docs/ART_BIBLE.md`](ART_BIBLE.md) — palette, timing, and shape language
* [`docs/VISUAL_QA.md`](VISUAL_QA.md) — capture workflow and rubric

## 2. Non-goals

* Rules changes or sim rewrites
* Art pipeline tooling or composite sprite generation specs
* Settler MVP or unrelated project assets

## 3. Product objective

> Make Duel Master Battle feel as easy to play on a phone as Clash Royale or Hearthstone feel to pick up — while preserving the deduction depth and non-leaking feedback rules of the ward duel.

The duel screen must pass a **two-second glance test**:

> Within two seconds, a new viewer understands where the battle is happening, what they can tap, and what just happened.

Reference resolution: **720 × 1280** portrait (see Visual Polish PRD §4).

---

## 4. Non-negotiable gameplay constraint

Visual and interaction design must not reveal more information than Mastermind-style rules allow.

**May reveal:** aggregate Fracture, Echo, and Fade counts.

**Must not reveal:** per-locus correctness, which projectile caused which feedback type, or any positional mapping between attack loci and result chips.

**Core animation rule:**

> Attacks may travel positionally, but feedback must resolve non-positionally.

Every control flow, animation, history row, and QA check in this PRD must preserve this rule. See Visual Polish PRD §3 and §9.

---

## 5. Thumb-zone layout contract

Vertical screen structure aligns with Visual Polish PRD §8. This section adds **reachability rules** derived from successful mobile card and battler UX (Hearthstone mobile overhaul, Clash Royale CTA placement, thumb-zone ergonomics research).

### 5.1 Zone map

| Zone | Screen allocation | Role | Allowed interactions | Forbidden |
|------|-------------------|------|----------------------|-----------|
| **Green (primary)** | Bottom ~35% | Player action | Locus sockets, essence tray, Cast button, cast timer, attack pattern | Rival info panels, history expand |
| **Yellow (secondary)** | Middle ~25–30% | Impact & result | Latest result chips (read-only); tap to open history sheet | Primary tap targets during active cast window |
| **Red (passive / rare)** | Top ~30–35% | Rival pressure | Rival ward and portrait (watch only); small “?” help | Cast, essence pick, destructive actions |

### 5.2 Reachability requirements

At 720 × 1280 reference resolution:

* Cast button center must sit within the **bottom 40%** of the viewport.
* Cast button center must be **≥ 48 px** above the bottom safe-area inset (gesture bar / home indicator).
* Primary interactive targets must not require a grip change for one-handed play.
* Secondary and destructive actions may live in yellow or red zones intentionally.

### 5.3 Safe areas

* Minimum outer padding: **24 px**
* Preferred major panel padding: **32 px**
* Breathing room around Cast button: **48 px** where practical
* Respect top notch and bottom gesture bar on all supported devices

### 5.4 Touch targets

| Control | Minimum size (720 × 1280) |
|---------|---------------------------|
| Cast button | 96 × 96 px |
| Locus socket | 72 × 72 px |
| Essence token | 72 × 72 px |
| Secondary buttons | 56 × 56 px |
| Utility buttons | 48 × 48 px |

Spacing between adjacent interactive targets: **≥ 8 px**, preferably **12–16 px**.

No important interactive target may be smaller than **48 × 48 px**.

---

## 6. Touch interaction model

The player builds an attack by assigning essences to loci, then casting when the cast window allows. Real-time pressure means controls must be fast, forgiving, and impossible to misread.

### 6.1 Interaction state machine

```text
IDLE
  → LOCUS_SELECTED        (tap locus)
  → ESSENCE_PICKER_OPEN   (picker anchored above thumb)
  → SOCKET_FILLED         (tap essence or drag-to-locus)
  → CAST_READY            (min cast time met, pattern valid)
  → CASTING               (wind-up + launch)
  → FEEDBACK_LOCKED       (result reveal; input queued or blocked)
  → IDLE
```

### 6.2 Gesture rules

| Gesture | Action | Must NOT |
|---------|--------|----------|
| **Tap locus** | Select locus; open essence picker anchored **above** the socket | Open picker under the player’s finger |
| **Tap essence (tray or picker)** | Fill selected locus; close picker | Require drag as the only path |
| **Long-press locus (400–500 ms)** | Peek: enlarge socket + show essence name **offset above finger** | Obscure label under finger (Slay the Spire iOS failure mode) |
| **Drag essence → locus** | Optional fast path; drag activates only after **≥ 12 px** movement | Accidental drag from inspect or scroll |
| **Tap filled locus** | Replace essence (re-open picker) | Clear socket on single tap |
| **Long-press filled locus OR tap small ✕ chip** | Clear socket | Destructive clear on accidental tap |
| **Tap Cast** | Single tap triggers wind-up → launch | Require double-tap |
| **During FEEDBACK_LOCKED** | Input queued or ignored with subtle “busy” pulse on attack builder | Allow cast or socket edits mid-reveal |

### 6.3 Primary interaction path (default)

1. Tap a locus socket.
2. Essence picker or tray highlights; tap an essence.
3. Socket fills with pop animation.
4. Repeat for remaining loci.
5. Tap Cast when ready.

Drag essence → locus is supported as an optional speed path, not the only taught path.

### 6.4 Input latency

* Dragged essence must follow the finger with **≤ 1 frame** perceived lag at 60 fps.
* Picker open/close: **≤ 150 ms** tween.
* Button press feedback: **0.08–0.14 s** (see ART_BIBLE).

### 6.5 Cast-while-animating policy

During `FEEDBACK_LOCKED` (~0.7–1.2 s after Cast):

* Player may **not** submit a new cast until the feedback sequence completes or reaches the “aftermath settle” phase.
* Attack builder shows a subtle busy state (dimmed tray or pulse on border), not an opaque modal.
* If input is queued, apply it only after lock clears.

Maximum uninterrupted animation lock before player can edit the next attack: **≤ 1.2 s**.

---

## 7. Primary CTA visual language

Primary actions use **accent gold** (`#ffc947` from ART_BIBLE) when active, following Clash Royale / Hearthstone patterns where the most important button is brightest and largest.

### 7.1 Cast button states

| State | Cast button | Timer ring | Essence tray |
|-------|-------------|------------|--------------|
| **Disabled** (< min cast time) | Grey-violet, no glow | Partial arc, cool colour | Normal |
| **Charging** | Soft pulse | Arc filling | Normal |
| **Ready** | Gold `#ffc947`, strong glow | Full ring; one flash on transition | Subtle highlight on empty sockets |
| **Auto-cast ≤ 5 s** | Faster pulse + warm rim | Ring shifts amber | Pattern outline shimmers |
| **Auto-cast ≤ 3 s** | Haptic tick + warning sound | Ring pulses 2×/sec | — |
| **Auto-cast ≤ 1 s** | “Unstable release” VFX on pattern | — | — |

### 7.2 Timer visual language

Timers must be **visual first**, text second (Hearthstone burning-rope principle adapted to ward duels):

* Circular charge ring around Cast or horizontal cast bar in the player zone.
* Colour shift as max cast time approaches (cool → amber → warm red).
* Pulse at warning thresholds; do not rely on a numeric countdown alone.
* Rival cast pressure uses a parallel visual (ring, bar, or ward pulse) — visible in one glance, not a paragraph of status text.

Example labels (short, optional): “Cast ready”, “Auto-cast soon”, “Rival casting”.

### 7.3 Haptic and audio feedback

| Event | Haptic | Audio |
|-------|--------|-------|
| Essence placed | Light tap | Soft pop |
| Cast ready | Medium tap | Ready chime |
| Cast submitted | Medium tap | Wind-up whoosh |
| Auto-cast warning (≤ 3 s) | Light tick | Warning tone |
| Fracture / Echo / Fade chip | Light tap each | Distinct chip sound per type |

Respect system mute and “reduce motion” settings; haptics are optional enhancement, not sole feedback channel.

---

## 8. Progressive onboarding (FTUE controls)

Teach controls through gameplay, not permanent help text (Hearthstone arrow/glow model; Marvel Snap “pick up card, play to location” simplicity).

### 8.1 Principles

* No modal longer than two sentences during the first duel.
* Use glowing targets, arrows, and colour state changes — not walls of text.
* Remove guided arrows after the taught action succeeds once.
* Help text lives behind a small “?” button, not on the main duel surface (Visual Polish PRD §8.5).

### 8.2 Encounter-scoped teaching (Blue Apprentice)

| Attack # | Teach | Success criterion |
|----------|-------|-------------------|
| **1** | Arrow on first empty locus → glow essence tray → glow Cast when ready | Player completes first cast without opening help |
| **2** | Tap history chip; show aggregate result is **not** per-locus | Player understands Fracture/Echo/Fade are grouped counts |
| **3** | Introduce cast timer ring with forgiving thresholds | Player notices timer before first auto-cast |

Later encounters remove arrows and rely on colour/state cues only.

### 8.3 Copy rules

* On-screen instructional text during duel: **≤ 11 words** per prompt where possible (Marvel Snap card-text discipline).
* Any instruction that must be read twice is rewritten or replaced with a visual cue.

---

## 9. Feedback readability contract

Feedback uses a **three-phase sequence** (anticipation → emphasis → aftermath) so players can parse results under time pressure without positional leak.

### 9.1 Sequence timing

| Phase | Duration | Visual | Audio / haptic |
|-------|----------|--------|----------------|
| **Anticipation** | 0.15–0.25 s | Essence bolts converge; rival ward brightens | Soft whoosh |
| **Emphasis** | 0.35–0.50 s | Ward swirl masks individual impacts; optional brief vignette | Impact thud |
| **Aftermath** | 0.35–0.70 s | Non-positional chip burst; chips settle in fixed cluster | Distinct sounds per chip type |

Timings align with [`docs/ART_BIBLE.md`](ART_BIBLE.md) animation table; total feedback reveal **≤ 1.2 s** before input unlock.

### 9.2 Result presentation

* Latest result appears as a **grouped cluster** in the middle zone (yellow), never aligned under attack loci.
* Each chip combines **icon + count + label + distinct colour + distinct shape** (Visual Polish PRD §9.1).
* Wording stays short: “2 Fractures”, “1 Echo”, “1 Fade” — not repeated sentences.

### 9.3 Hard QA rule

**Fail any build** where chip horizontal position correlates with locus index in screenshots or live capture. Feedback cluster position must be fixed or deliberately shuffled — never positional.

### 9.4 Reduce motion

When reduce motion is enabled:

* Replace large movement with fade/scale.
* Keep chip counts and labels fully visible.
* Skip screen shake and heavy particles.
* Do not skip the aftermath phase entirely — players still need readable aggregate results.

---

## 10. Visual hierarchy during play

At any moment in the duel, only three major focal areas compete for attention (Visual Polish PRD §6.1):

1. **Rival ward and pressure** (top)
2. **Latest attack result** (middle)
3. **Player attack builder and Cast** (bottom)

Everything else is secondary: compact history, hidden help, settings, encounter chrome.

### 10.1 Text budget

On the default duel screen (no expanded history, no help modal):

* Visible text nodes: **< 30**
* Visible character count: **< 500**
* Default history rows: **≤ 3** player attacks visible

See [`docs/VISUAL_QA.md`](VISUAL_QA.md) automated metrics.

### 10.2 Text sizes (720 × 1280)

| Role | Size |
|------|------|
| Primary status | 26–34 px |
| Secondary status | 20–24 px |
| Button text | 22–28 px |
| History row | 18–22 px |
| Captions | ≥ 16 px, sparingly |

Normal text contrast: **≥ 4.5:1**. Large status text: **≥ 3:1**.

### 10.3 Colour semantics

| Meaning | Treatment |
|---------|-----------|
| Primary action (Cast ready) | Gold `#ffc947` |
| Player aura / ally | Cyan `#4fc3f7` |
| Fracture | Green-gold crack glyph `#66ff99` |
| Echo | Amber ring `#ffb84d` |
| Fade | Silver mote `#a8a8b8` |
| Disabled control | Desaturated, still legible |

Never rely on colour alone — pair with icon, shape, and label (Visual Polish PRD §14.8).

---

## 11. Session and pacing UX targets

Real-time ward duels should fit a **lunch-break session** (Marvel Snap / Clash Royale standard):

| Target | Value |
|--------|-------|
| Typical duel length | 3–6 minutes |
| Max feedback input lock | ≤ 1.2 s |
| Rival pressure readable | ≤ 1 glance (timer + ward state chip) |
| Dead time while waiting on rival | Zero — show rival casting animation/ring, not static UI |

Player must always see without scrolling: current attack pattern, active loci, available essences, cast availability, time to auto-cast, latest aggregate result, rival cast pressure.

---

## 12. Device and accessibility matrix

| Profile | Min Cast | Min locus / essence | Text minimum | Notes |
|---------|----------|---------------------|--------------|-------|
| Reference 720 × 1280 | 96 px | 72 px | 18 px history | Design baseline |
| Small phone ~640 × 1136 | 88 px | 64 px | 16 px captions only | Scale up targets; never shrink Cast below 88 px |
| Large phone / tablet | Same logical size | Same | Same | Extra margin, not smaller targets |

### 12.1 Settings

* **Left-hand mode:** mirror locus tray and Cast to the left edge; keep thumb-zone rules.
* **Reduce motion:** see §9.4.
* **Larger text:** +4 px on status labels; do not shrink touch targets to compensate.

### 12.2 Accessibility checklist

* Fracture / Echo / Fade distinguishable by icon and shape, not colour alone.
* Tooltips and peek labels meet minimum contrast.
* Auto-cast warnings use motion + sound + haptic, any of which can be disabled without losing critical state info.

---

## 13. Anti-patterns (do not ship)

Explicit failures to test against before release:

- [ ] Touch target **< 48 px** at 720 × 1280 reference
- [ ] Cast or confirm control placed under typical thumb rest (Slay the Spire skip-button problem)
- [ ] Finger covers essence name on long-press inspect
- [ ] Drag activation threshold **< 8 px** (causes accidental plays)
- [ ] **> 30** visible text nodes on default duel screen
- [ ] Colour-only Fracture / Echo / Fade distinction
- [ ] Positional feedback leak in history rows or chip placement
- [ ] Desktop-style dense log visible by default
- [ ] Animations block input with no visible “busy” state on attack builder
- [ ] Card/board-game language visible (“guess”, “code”, pegs, pins)
- [ ] Help paragraph permanently on duel screen

---

## 14. Playability QA checklist

Complements [`docs/VISUAL_QA.md`](VISUAL_QA.md) screenshot rubric with **interaction** checks.

### 14.1 Automated / scripted targets

| Check | Target |
|-------|--------|
| Cast button in thumb zone | Center Y > 60% of screen height |
| Drag activation threshold | ≥ 12 px |
| Feedback lock duration | ≤ 1.2 s |
| Picker opens above locus | `picker.y < locus.y` |
| First-cast FTUE | Completable in UI smoke test without help modal |
| Touch target audit | No role=cast/locus/essence control < minimum from §5.4 |

Implement in `tools/visual_qa_report.py` or a sibling `tools/playability_qa_report.py` when wiring QA automation.

### 14.2 Manual playtest gates

Before marking a playability pass complete:

1. One-handed play on smallest supported phone — complete a full duel without mis-taps.
2. Long-press inspect on every locus — label never hidden under finger.
3. Intentional drag cancel — essence returns smoothly, no accidental cast.
4. Auto-cast at 3 s and 1 s — warnings visible without reading log text.
5. Expanded history — no per-locus result alignment.
6. Left-hand mode — Cast and loci reachable without grip change.

### 14.3 Rubric extension

Add **Playability / controls** as a scored category (1–5) in visual QA reports. Pass threshold: **≥ 4**.

Score 1: Accidental inputs, finger occlusion, unclear next action.  
Score 5: Thumb-friendly, instant feedback, FTUE invisible after first duel, zero positional leak.

---

## 15. Acceptance standard

The duel screen passes this PRD only if:

1. Portrait mobile-first layout with green/yellow/red zones respected.
2. Cast button is largest control, gold when ready, in thumb zone.
3. Gesture state machine behaves per §6 without accidental plays in smoke tests.
4. Feedback uses three-phase non-positional reveal per §9.
5. FTUE teaches first cast without permanent help text.
6. Anti-patterns in §13 are all clear.
7. Visual QA + playability checklist scores **≥ 4** in every category.
8. Non-leak rules unchanged from Visual Polish PRD §3.

---

## 16. Related documents

| Document | Scope |
|----------|-------|
| [`docs/PRD.md`](PRD.md) | Product rules, real-time duel, encounter progression |
| Visual Polish PRD | Composite sprites, UI skin, screenshot states, layout detail |
| [`docs/ART_BIBLE.md`](ART_BIBLE.md) | Palette, outlines, animation durations |
| [`docs/VISUAL_QA.md`](VISUAL_QA.md) | Capture scripts, montages, metric thresholds |

---

## 17. Research references (informative)

Patterns adapted from shipped mobile titles and UX literature:

* **Hearthstone (mobile):** full layout overhaul, card lift away from finger, arrow/glow onboarding, dramatic timer feedback, three-phase VFX.
* **Clash Royale:** gold primary CTAs, shallow menus, colour-coded battlefield readability, strong silhouettes.
* **Marvel Snap:** minimal interaction surface (play to location), short copy, simultaneous pacing, dark stage UI.
* **Slay the Spire (iOS, cautionary):** small targets, finger occlusion on hold, weak drag thresholds, desktop port layout — explicit anti-patterns for this project.
* **Thumb-zone ergonomics:** bottom 35–40% for primary actions, 48 dp minimum targets, safe-area padding above gesture bar.

These references inform requirements; Duel Master Battle must not copy their art direction or rules — only their mobile usability patterns.
