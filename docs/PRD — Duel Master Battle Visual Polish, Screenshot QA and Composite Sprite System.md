# PRD — Duel Master Battle Visual Polish, Screenshot QA and Composite Sprite System

## 1. Product objective

Duel Master Battle already works mechanically, but the current visual presentation is not good enough for a finished mobile game. The current duel screen is too grey, too text-heavy, too debug-like, and too difficult for a human player to follow at speed.

This PRD defines the next major product milestone:

> Transform Duel Master Battle from a functional prototype into a visually clear, exciting, mobile-first magical puzzle duel with strong screenshot QA and a reusable composite sprite system.

This is not a rules rewrite. The underlying Mastermind-style deduction rules must remain correct. The purpose of this phase is to make the game readable, enticing, juicy and visually coherent.

---

## 2. Core visual goal

The game should feel like:

> A bright, juicy, magical mobile puzzle battler where two wizards fling structured essence attacks into living ward barriers.

The desired feel is:

* Mobile-first.
* Colourful.
* Tactile.
* Readable.
* Rewarding.
* Magical.
* Puzzle-like.
* Polished.
* Fast to understand.
* Fun to watch.

The game should no longer feel like:

* A debug UI.
* A grey test harness.
* A text log.
* A direct Mastermind clone.
* A desktop-first Godot prototype.
* A table of guesses and results.

---

## 3. Non-negotiable gameplay constraint

The visual language must not reveal more information than the original Mastermind-style rules allow.

The game may reveal:

* Number of Fractures.
* Number of Echoes.
* Number of Fades.

The game must not reveal:

* Which locus was exactly correct.
* Which locus had the correct essence in the wrong place.
* Which projectile caused a Fracture.
* Which projectile caused an Echo.
* Which projectile caused a Fade.
* Any per-locus correctness information.

Core animation rule:

> Attacks may travel positionally, but feedback must resolve non-positionally.

Allowed:

* Four essence bolts fly into the rival ward.
* The ward absorbs all bolts.
* The barrier swirls and masks individual impacts.
* A grouped result appears: 2 Fractures, 1 Echo, 1 Fade.

Not allowed:

* The Roach projectile visibly cracks the barrier.
* The Uzag projectile visibly fades.
* The Gyse projectile visibly echoes.
* Feedback icons aligned under the exact attack loci.

Every visual, animation, history row and QA check must preserve this rule.

---

## 4. Target platform and visual reference resolution

Primary platform:

* Android mobile.
* Portrait orientation.

Reference design resolution:

* 720 × 1280.

All visual standards in this PRD use that reference resolution.

The UI must scale cleanly to:

* Small phones.
* Large phones.
* Desktop test window.
* Optional web export.

---

## 5. Current visual problems to fix

The current duel screen has these problems:

1. Too much text is visible at once.
2. The screen is dominated by grey panels and log rows.
3. The player cannot instantly tell where to look.
4. The current attack builder is not visually dominant enough.
5. The Cast button is too plain and too small in feel.
6. The rival and player feel like small icons, not characters.
7. The ward barrier does not feel like the centre of the duel.
8. Feedback rows are hard to scan quickly.
9. Fracture / Echo / Fade are technically correct but visually weak.
10. History dominates the play space.
11. Help text is permanently visible and competes with play.
12. The game does not yet have a strong “magical puzzle battler” identity.
13. The UI looks like it was built to prove the sim works, not to attract players.
14. There is not enough animation, reward feedback, glow, motion or impact.

The visual polish pass is successful only if these problems are visibly improved in screenshots.

---

## 6. Visual design principles

### 6.1 Fewer focal points

At any point in the duel, the player should have only three major focal areas:

1. Rival ward and pressure.
2. Latest attack result.
3. Player attack builder and Cast button.

Everything else is secondary.

The screen should pass a two-second glance test:

> Within two seconds, a new viewer should understand where the battle is happening, what the player can tap, and what just happened.

### 6.2 Text must be reduced

The main duel screen must not be a wall of text.

Persistent duel text should be limited to:

* Short labels.
* Current timers.
* Current result.
* Compact history rows.
* Small contextual prompts only when needed.

Rules explanation should move to:

* Help modal.
* Tutorial overlay.
* “How feedback works” screen.
* Tap-to-expand tooltip.

Do not leave paragraph-style explanations permanently visible during active play.

### 6.3 Make the game juicy

Every important action should have visual and audio response.

The game should include:

* Button press bounce.
* Cast button glow when ready.
* Essence socket pop when filled.
* Barrier pulse on impact.
* Fracture crack burst.
* Echo ring shimmer.
* Fade dissolve particles.
* Auto-cast warning pulse.
* Victory sparkle / burst.
* Clash shockwave.
* Last Stand instability effects.

The player should feel rewarded for interacting, even before they understand the full deduction logic.

### 6.4 Magic first, UI second

The battle should be visually led by magical objects:

* Wards.
* Essence orbs.
* Loci.
* Runes.
* Projectiles.
* Fractures.
* Echo rings.
* Fading motes.

Panels, labels and logs should support those magical objects, not dominate them.

### 6.5 Bright, saturated, but readable

The game should use a richer palette than the current grey-heavy prototype.

Use:

* Deep magical background gradients.
* Saturated essence colours.
* Bright feedback highlights.
* High contrast text.
* Soft glows.
* Warm/cool contrast.
* Jewel-like buttons and essence tokens.

Avoid:

* Flat grey backgrounds.
* Low-contrast grey-on-grey text.
* Tiny coloured squares.
* Muted debug-style controls.
* Unstyled default Godot buttons.

### 6.6 Colour is never enough

Essences and feedback types must be distinguishable by:

* Colour.
* Shape.
* Icon.
* Label.
* Motion.
* Sound where appropriate.

Fracture, Echo and Fade must each have their own distinct shape language.

Example:

* Fracture = sharp crack symbol.
* Echo = circular ripple / ring symbol.
* Fade = dissolving mote / broken dust symbol.

### 6.7 Visual identity must hide Mastermind

The player may still see their own attack pattern by locus, because they chose it. But feedback must look like barrier reactions, not board-game pegs.

Avoid:

* Rows of plain coloured dots.
* Black/white pin equivalents.
* Spreadsheet-like combat logs.
* Static Mastermind board layout.

Use:

* Essence tokens.
* Attack ribbons.
* Impact summaries.
* Ward reaction glyphs.
* Result chips.
* Animated magical feedback clusters.

---

## 7. Mobile UI standards

### 7.1 Touch targets

At the 720 × 1280 reference resolution:

* Primary Cast button target: minimum 96 × 96 px.
* Essence token target: minimum 72 × 72 px.
* Locus socket target: minimum 72 × 72 px.
* Secondary buttons: minimum 56 × 56 px.
* Small utility buttons: minimum 48 × 48 px.
* No important interactive target may be smaller than 48 × 48 px.

There must be at least 8 px spacing between adjacent interactive targets, preferably 12–16 px.

### 7.2 Text size

At the 720 × 1280 reference resolution:

* Primary status text: 26–34 px.
* Secondary status text: 20–24 px.
* Button text: 22–28 px.
* History row text: 18–22 px.
* Tiny captions: minimum 16 px, used sparingly.

Avoid long lines of text. Prefer compact chips and icons.

### 7.3 Contrast

Text must be readable over its background.

Requirements:

* Normal text should target 4.5:1 contrast or better.
* Large title/status text should target 3:1 contrast or better.
* Important controls should have strong luminance contrast from background.
* Disabled controls must look disabled but still legible.

### 7.4 Safe areas

The UI must respect mobile safe areas.

Important controls must not sit too close to:

* Top notch.
* Bottom gesture bar.
* Screen edges.
* Scrollbar edge.

Recommended safe padding:

* 24 px minimum outer padding.
* 32 px preferred for major panels.
* 48 px breathing room around the Cast button where practical.

---

## 8. New duel screen layout

The current duel screen should be redesigned around a clear vertical structure.

### 8.1 Top zone — rival ward

Approximate screen allocation:

* Top 30–35% of screen.

Contains:

* Rival portrait / composite wizard.
* Rival ward barrier.
* Rival name/title.
* Rival cast pressure timer.
* Rival remaining casts.
* Current rival state: Stable / Unstable / Broken.

The rival ward should be a major visual focal object.

### 8.2 Middle zone — impact and latest result

Approximate screen allocation:

* Middle 25–30% of screen.

Contains:

* Attack travel path.
* Barrier impact animation.
* Latest result cluster.
* Fracture / Echo / Fade chips.
* Short text such as “Ward cracks twice” only if needed.

The latest result should be large, central and readable.

### 8.3 Bottom zone — player action

Approximate screen allocation:

* Bottom 30–35% of screen.

Contains:

* Player mini portrait or aura.
* Active loci sockets.
* Essence tray.
* Cast timer.
* Large Cast button.
* Auto-cast warning.
* Current attack pattern.

This is the main interaction area.

### 8.4 Collapsed history

History should not dominate the default view.

Default history behaviour:

* Show only the last 2–3 player attacks.
* Show only the last 1–2 rival attacks, or show rival history in a separate tab.
* Older history is available through a slide-up panel.
* History rows use compact icons and chips, not full text paragraphs.

Expanded history behaviour:

* Slide-up sheet.
* Clear grouping: Your attacks / Rival attacks.
* Scrollable.
* No feedback aligned positionally under loci.

### 8.5 Help text

Do not show long help text permanently.

Replace with:

* Small “?” button.
* Tap-to-open help card.
* First-time tutorial overlay.
* Short one-line contextual hint only when needed.

---

## 9. Result feedback design

### 9.1 Feedback chips

Create large result chips for:

* Fracture.
* Echo.
* Fade.

Each chip should include:

* Icon.
* Count.
* Label.
* Distinct colour.
* Distinct shape.
* Small animation.

Example visual language:

* Fracture: jagged green/gold crack, sharp pop.
* Echo: circular amber ring, ripple pulse.
* Fade: grey/silver dust mote, dissolve.

### 9.2 Latest result cluster

The latest result should appear as a grouped cluster, not a row aligned to loci.

Example:

```text
Fracture ×2    Echo ×1    Fade ×1
```

But visually this should be a magical result burst, not plain text.

### 9.3 Result wording

Use short wording.

Preferred:

* “2 Fractures”
* “1 Echo”
* “1 Fade”

Avoid long repeated sentences in the duel screen.

Long explanation belongs in help.

### 9.4 Result animation sequence

For each attack:

1. Essence bolts launch.
2. Bolts converge into the ward.
3. Ward absorbs all bolts.
4. Ward swirls, masking individual impacts.
5. Result glyph cluster bursts outward.
6. Chips settle into latest result panel.
7. History row is added.

The feedback reveal must be non-positional.

---

## 10. Composite sprite system

### 10.1 Purpose

Cursor may struggle to create a single beautiful full wizard sprite. Therefore the art system should use composite sprites made from reusable layered parts.

The goal is:

* More expressive animation.
* Reusable assets.
* Easier procedural generation.
* Better visual variety.
* Lower requirement for perfect single-image art.
* More “alive” characters using simple rotations, offsets and tweens.

### 10.2 Character composite structure

Each wizard should be assembled from separate parts.

Minimum character parts:

```text
root
  shadow
  back_aura
  back_cloak
  torso
  head
  face
  eyes
  hair_or_hat
  left_upper_arm
  left_forearm
  left_hand
  right_upper_arm
  right_forearm
  right_hand
  front_cloak
  chest_gem
  floating_runes
  cast_glow
```

Optional parts:

```text
shoulder_pads
belt
mask
horns
halo
beard
sleeve_trails
familiar_or_orb
```

Each part should be a separate transparent PNG or generated texture.

Each part must have:

* Anchor point.
* Default offset.
* Z-index/layer order.
* Optional tint.
* Optional idle motion.
* Optional casting motion.
* Optional defeat motion.

### 10.3 Character animation states

Each composite wizard should support:

* Idle breathing.
* Thinking / pressure.
* Cast wind-up.
* Attack release.
* Barrier hit reaction.
* Ward broken.
* Last Stand unstable.
* Victory.
* Defeat.

These can be simple tweens:

* Head bob.
* Arms lift.
* Hands glow.
* Cloak sway.
* Aura pulse.
* Eyes flash.
* Runes orbit.
* Body recoil.

Do not wait for perfect frame-by-frame character art.

### 10.4 Enemy visual variation

Enemies should be generated from different part sets and palettes.

Example enemy styles:

#### Blue Apprentice

* Rounded shapes.
* Soft blue aura.
* Simple robe.
* Friendly silhouette.
* Slow idle motion.

#### Thorn Adept

* Vine-like cloak shapes.
* Green/brown palette.
* Thorn orbit particles.
* Angular hands.

#### Mirror Mage

* Symmetrical body.
* Half-light / half-shadow palette.
* Reflective face mask.
* Echo ring aura.

#### Archmage

* Taller silhouette.
* Gold/arcane aura.
* More floating runes.
* Stronger casting animation.

#### Eightfold Warden

* Large barrier presence.
* Eight orbiting locus stones.
* Heavy cloak.
* Deep violet/gold palette.
* Last Stand cracks.

### 10.5 Player wizard

The player wizard can be simpler than enemies, but should still feel alive.

Minimum:

* Blue/purple base palette.
* Visible casting hands.
* Subtle idle aura.
* Cast wind-up.
* Victory and defeat reaction.

---

## 11. Composite magic effects

### 11.1 Spell effect structure

Each attack projectile should be assembled from reusable layers.

Minimum projectile parts:

```text
spell_root
  core_glyph
  inner_glow
  outer_aura
  trail
  sparkle_particles
  distortion_ring
```

Impact parts:

```text
impact_root
  impact_flash
  shockwave_ring
  ward_ripple
  fragments
  result_mask_swirl
```

Feedback parts:

```text
feedback_root
  fracture_glyphs
  echo_rings
  fade_motes
  count_chips
```

### 11.2 Essence-specific visual language

Each essence should have a distinct projectile identity.

#### Flame

* Core: angular ember.
* Aura: orange/red flicker.
* Trail: sparks.
* Motion: slight wobble and flare.

#### Frost

* Core: crystal shard.
* Aura: pale blue glow.
* Trail: snow motes.
* Motion: sharp linear glide.

#### Storm

* Core: lightning fork.
* Aura: electric field.
* Trail: jagged arcs.
* Motion: jitter.

#### Stone

* Core: floating rune rock.
* Aura: dust ring.
* Trail: small debris.
* Motion: heavy thump.

#### Light

* Core: radiant circle.
* Aura: gold-white bloom.
* Trail: soft rays.
* Motion: clean expansion.

#### Shadow

* Core: dark crescent.
* Aura: smoky violet.
* Trail: inward smoke.
* Motion: slight phase/flicker.

#### Vine

* Core: curled tendril.
* Aura: green living glow.
* Trail: leaf specks.
* Motion: curling path.

#### Metal

* Core: faceted shard.
* Aura: silver edge.
* Trail: glints.
* Motion: sharp straight slash.

#### Spirit

* Core: hollow eye/flame.
* Aura: pale cyan.
* Trail: wisps.
* Motion: drifting afterimage.

#### Arcane

* Core: impossible knot.
* Aura: violet/gold.
* Trail: rotating symbols.
* Motion: spiral.

### 11.3 Ward effect structure

Ward barriers should be composite too.

Minimum ward parts:

```text
ward_root
  outer_ring
  inner_ring
  rotating_runes
  barrier_surface
  shield_gradient
  hidden_locus_glow
  impact_mask
  crack_layer
  instability_layer
  break_particles
```

Ward states:

* Stable.
* Pressured.
* Impacted.
* Fractured.
* Unstable Last Stand.
* Broken.

Important:

Hidden locus glow must not reveal actual hidden pattern. Any locus-like visual in the ward is decorative only.

---

## 12. UI skin system

Create a coherent UI skin, not ad-hoc grey controls.

### 12.1 Panels

Panel style:

* Rounded rectangles.
* Rich dark blue/purple base.
* Slight inner glow.
* Soft drop shadow.
* Thin bright accent border.
* Consistent padding.

Panel types:

* Primary battle panel.
* Secondary info panel.
* History sheet.
* Help modal.
* Result modal.
* Settings panel.

### 12.2 Buttons

Button style:

* Chunky.
* Rounded.
* High contrast.
* Strong pressed state.
* Glow when primary.
* Disabled state clearly visible.
* 1–2 frame/tween bounce on tap.

Primary Cast button:

* Largest button on duel screen.
* Circular or gem-like.
* Clearly disabled before min cast time.
* Glows/pulses when ready.
* Pulses faster near auto-cast.

### 12.3 Essence tokens

Essence tokens should feel like collectible magical puzzle pieces.

Each token:

* Circular/gem-like or shaped medallion.
* Distinct internal glyph.
* Saturated colour.
* Highlight ring when selected.
* Pop animation on placement.
* Disabled overlay if not legal.
* Small label or icon support.

### 12.4 Locus sockets

Loci should feel like magical coordinates.

Each socket:

* Large enough to tap.
* Shows locus name.
* Shows unique locus rune.
* Empty state is clear.
* Filled state holds essence token.
* Selected state pulses.
* Invalid state shakes.

### 12.5 Timers

Timers must be visual, not just text.

Use:

* Circular charge ring.
* Horizontal cast bar.
* Colour shift as max time approaches.
* Pulse at warning thresholds.

Text should support the timer, not replace it.

Example labels:

* “Cast ready”
* “Auto-cast soon”
* “Rival casting”

---

## 13. Screenshot QA system

### 13.1 Purpose

Cursor must not simply “make it look nicer” subjectively. It must create a repeatable screenshot capture and assessment workflow.

The workflow must produce evidence that visuals improved.

### 13.2 Required files

Create:

```text
docs/VISUAL_PRD.md
docs/VISUAL_QA.md
tools/capture_visual_qa.sh
tools/visual_qa_report.py
qa/screenshots/baseline/
qa/screenshots/current/
qa/reports/
qa/montages/
```

File names can vary if the project already has a better convention, but the workflow must be documented.

### 13.3 Required screenshot states

Capture screenshots for:

1. Main menu.
2. Difficulty select.
3. Encounter select.
4. Ward setup.
5. Duel start.
6. Duel mid-state with 2–3 attacks.
7. Duel dense-state with several history rows.
8. Cast ready state.
9. Auto-cast warning state.
10. Attack impact state.
11. Feedback reveal state.
12. Last Stand state.
13. Victory result.
14. Defeat result.
15. Clash or Stalemate result if easy to script.

Screenshots must be deterministic where possible.

Use scripted scenes or debug hooks if necessary.

### 13.4 Screenshot naming

Use clear names:

```text
01_main_menu.png
02_difficulty_select.png
03_encounter_select.png
04_ward_setup.png
05_duel_start.png
06_duel_mid.png
07_duel_dense_history.png
08_cast_ready.png
09_auto_cast_warning.png
10_attack_impact.png
11_feedback_reveal.png
12_last_stand.png
13_victory.png
14_defeat.png
15_clash.png
```

### 13.5 Screenshot montage

Generate a montage image showing all current screenshots.

Also generate before/after montages where possible:

```text
qa/montages/baseline_grid.png
qa/montages/current_grid.png
qa/montages/before_after_grid.png
```

---

## 14. Visual QA assessment framework

Each screenshot must be scored 1–5 in each category.

### 14.1 Readability

Score 1:

* Player cannot tell what matters.
* Too much text.
* Labels compete.
* Controls unclear.

Score 5:

* Main action is obvious in two seconds.
* Text is minimal.
* Important state is readable.
* No cognitive overload.

### 14.2 Visual hierarchy

Score 1:

* Everything has equal weight.
* No clear focal point.
* History/log dominates.

Score 5:

* Rival ward, latest result and Cast button dominate.
* Secondary info is visibly secondary.
* Eye flow is intentional.

### 14.3 Mobile usability

Score 1:

* Tiny controls.
* Crowded tap targets.
* Desktop-style layout.

Score 5:

* Touch targets are large.
* Bottom action area is comfortable.
* Layout is portrait-first.
* Safe areas respected.

### 14.4 Excitement / juice

Score 1:

* Static.
* Grey.
* No impact.
* No satisfying feedback.

Score 5:

* Bright and inviting.
* Actions pop.
* Magic feels alive.
* Casts and impacts are satisfying.

### 14.5 Magical identity

Score 1:

* Looks like a generic UI or raw Mastermind board.

Score 5:

* Looks like a distinctive magical ward duel.
* Wards, essences, runes and barriers define the screen.
* The Mastermind structure is hidden.

### 14.6 Information density

Score 1:

* Wall of text.
* Too many visible rows.
* Help and history overwhelm play.

Score 5:

* Only current decision-critical information is prominent.
* History is compact/collapsed.
* Help is available but not intrusive.

### 14.7 Feedback clarity

Score 1:

* Fracture/Echo/Fade unclear.
* Feedback appears positional or misleading.
* Player cannot interpret results.

Score 5:

* Aggregate result is instantly clear.
* Each feedback type has distinct icon/shape/motion.
* No information leak.

### 14.8 Accessibility

Score 1:

* Colour-only meaning.
* Low contrast.
* Tiny text.

Score 5:

* Colour, shape, icon and text all support meaning.
* Contrast is strong.
* Motion can be reduced.
* Text is readable.

### 14.9 Overall polish

Score 1:

* Prototype/debug feel.

Score 5:

* Cohesive, intentional mobile game presentation.

### 14.10 Pass thresholds

Before this phase can be considered complete, every core screen must score at least:

```text
Readability: 4
Visual hierarchy: 4
Mobile usability: 4
Excitement / juice: 4
Magical identity: 4
Feedback clarity: 4
Accessibility: 4
Overall polish: 4
```

If a screen scores below 4 in any category, Cursor must record why and perform another improvement pass.

---

## 15. Automated visual metrics

In addition to subjective scoring, add simple automated metrics where practical.

The visual QA script should attempt to calculate:

### 15.1 Text density

Metric:

* Approximate number of visible Label/Button text nodes.
* Total visible character count.
* Number of visible history rows.

Targets for duel screen:

* Persistent visible text nodes: aim below 30.
* Persistent visible character count: aim below 500.
* Default visible history rows: 3 player rows or fewer, plus latest rival summary.

### 15.2 Touch target audit

Metric:

* List visible buttons / tappable controls.
* Flag controls smaller than 48 × 48 at reference resolution.
* Flag primary controls smaller than required.

Targets:

* No important target below 48 × 48.
* Cast button at least 96 × 96.
* Essence/locus targets at least 72 × 72.

### 15.3 Grey dominance

Metric:

* Estimate percentage of pixels that are low-saturation grey.
* Flag screens that are visually dominated by flat grey.

Target:

* Main duel screen should not be dominated by flat neutral grey.
* Background can be dark, but should have hue, gradient, depth and magical atmosphere.

### 15.4 Contrast audit

Metric:

* Audit known UI text colours against panel/background colours.
* Use defined theme colours rather than screenshot OCR where easier.

Target:

* Normal UI text contrast at least 4.5:1.
* Large status text contrast at least 3:1.
* Critical controls visually distinct from background.

### 15.5 Non-leak audit

Metric:

* Inspect feedback payloads and UI nodes.
* Confirm no per-locus feedback classification is exposed to animation or display.

Target:

* Feedback passed to UI as aggregate counts only.
* No arrays like `[fracture, fade, echo, fracture]`.
* No feedback icons positioned under exact loci.

### 15.6 Report output

Generate:

```text
qa/reports/visual_qa_latest.md
qa/reports/visual_metrics_latest.json
```

The report should include:

* Screenshot list.
* Scores.
* Failing categories.
* Automated metric warnings.
* Before/after notes.
* Remaining issues.

---

## 16. Cursor visual improvement process

Cursor must work iteratively.

### 16.1 Baseline capture

Before changing visuals:

1. Run the game.
2. Capture baseline screenshots.
3. Generate baseline montage.
4. Write baseline assessment.

### 16.2 First redesign pass

Focus on:

* Layout.
* Text reduction.
* Panel hierarchy.
* Touch target sizing.
* Cast button prominence.
* History collapse.
* Colour palette.

### 16.3 Second redesign pass

Focus on:

* Composite sprites.
* Essence tokens.
* Ward visuals.
* Feedback chips.
* Character presence.

### 16.4 Third redesign pass

Focus on:

* Attack animations.
* Barrier impacts.
* Particles.
* UI juice.
* Result screen polish.

### 16.5 Final QA pass

1. Capture current screenshots.
2. Generate current montage.
3. Score against rubric.
4. Compare before/after.
5. Fix any category below 4.
6. Update docs.

Do not stop after one superficial pass.

---

## 17. Specific implementation requirements

### 17.1 Theme constants

Create a central visual theme file if one does not already exist.

Example:

```text
godot_project/client/scripts/visual_theme.gd
```

It should define:

* Background colours.
* Panel colours.
* Accent colours.
* Feedback colours.
* Essence colours.
* Font sizes.
* Standard spacing.
* Standard touch target sizes.
* Animation durations.

Avoid hardcoding visual constants across many files.

### 17.2 UI components

Create reusable UI components where practical:

```text
components/essence_token.gd
components/locus_socket.gd
components/feedback_chip.gd
components/cast_button.gd
components/cast_timer.gd
components/history_row.gd
components/ward_barrier.gd
components/composite_wizard.gd
```

The goal is consistency and maintainability.

### 17.3 Composite asset generator

Update or replace the existing draft sprite generation system so it produces layered assets.

Suggested output:

```text
assets/generated/composite/wizards/
assets/generated/composite/effects/
assets/generated/composite/wards/
assets/generated/composite/ui/
assets/generated/composite/essences/
assets/generated/composite/loci/
```

Character parts:

```text
blue_apprentice/head.png
blue_apprentice/torso.png
blue_apprentice/left_upper_arm.png
blue_apprentice/left_forearm.png
blue_apprentice/left_hand.png
blue_apprentice/right_upper_arm.png
blue_apprentice/right_forearm.png
blue_apprentice/right_hand.png
blue_apprentice/cloak_back.png
blue_apprentice/cloak_front.png
blue_apprentice/aura.png
blue_apprentice/eyes.png
```

Magic parts:

```text
flame/core.png
flame/aura.png
flame/trail.png
flame/spark.png
flame/impact.png
```

Ward parts:

```text
ward/outer_ring.png
ward/inner_ring.png
ward/runes.png
ward/surface.png
ward/cracks.png
ward/instability.png
```

### 17.4 Procedural generation style

If generating assets procedurally, use simple but polished shapes:

* Gradients.
* Stroke outlines.
* Highlights.
* Drop shadows.
* Glow layers.
* Radial rings.
* Starbursts.
* Runes.
* Spark particles.
* Soft masks.

Avoid plain flat rectangles and tiny coloured squares.

### 17.5 Animation implementation

Use Godot tweens / AnimationPlayer for:

* Button bounce.
* Essence placement pop.
* Cast button ready pulse.
* Wizard idle breathing.
* Hand glow.
* Projectile launch.
* Ward impact.
* Feedback reveal.
* Result celebration.

Animations must be short and responsive.

Recommended timings:

```text
Button press feedback: 0.08–0.14s
Essence placement pop: 0.12–0.20s
Cast wind-up: 0.25–0.45s
Projectile travel: 0.35–0.65s
Impact mask swirl: 0.25–0.45s
Feedback reveal: 0.35–0.70s
Victory burst: 0.8–1.5s
```

### 17.6 Reduce motion

All major animations must respect reduce motion.

In reduce-motion mode:

* Remove screen shake.
* Reduce particle count.
* Replace large movement with fade/scale.
* Keep feedback readable.

---

## 18. Revised main duel UI acceptance standard

The main duel screen passes only if:

1. It is clearly portrait mobile-first.
2. Rival ward is visually dominant in the top section.
3. Latest feedback is obvious and aggregate.
4. Player attack builder is large and touch-friendly.
5. Cast button is visually prominent.
6. Current cast timer is visual, not just text.
7. History is compact by default.
8. Help text is hidden behind tap/overlay.
9. No visible element looks like raw debug UI.
10. The screen uses a cohesive magical palette.
11. Buttons and tokens are chunky and satisfying.
12. Feedback does not leak positional information.
13. Screenshot QA score is at least 4 in all required categories.

---

## 19. Revised battle flow visual standard

### 19.1 Player selects essence

Expected feel:

* Token lifts or glows.
* Locus socket pulses.
* On placement, token pops into socket.
* Soft sound/haptic.

### 19.2 Cast becomes ready

Expected feel:

* Cast button lights up.
* Ring completes.
* Short “ready” shimmer.
* No excessive text.

### 19.3 Player casts

Expected feel:

* Wizard hands rise.
* Locus sockets flash.
* Essence bolts form.
* Cast button depresses/bursts.
* Projectiles launch.

### 19.4 Attack hits ward

Expected feel:

* Ward receives all bolts together.
* Individual impacts are masked.
* Shield ripples.
* Runes spin.
* Impact flash.

### 19.5 Feedback appears

Expected feel:

* Result cluster bursts out.
* Fracture / Echo / Fade chips appear.
* Chips count up or pop.
* Result is readable within one second.
* History updates quietly.

### 19.6 Auto-cast warning

Expected feel:

* Cast ring pulses faster.
* Attack builder glows unstable.
* Subtle warning sound.
* If auto-cast fires, empty sockets fill with clear auto-fill effect.

### 19.7 Last Stand

Expected feel:

* Ward cracks but remains alive.
* Aura becomes unstable.
* Timer/final-cast indicator appears.
* Music or pulse intensifies.
* Player understands danger without long text.

---

## 20. Out of scope

Do not add these in the visual polish phase:

* New combat rules.
* New mana/HP system.
* Online multiplayer.
* Shop.
* Ads.
* In-app purchases.
* Large campaign map.
* Complex narrative scenes.
* Full hand-painted art dependency.
* Slot-specific feedback.
* Anything that changes the deduction information model.

This phase is about visual clarity, game feel and presentation.

---

## 21. Deliverables

Cursor must deliver:

1. New visual PRD saved in docs.
2. Screenshot capture tooling.
3. Screenshot QA rubric.
4. Baseline screenshots.
5. Improved screenshots.
6. Before/after montage.
7. Composite sprite generator or generated composite asset set.
8. Updated duel UI.
9. Updated menu / setup / result visuals.
10. Updated feedback chip visuals.
11. Updated attack and barrier animations.
12. Updated settings support for reduce motion.
13. Visual QA report.
14. Passing tests.
15. Manual notes on remaining weaknesses.

---

## 22. Testing requirements

All existing gameplay tests must still pass.

Additional tests/checks:

1. Screenshot capture script runs without manual interaction.
2. Visual QA report is generated.
3. No critical touch target below minimum.
4. Feedback payload remains aggregate-only.
5. Reduce motion mode disables major motion.
6. History defaults to collapsed/compact mode.
7. Help text is not permanently cluttering duel view.
8. Cast button is disabled before min cast time and visually ready after.
9. Auto-cast warning is visible.
10. Result screen displays correctly.

---

## 23. Definition of done

This visual polish phase is done when:

* The game no longer resembles the current grey debug prototype.
* The main duel screen is readable in a two-second glance.
* The player can identify the Cast button immediately.
* The player can understand latest Fracture/Echo/Fade result quickly.
* History is useful but not overwhelming.
* The rival ward and attack impact feel like the centre of play.
* Composite wizards feel alive through layered motion.
* Essence attacks feel magical and satisfying.
* Screenshot QA exists and is documented.
* Before/after screenshots show an obvious improvement.
* Visual QA scores meet the required threshold.
* The Mastermind information limit is preserved.

The target is not perfect final commercial art. The target is:

> A visibly polished, juicy, mobile-first magical duel that is good enough to show someone without explaining that it is “just a prototype.”

