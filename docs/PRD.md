# PRD — Duel Master Battle: Real-Time Wizard Ward Duel

## 1. Product summary

**Duel Master Battle** is a mobile-first real-time wizard duel game built on a hidden-pattern deduction ruleset.

The underlying game logic is inspired by Mastermind, but the finished product must not feel like a board-game clone. The player experience should feel like two rival wizards shaping magical attacks and firing them into each other’s defensive wards under time pressure.

The player secretly sets a magical ward pattern, then attacks the opponent’s ward by casting patterns of magical essences into named abstract loci. Each attack returns aggregate feedback only: how many essences were exactly correct, how many were present but displaced, and how many had no effect.

The final product must include:

* Real-time Human vs Bot duel play.
* Mobile-first touch interface.
* Difficulty selection: Easy, Medium, Hard.
* Encounter progression from simple tutorial duels to full Archmage duels.
* Strong visual identity that hides the original Mastermind-like structure.
* Fully implemented attack, barrier and feedback animations.
* Accessibility-safe feedback using motion, iconography, labels and sound, not colour alone.
* Exportable/publishable mobile build.
* Automated tests and manual QA gates.

---

## 2. Current project baseline

The existing project already includes:

* Python prototype rules.
* Godot playable Human vs Bot implementation.
* Encounter-driven rulesets.
* Four current encounters: Blue Apprentice, Thorn Adept, Mirror Mage, Archmage Duel.
* Magic pools, slot counts, attack limits and bot difficulty.
* Godot UI smoke tests.
* Draft placeholder sprites and icons.
* Local web export script.
* Current alternating-turn flow.

This PRD supersedes the current alternating-turn model.

The finished game must move to:

> Real-time magical ward duels with independent cast timers for both player and bot.

---

## 3. Product vision

The game should feel like:

> A tense, readable, mobile-friendly magical duel where the player is trying to read, crack and break an enemy wizard’s ward before their own ward collapses.

The player should not feel like they are arranging pegs.

They should feel like they are:

* Reading enemy ward reactions.
* Choosing magical essences.
* Shaping a ritual attack.
* Timing casts under pressure.
* Watching attacks collide with a living magical barrier.
* Learning from cracks, echoes and fading impacts.
* Breaking the enemy’s hidden pattern.

---

## 4. Design pillars

### 4.1 Mask the source game

The finished visual and UX language must avoid obvious Mastermind framing.

Avoid:

* Pegs.
* Pins.
* Rows of coloured dots as the primary fantasy.
* “Guess” language.
* “Code” language.
* Static board-game presentation.

Use:

* Wards.
* Loci.
* Essences.
* Attacks.
* Fractures.
* Echoes.
* Fades.
* Cast windows.
* Barrier impacts.
* Wizard rivals.

### 4.2 Preserve Mastermind information limits

This is a hard rule.

The visual language must not reveal more information than original Mastermind feedback.

An attack may reveal:

* Number of exact matches.
* Number of correct essence/wrong locus matches.
* Number of misses.

An attack must not reveal:

* Which specific locus was exactly correct.
* Which specific locus contained a displaced essence.
* Which specific projectile caused which feedback result.
* Whether a particular visible projectile was the one that fractured the ward.
* Any hidden opponent pattern information not earned through aggregate feedback.

Core rule:

> Attacks may travel positionally, but feedback must resolve non-positionally.

Example:

Allowed:

> Four attack bolts fly into the barrier. The barrier swirls, masks the impacts, then reveals 2 Fractures, 1 Echo and 1 Fade as a grouped result.

Not allowed:

> The Roach bolt cracks the barrier, Uzag fades, Lieana echoes and Gyse cracks.

### 4.3 Real-time tension, not action chaos

The game is real-time, but not twitch combat.

The player is under time pressure to reason, choose essences and cast, but the core skill remains deduction.

The game should feel tense, legible and fair.

### 4.4 Mobile-first

The game must be designed primarily for portrait mobile play.

Controls must be:

* Finger-friendly.
* Clear at small screen sizes.
* Usable one-handed where practical.
* Readable without hover states.
* Robust against accidental taps.

### 4.5 Clear, satisfying feedback

Every attack should feel good to watch.

Even a bad attack should produce a satisfying magical interaction.

The player should understand the result from:

* Animation.
* Iconography.
* Text label.
* Sound.
* History row.

---

## 5. Core terminology

Replace the current user-facing terminology throughout the game.

| Existing / generic term | Final game term |
| ----------------------- | --------------- |
| Peg / colour            | Essence         |
| Slot / point            | Locus           |
| Secret code             | Ward pattern    |
| Guess                   | Attack pattern  |
| Submit guess            | Cast attack     |
| Exact match             | Fracture        |
| Colour-only match       | Echo            |
| Miss / no match         | Fade            |
| Bot                     | Rival wizard    |
| Max guesses             | Attack limit    |
| Turn                    | Cast window     |
| Draw                    | Stalemate       |
| Mutual solve            | Clash           |

Internal code may keep some legacy terms temporarily, but final UI text, docs and visible labels must use the final game terms.

---

## 6. Core game rules

### 6.1 Ward pattern

Each duelist secretly creates a ward pattern.

A ward pattern is made by placing magical essences into named loci.

A duel may use between 1 and 8 loci.

The standard full game uses 4 loci.

The maximum supported system must be 8 loci.

### 6.2 Loci

The default locus names are:

1. Roach
2. Uzag
3. Lieana
4. Gyse
5. Vorr
6. Mael
7. Oshen
8. Keth

Encounters choose how many of these are active.

Example:

* 1-locus duel: Roach only.
* 2-locus duel: Roach, Uzag.
* 4-locus duel: Roach, Uzag, Lieana, Gyse.
* 8-locus boss duel: all eight loci.

These names should be treated as abstract magical concepts, not physical objects.

### 6.3 Essences

Essences replace colours.

The existing ten magic types may remain as the first production essence set:

1. Flame
2. Frost
3. Storm
4. Stone
5. Light
6. Shadow
7. Vine
8. Metal
9. Spirit
10. Arcane

Each essence must have:

* Name.
* Icon.
* Colour treatment.
* Shape/silhouette.
* Small motion identity.
* Accessible text label.
* Optional short sound cue.

Colour must never be the only identifier.

### 6.4 Attack pattern

An attack pattern is a player-selected sequence of essences across the active loci.

Example:

* Roach: Flame
* Uzag: Frost
* Lieana: Shadow
* Gyse: Vine

When cast, this attack is compared to the opponent’s hidden ward pattern.

### 6.5 Feedback scoring

Feedback uses multiset Mastermind scoring.

For each attack, calculate:

* **Fracture**: correct essence in the correct locus.
* **Echo**: correct essence exists in the ward but in a different locus, after Fractures have already been accounted for.
* **Fade**: no useful match remaining.

The total must always equal the active locus count.

Example for a 4-locus duel:

* 2 Fractures
* 1 Echo
* 1 Fade

The UI may display the result as:

> 2 Fractures · 1 Echo · 1 Fade

or:

> The ward cracks twice. One essence echoes. One fades.

### 6.6 Repeats

Each encounter defines whether repeated essences are allowed.

If repeats are disabled:

* The player cannot place the same essence in more than one active locus.
* The bot must also obey this rule.
* Auto-cast must obey this rule.

If repeats are enabled:

* Any legal essence may be used in multiple loci.
* Scoring must use correct multiset logic.

### 6.7 Secret pool and attack pool

Each duelist has two pools:

* **Secret pool**: essences allowed in that duelist’s hidden ward.
* **Attack pool**: essences allowed in that duelist’s attacks.

For standard v1 encounters:

> Secret pool must be a subset of attack pool.

This ensures every ward is solvable using available attack essences.

Some lower-level enemies may only use restricted pools.

Example:

* Ember Novice can only use Flame, Stone and Light.
* Thorn Adept can only use Vine, Stone, Flame, Frost.
* Archmage can use all ten essences.

Advanced hidden secret types are out of scope for v1.

---

## 7. Real-time duel model

### 7.1 Replacement for alternating turns

The current alternating turn model must be replaced.

Both duelists act independently in real time.

Each duelist has a repeating **Cast Window**.

A Cast Window begins immediately after:

* The duel starts, or
* The duelist’s previous attack has been cast and resolved.

During each Cast Window:

1. The duelist prepares an attack pattern.
2. The duelist cannot cast before their minimum cast time has elapsed.
3. Once the minimum cast time has elapsed, the duelist may cast at any point.
4. If the maximum cast time is reached, the game auto-casts a legal attack.
5. A new Cast Window begins after the attack resolves.

### 7.2 Minimum cast time

Each duelist has:

```text
min_cast_time_seconds
```

This prevents:

* Human spam attacks.
* Bot instant attacks.
* Unreadable attack chains.

The cast button is disabled until the minimum cast time has elapsed.

The UI should show the player when casting becomes available.

### 7.3 Maximum cast time

Each duelist has:

```text
max_cast_time_seconds
```

If the duelist has not cast by this time, an attack is automatically cast.

For the human player:

* If the player has selected a complete legal pattern, cast it.
* If the player has selected a partial pattern, fill empty loci with random legal essences, then cast.
* If the player has selected nothing, generate a full random legal attack.

For the bot:

* If the bot has a selected solver attack ready, cast it.
* If no valid solver attack is ready, cast a random legal attack.

### 7.4 Cast window examples

Easy opponent:

```text
min_cast_time_seconds = 8
max_cast_time_seconds = 24
```

Medium opponent:

```text
min_cast_time_seconds = 5
max_cast_time_seconds = 16
```

Hard opponent:

```text
min_cast_time_seconds = 3
max_cast_time_seconds = 10
```

Boss opponent:

```text
min_cast_time_seconds = 2
max_cast_time_seconds = 8
```

These are starting values and should be tuned through playtesting.

### 7.5 Attack resolution timing

Each attack has a short animation and resolution period.

Recommended attack sequence:

1. Cast wind-up.
2. Essence bolts form.
3. Bolts travel toward enemy ward.
4. Barrier absorbs/masks impact.
5. Aggregate feedback appears.
6. History row is added.
7. Next Cast Window starts.

The game may continue both players’ timers during attack animations, but must remain readable.

For v1, the safer implementation is:

* A duelist’s own next Cast Window starts after their attack result is logged.
* The opponent’s Cast Window continues independently unless they are in a blocking animation.
* If both attacks resolve close together, process by timestamp order.

### 7.6 Simultaneous attacks

If both duelists cast at effectively the same time:

* Both attacks should be allowed to resolve.
* If one or both attacks break a ward, resolve using the win condition rules.
* No attack should be cancelled simply because the other player attacked first within the same short timing frame.

Implementation should use a small deterministic ordering rule:

```text
If cast timestamps differ, earlier timestamp resolves first.
If cast timestamps are identical, resolve player first for deterministic local play.
If both attacks break wards within the same resolution frame, result is Clash.
```

---

## 8. Difficulty selection

The main menu must offer:

* Easy
* Medium
* Hard

Difficulty should be selected separately from encounter.

The same encounter can therefore be played on different difficulties.

Example:

* Mirror Mage — Easy
* Mirror Mage — Medium
* Mirror Mage — Hard

### 8.1 Easy

Easy should feel forgiving.

Bot behaviour:

* Random or very basic legal attacks.
* Slow cast windows.
* May repeat poor attacks.
* Lower pressure.

Recommended values:

```text
bot_logic = easy_random
bot_min_cast_time_multiplier = 1.4
bot_max_cast_time_multiplier = 1.4
```

### 8.2 Medium

Medium should feel fair.

Bot behaviour:

* Candidate elimination.
* Uses feedback correctly.
* Moderate cast windows.
* Does not feel omniscient.

Recommended values:

```text
bot_logic = candidate_filter
bot_min_cast_time_multiplier = 1.0
bot_max_cast_time_multiplier = 1.0
```

### 8.3 Hard

Hard should feel dangerous but fair.

Bot behaviour:

* Strong solver logic.
* Faster cast windows.
* Avoids obviously wasteful attacks.
* Still obeys all timing limits.

Recommended values:

```text
bot_logic = capped_minimax
bot_min_cast_time_multiplier = 0.75
bot_max_cast_time_multiplier = 0.75
```

### 8.4 No instant bot solves

Even if the solver knows the best move instantly, the bot must still obey minimum cast time.

The player should never feel that the bot has superhuman mechanical speed.

---

## 9. Encounter model

Each encounter must be fully config-driven.

Required fields:

```text
encounter_id
encounter_name
enemy_name
enemy_title
enemy_archetype
enemy_visual_theme
locus_count
active_loci
secret_essence_pool
attack_essence_pool
allow_repeats
max_attacks_per_duelist
base_min_cast_time_seconds
base_max_cast_time_seconds
enemy_ai_profile
enemy_traits
player_traits
last_stand_rules
tutorial_flags
unlock_requirements
```

### 9.1 Built-in v1 encounters

#### Blue Apprentice

Purpose:

* First tutorial.
* Teaches choosing an essence and casting an attack.
* Uses 1 locus.

Rules:

```text
locus_count = 1
active_loci = [Roach]
essence_pool = [Flame, Frost, Storm]
allow_repeats = false
max_attacks_per_duelist = 4
enemy_ai_profile = easy
```

#### Thorn Adept

Purpose:

* Teaches two-locus deduction.
* Teaches that correct essence can be in wrong locus.

Rules:

```text
locus_count = 2
active_loci = [Roach, Uzag]
essence_pool = [Flame, Frost, Vine, Stone]
allow_repeats = false
max_attacks_per_duelist = 6
enemy_ai_profile = medium
```

#### Mirror Mage

Purpose:

* Teaches repeats and ambiguity.
* Introduces less obvious deduction.

Rules:

```text
locus_count = 3
active_loci = [Roach, Uzag, Lieana]
essence_pool = [Light, Shadow, Frost, Storm, Arcane]
allow_repeats = true
max_attacks_per_duelist = 8
enemy_ai_profile = medium_or_hard
```

#### Archmage Duel

Purpose:

* Full standard game.
* Main balance anchor.

Rules:

```text
locus_count = 4
active_loci = [Roach, Uzag, Lieana, Gyse]
essence_pool = [all 10 essences]
allow_repeats = true
max_attacks_per_duelist = 12
enemy_ai_profile = hard
```

### 9.2 Optional later boss encounters

The engine must support up to 8 loci, but the first published version does not need many 8-locus fights.

Potential boss:

#### The Eightfold Warden

```text
locus_count = 8
active_loci = [Roach, Uzag, Lieana, Gyse, Vorr, Mael, Oshen, Keth]
essence_pool = [all 10 essences]
allow_repeats = true
max_attacks_per_duelist = 18
enemy_ai_profile = hard
last_stand_seconds = 20
```

This should be treated as advanced content only.

---

## 10. Last Stand and comeback rules

### 10.1 Purpose

Last Stand creates dramatic endings and supports enemy identity.

Some duelists are not defeated immediately when their ward is broken.

Instead, they survive briefly and have a final chance to break the opponent’s ward.

### 10.2 Last Stand states

When a duelist’s ward is broken:

* If they have no Last Stand, they lose immediately.
* If they have Last Stand, they enter **Unstable Ward** state.
* During Unstable Ward, they may continue casting according to their cast windows.
* If they break the opponent’s ward during this state, the duel ends in Clash.
* If their Last Stand expires, they lose.

### 10.3 Last Stand fields

```text
last_stand_min_attacks
last_stand_seconds
```

Examples:

```text
last_stand_min_attacks = 1
last_stand_seconds = 0
```

The duelist always gets at least one final attack.

```text
last_stand_min_attacks = 0
last_stand_seconds = 12
```

The duelist survives for 12 seconds.

```text
last_stand_min_attacks = 1
last_stand_seconds = 10
```

The duelist survives until they have had one final attack, capped or supported by 10 seconds depending on final tuning.

### 10.4 Recommended interpretation

For v1, use this rule:

> A broken duelist with Last Stand is defeated only when both their required final attacks have been used and their final survival timer has expired.

This makes Last Stand clear and generous.

### 10.5 Counter-traits

Some duelists may modify Last Stand.

Examples:

#### Severance

Reduces opponent Last Stand time.

```text
opponent_last_stand_seconds_modifier = -5
```

#### Silence

Blocks attempt-based Last Stand.

```text
blocks_opponent_last_stand_min_attacks = true
```

#### Anchor

Guarantees at least one final cast after ward break.

```text
last_stand_min_attacks = 1
```

#### Haste

Reduces own minimum cast time.

```text
own_min_cast_time_modifier = -1.5
```

#### Pressure

Reduces opponent maximum cast time.

```text
opponent_max_cast_time_modifier = -3
```

For first release, traits should belong to encounters/enemies, not to a player build/loadout system.

---

## 11. Win and result states

### 11.1 Victory

The player wins when:

* The player breaks the enemy ward, and
* The enemy has no active Last Stand remaining.

### 11.2 Defeat

The player loses when:

* The enemy breaks the player ward, and
* The player has no active Last Stand remaining.

### 11.3 Clash

The duel ends in Clash when:

* Both wards are broken within the same simultaneous resolution frame, or
* A duelist breaks the opponent’s ward during Last Stand.

Clash is a dramatic draw.

### 11.4 Stalemate

The duel ends in Stalemate when:

* Both duelists exhaust their attack limits, and
* Neither ward has been broken.

### 11.5 No progress tie-break for v1

Do not use “best Fracture/Echo progress” to decide a winner in v1.

For v1:

> Solve wins. No solve means Stalemate.

This is cleaner, easier to explain, and fairer.

---

## 12. Attack limits

Each duelist has a maximum number of attacks.

```text
max_attacks_per_duelist
```

When a duelist has used all attacks:

* They cannot cast further attacks.
* Their opponent may continue if they still have attacks.
* If neither side can cast and no ward is broken, result is Stalemate.

Attack limits should be displayed clearly but thematically.

Suggested label:

> Stability remaining

or:

> Casts before collapse

Avoid exposing the system as “guesses left” in final UI.

---

## 13. Mobile UX

### 13.1 Orientation

Primary target:

* Portrait mobile.

Optional:

* Landscape tablet/desktop support.

### 13.2 Main duel screen layout

Recommended portrait layout from top to bottom:

1. Enemy wizard portrait and ward barrier.
2. Enemy cast timer.
3. Shared attack result animation space.
4. Player attack builder.
5. Player cast timer and Cast button.
6. Compact history panel, expandable if needed.

The player must always be able to see:

* Their current attack pattern.
* Active loci.
* Available essences.
* Cast availability.
* Time remaining before auto-cast.
* Latest attack result.
* Enemy attack pressure.

### 13.3 Touch interaction

The player builds an attack by selecting a locus and choosing an essence.

Alternative mobile-friendly pattern:

* Tap a locus socket.
* Essence wheel or tray opens.
* Tap essence.
* Socket fills.
* Repeat.
* Cast when available.

For speed, also support:

* Drag essence to locus.
* Tap already-filled locus to replace.
* Long press or small clear button to empty locus.

### 13.4 Auto-cast warning

When max cast time is close, the UI must warn the player.

Example:

* At 5 seconds remaining: timer pulses.
* At 3 seconds remaining: warning sound.
* At 1 second remaining: attack pattern glows unstable.
* At 0: auto-cast.

Do not make this stressful in tutorial encounters.

### 13.5 History

Each attack history row should show:

* Attack essences by locus.
* Aggregate result only.
* Time cast.
* Whether it was manual or auto-cast.

Important:

The history may show what the player attacked with by locus, because the player chose that attack.

But the result shown beside it must remain aggregate and non-positional.

Example:

```text
Attack 5: Flame / Frost / Shadow / Vine
Result: 2 Fractures · 1 Echo · 1 Fade
```

Do not align feedback icons under specific loci.

---

## 14. Visual identity

### 14.1 Target feel

The finished game should feel:

* Arcane.
* Abstract.
* Strange.
* Readable.
* Mobile-polished.
* Slightly ritualistic.
* Not generic medieval fantasy.

Avoid overused fantasy props:

* Staff.
* Spell book.
* Wand.
* Cauldron.
* Robe as main identity.
* Generic fireball-only spell combat.

Use abstract magical forms:

* Floating loci.
* Ward geometry.
* Essence glyphs.
* Fracture patterns.
* Echo rings.
* Dissolving motes.
* Ritual circles.
* Living barriers.
* Impossible symbols.

### 14.2 Visual grammar

The visual grammar must map consistently:

| Concept        | Visual treatment                               |
| -------------- | ---------------------------------------------- |
| Locus          | Named socket / rune node                       |
| Essence        | Distinct glyph-orb with colour, shape and icon |
| Ward pattern   | Hidden barrier geometry                        |
| Attack pattern | Sequence of essence bolts                      |
| Fracture       | Sharp crack / bright rupture                   |
| Echo           | Resonant ring / displaced shimmer              |
| Fade           | Dissolve / ash / absorption                    |
| Last Stand     | Broken unstable barrier, pulsing collapse      |
| Auto-cast      | Unstable forced release                        |
| Cast window    | Growing ritual charge                          |

### 14.3 Barrier feedback

Every attack should hit the opponent’s barrier.

Resolution must work like this:

1. Attack bolts fly toward enemy.
2. Barrier absorbs all bolts.
3. Barrier masks the individual impacts.
4. Barrier swirls/recombines.
5. Aggregate feedback appears as grouped Fractures, Echoes and Fades.

The feedback may appear:

* Around the barrier.
* In a central result glyph.
* As three grouped counters.
* As floating signs that are deliberately shuffled/non-positional.

### 14.4 Non-leak animation rule

The animation must never imply:

* “This locus was correct.”
* “This projectile caused this Fracture.”
* “This essence is definitely in the opponent’s ward at this locus.”

Allowed animation:

* All bolts hit.
* Barrier swirls.
* Grouped result signs appear.

Not allowed animation:

* First bolt cracks.
* Second bolt fades.
* Third bolt echoes.
* Fourth bolt cracks.

### 14.5 Essence visual design

Each essence needs a distinct identity.

Example production direction:

#### Flame

* Angular ember glyph.
* Flickering edge.
* Warm burst sound.

#### Frost

* Crystalline glyph.
* Sharp shimmer.
* Glassy sound.

#### Storm

* Forked line glyph.
* Jitter motion.
* Electric snap.

#### Stone

* Heavy block glyph.
* Slow pulse.
* Low thud.

#### Light

* Radiant circular glyph.
* Clean expansion.
* Bell tone.

#### Shadow

* Inverted crescent glyph.
* Smoke inward motion.
* Muted whisper.

#### Vine

* Curling tendril glyph.
* Organic growth motion.
* Soft snap.

#### Metal

* Faceted blade glyph.
* Hard reflection.
* Ringing sound.

#### Spirit

* Hollow eye glyph.
* Floating afterimage.
* Breath-like sound.

#### Arcane

* Impossible knot glyph.
* Rotating symbol.
* Complex chime.

### 14.6 Locus visual design

Loci should not look like normal equipment slots.

Each locus is an abstract named magical coordinate.

Suggested treatment:

* Roach: grounded, old, rough-edged rune.
* Uzag: vertical, jagged, forceful rune.
* Lieana: flowing, curved, elegant rune.
* Gyse: split, mirrored, unstable rune.
* Vorr: deep, circular, heavy rune.
* Mael: spiralling, kinetic rune.
* Oshen: wide, wave-like rune.
* Keth: sharp, final, sealing rune.

Each locus should have:

* Name label.
* Shape identity.
* Empty state.
* Filled state.
* Invalid state.
* Auto-filled state.

---

## 15. Audio and haptics

### 15.1 Audio goals

Audio should make the duel satisfying to watch and play.

Required sound classes:

* Essence select.
* Locus fill.
* Cast available.
* Cast wind-up.
* Attack launch.
* Barrier impact.
* Fracture.
* Echo.
* Fade.
* Auto-cast warning.
* Victory.
* Defeat.
* Clash.
* Stalemate.
* Last Stand activation.

### 15.2 Haptics

Mobile haptics should be used sparingly.

Suggested haptics:

* Light tap when placing essence.
* Medium pulse when casting.
* Sharp pulse for Fracture.
* Soft pulse for Echo.
* Low dull pulse for Fade.
* Warning pulse when auto-cast is imminent.
* Strong pulse on ward break.

Haptics must be optional in settings.

---

## 16. Accessibility requirements

The game must be playable without relying on colour alone.

Every essence must have:

* Label.
* Icon/glyph.
* Colour.
* Optional number/index.
* Distinct silhouette.

Every feedback result must have:

* Text label.
* Icon.
* Animation.
* Sound cue where possible.

Required settings:

* Reduce motion.
* Disable haptics.
* Disable screen shake.
* Larger text mode if practical.
* Colourblind-safe palette review.
* Audio independent from gameplay-critical feedback.

No gameplay-critical information may be available only through sound, colour or haptics.

---

## 17. Bot and AI requirements

### 17.1 AI profiles

Maintain or adapt the existing bot profiles:

* Easy: random/basic.
* Medium: candidate elimination.
* Hard: capped minimax or stronger solver.

The bot must obey:

* Encounter rules.
* Secret pool.
* Attack pool.
* Repeat rules.
* Attack limit.
* Minimum cast time.
* Maximum cast time.
* Last Stand rules.

### 17.2 Bot thinking in real time

The bot may calculate its next attack instantly internally, but it cannot cast before its minimum cast time.

If solver calculation is slow:

* Calculate asynchronously or during the cast window if needed.
* If no solver result is ready by max cast time, cast a random legal attack.
* Avoid freezing the UI.

### 17.3 Difficulty must be readable

Difficulty should feel different through:

* Cast speed.
* Solver strength.
* Mistake rate.
* Pressure.

Avoid making Hard feel unfair by giving hidden information.

The bot must never access information that a legal solver would not have.

---

## 18. Technical implementation requirements

### 18.1 Authoritative sim

The real-time duel must be controlled by an authoritative simulation layer, not scattered UI logic.

Create or update a Godot sim object responsible for:

* Duel state.
* Player ward.
* Enemy ward.
* Cast windows.
* Timers.
* Legal attack validation.
* Auto-cast.
* Attack resolution.
* Feedback scoring.
* Last Stand.
* Result states.
* History records.

The UI should render state and submit player actions.

### 18.2 Determinism

The sim should be deterministic when given:

* Ruleset.
* Difficulty.
* Seeds.
* Player inputs.
* Timestamps or tick deltas.

This supports testing and replay debugging.

### 18.3 Tick model

Use a fixed-step or carefully controlled process loop for duel timing.

The sim must expose:

```text
advance_time(delta_seconds)
submit_player_attack(pattern)
get_current_state()
```

Avoid tying core rules directly to frame rate.

### 18.4 Ruleset data model

Update ruleset support from 1–4 current points to 1–8 loci.

Required ruleset fields:

```text
id
display_name
enemy_name
enemy_title
locus_count
locus_names
secret_essence_pool
attack_essence_pool
allow_repeats
max_attacks_per_duelist
base_min_cast_time_seconds
base_max_cast_time_seconds
enemy_ai_profile
enemy_traits
player_traits
last_stand_min_attacks
last_stand_seconds
tutorial_flags
```

### 18.5 Difficulty profile data model

Create separate difficulty profiles:

```text
difficulty_id
display_name
bot_logic
bot_min_cast_time_multiplier
bot_max_cast_time_multiplier
bot_mistake_rate
bot_solver_cap
```

Difficulty is selected from the main menu and applied to the encounter.

### 18.6 Attack history record

Each attack should produce a structured history record:

```text
attacker_id
target_id
attack_number
cast_time
was_auto_cast
pattern_by_locus
fracture_count
echo_count
fade_count
broke_ward
triggered_last_stand
```

The UI must not display feedback positionally.

### 18.7 Animation events

The sim should emit clean events for animation:

```text
cast_started
attack_launched
attack_impacted
feedback_revealed
ward_broken
last_stand_started
duel_finished
```

The animation layer should consume these events without changing game rules.

---

## 19. Publishing requirements

### 19.1 Primary target

Primary target:

* Android mobile build.

Secondary targets:

* Desktop local build.
* Web export if practical.

iOS can remain future scope unless signing/build access is available.

### 19.2 Mobile build requirements

The finished mobile build must:

* Launch reliably on Android.
* Use portrait orientation by default.
* Scale correctly across common phone screen sizes.
* Avoid tiny controls.
* Avoid desktop-only hover interactions.
* Save basic settings.
* Return cleanly from pause/background.
* Maintain stable performance during attack animations.

### 19.3 Performance targets

Target:

* 60 FPS during normal play on a mid-range Android phone.
* No UI freeze during bot calculations.
* Attack resolution animation under 2 seconds unless deliberately slowed for tutorial.
* Main duel scene load under 3 seconds after initial launch where practical.

### 19.4 Build outputs

Required release outputs:

* Debug Android build.
* Release Android build.
* Local desktop build.
* Optional local web export.
* Release notes.
* Manual test log.

---

## 20. Content requirements

### 20.1 Minimum release content

The finished release should include at least:

* Tutorial duel.
* 3 progression encounters.
* Full Archmage Duel.
* Difficulty selection.
* Basic settings screen.
* Credits/about screen.
* Help/rules screen.

Minimum encounters:

1. Blue Apprentice.
2. Thorn Adept.
3. Mirror Mage.
4. Archmage Duel.
5. At least one visually distinct boss or advanced variant if time allows.

### 20.2 Tutorialisation

Tutorial must teach:

* What a locus is.
* What an essence is.
* How to set your ward.
* How to build an attack.
* What Fracture means.
* What Echo means.
* What Fade means.
* That feedback is aggregate, not positional.
* How real-time cast windows work.
* What auto-cast means.

Tutorial text must be short and mobile-readable.

### 20.3 Rules help screen

Include a permanent help screen explaining:

> Each attack tells you how many essences were exactly right, how many were present but displaced, and how many faded. It never tells you which specific locus caused each result.

This is essential because the visual language deliberately avoids positional feedback.

---

## 21. UI screens

### 21.1 Title screen

Contains:

* Game title.
* Start.
* Settings.
* Credits.

### 21.2 Encounter select

Contains:

* Encounter cards.
* Enemy name and title.
* Locus count.
* Essence pool preview.
* Repeat rule.
* Attack limit.
* Special trait summary.
* Start button.

### 21.3 Difficulty select

Can be either:

* Before encounter select, or
* On the encounter select screen.

Required choices:

* Easy.
* Medium.
* Hard.

Show short descriptions:

* Easy: slower rival, simpler attacks.
* Medium: balanced duel.
* Hard: faster rival, sharper deduction.

### 21.4 Ward setup screen

The player sets their hidden ward.

Requirements:

* Show active loci.
* Show legal essence pool.
* Enforce repeat rules.
* Validate complete ward before starting.
* Explain that this is the ward the enemy is trying to break.

### 21.5 Duel screen

The main game screen.

Required elements:

* Enemy portrait/barrier.
* Enemy cast timer.
* Enemy attack count remaining.
* Latest enemy attack result.
* Player attack builder.
* Player cast timer.
* Cast button.
* Player attack count remaining.
* Latest player attack result.
* Expandable history.
* Pause button.

### 21.6 Result screen

Result states:

* Victory.
* Defeat.
* Clash.
* Stalemate.

Show:

* Result title.
* Enemy defeated/not defeated.
* Number of attacks used by each side.
* Best/last attack summary.
* Retry.
* Change difficulty.
* Back to encounter select.

---

## 22. Visual production deliverables

Replace all placeholder art with production-ready mobile assets.

Required asset groups:

### 22.1 Characters

* Player wizard/avatar.
* Enemy wizard portraits for each encounter.
* At least one boss portrait.
* Silhouette and expression variants if practical.

### 22.2 Barriers and wards

* Player ward barrier.
* Enemy ward barrier.
* Idle state.
* Hit/impact state.
* Fractured state.
* Last Stand unstable state.
* Broken state.

### 22.3 Essence icons

* 10 production essence icons.
* Selected state.
* Disabled state.
* Invalid state.
* Small history version.
* Large attack version.

### 22.4 Locus icons

* 8 locus icons.
* Empty state.
* Filled state.
* Highlighted state.
* Auto-filled state.
* Invalid state.

### 22.5 Feedback icons

* Fracture.
* Echo.
* Fade.
* Clash.
* Stalemate.
* Last Stand.

### 22.6 UI skin

* Buttons.
* Panels.
* Timers.
* Progress rings.
* History rows.
* Modal windows.
* Tooltip/help cards.
* Settings toggles.

### 22.7 Animation assets

* Attack launch.
* Essence bolt travel.
* Barrier impact.
* Feedback reveal.
* Ward break.
* Last Stand activation.
* Victory/defeat result reveal.

---

## 23. Animation implementation requirements

### 23.1 Attack animation

Each attack must visibly travel from caster to target.

Recommended sequence:

1. Locus glyphs light up.
2. Essence bolts form.
3. Bolts braid or travel toward the target.
4. Barrier absorbs all bolts.
5. Barrier masks individual impacts.
6. Aggregate feedback signs appear.
7. Result row is added.

### 23.2 Feedback reveal

Feedback reveal must be aggregate.

For a 4-locus attack with 2 Fractures, 1 Echo, 1 Fade:

Allowed:

* Barrier shows two crack glyphs, one echo ring and one fade mote as a grouped cluster.

Not allowed:

* The first and fourth projectile visibly create cracks.

### 23.3 History animation

After feedback appears, compress the result into the history panel.

The history row should preserve:

* Attack pattern.
* Aggregate result.

It must not imply positional mapping.

### 23.4 Last Stand animation

When Last Stand begins:

* Enemy barrier visibly breaks but does not vanish.
* Barrier becomes unstable.
* Timer or final attack count appears.
* Music/sound intensity increases.
* Player clearly understands the enemy is nearly defeated but still dangerous.

---

## 24. Settings

Required settings:

* Sound volume.
* Music volume.
* Haptics on/off.
* Screen shake on/off.
* Reduce motion on/off.
* Text size if practical.
* Reset tutorial.
* Credits/about.

Optional settings:

* Colourblind palette.
* Left-handed layout.
* Battery saver animation mode.

---

## 25. Save data

Minimum save data:

* Tutorial completed.
* Encounters unlocked.
* Last selected difficulty.
* Settings.
* Best result per encounter/difficulty if simple to implement.

Save data should be local only for v1.

No account system is required.

---

## 26. Out of scope for first finished release

Do not add these before the core game is finished:

* Multiplayer.
* Online accounts.
* PvP matchmaking.
* Mana system.
* HP/damage system.
* Equipment.
* Deck-building.
* RPG levelling.
* Shop.
* Ads.
* In-app purchases.
* Procedural campaign map.
* Complex story mode.
* Hidden secret types not present in attack pool.
* Positional feedback variant.
* Player-build trait system.

These may be future expansions, but they would distract from finishing the core mobile game.

---

## 27. Testing requirements

### 27.1 Rules tests

Automated tests must cover:

* Fracture/Echo/Fade scoring.
* Repeats allowed.
* Repeats disallowed.
* Secret pool validation.
* Attack pool validation.
* 1-locus encounters.
* 2-locus encounters.
* 3-locus encounters.
* 4-locus encounters.
* 8-locus support.
* Illegal attacks rejected.
* Auto-cast creates legal attacks.
* Attack limit exhaustion.
* Victory.
* Defeat.
* Clash.
* Stalemate.
* Last Stand expiry.
* Last Stand comeback Clash.

### 27.2 Information leak tests

Add explicit tests or review checks for non-leak behaviour.

Required rule:

> Feedback data exposed to UI must contain only aggregate counts, not per-locus result classification.

The UI layer may know the submitted attack pattern by locus, but must not receive a per-locus feedback array.

The feedback payload should look like:

```text
fractures = 2
echoes = 1
fades = 1
```

It should not look like:

```text
[fracture, fade, echo, fracture]
```

### 27.3 Real-time sim tests

Tests must cover:

* Minimum cast time blocks casting.
* Casting becomes legal after min time.
* Auto-cast occurs at max time.
* Partial human pattern is filled legally at max time.
* Bot casts by max time.
* Timers reset after attack resolution.
* Simultaneous attacks resolve deterministically.
* Bot cannot cast faster than allowed.
* Pausing does not consume cast time.

### 27.4 UI smoke tests

Update existing Godot UI smoke tests to include:

* Difficulty select.
* Encounter select.
* Ward setup.
* Real-time duel start.
* Player cast blocked before min time.
* Player cast enabled after min time.
* Auto-cast path.
* Attack animation event.
* Feedback appears.
* History row appears.
* Result screen.

### 27.5 Mobile manual test checklist

Manual QA must cover:

* Small Android phone.
* Large Android phone.
* Tablet if available.
* Portrait layout.
* App background/resume.
* Audio settings.
* Haptics setting.
* Reduce motion.
* Tutorial completion.
* Full Archmage Duel.
* At least one Easy, Medium and Hard duel.
* Last Stand encounter.
* No unreadably small touch targets.

---

## 28. Acceptance criteria

The product is finished when all of the following are true.

### 28.1 Gameplay

* Player can launch the game on mobile.
* Player can choose difficulty.
* Player can choose encounter.
* Player can set a ward.
* Player and bot duel in real time.
* Both sides obey min and max cast times.
* Auto-cast works.
* Bot uses selected difficulty.
* Attacks produce correct aggregate feedback.
* Result states work: Victory, Defeat, Clash, Stalemate.
* Last Stand works where configured.
* Attack limits work.

### 28.2 Visual identity

* Placeholder PIL art has been replaced or deliberately upgraded.
* Game no longer looks like coloured peg Mastermind.
* Attacks visibly fly into barriers.
* Barrier feedback is satisfying and readable.
* Feedback does not leak positional information.
* Essence and locus identities are visually distinct.
* UI is cohesive and mobile-polished.

### 28.3 Mobile UX

* Portrait mobile layout works.
* Touch controls are reliable.
* Text is readable.
* Buttons are finger-sized.
* Timers are clear.
* Player can understand why auto-cast happened.
* Tutorial explains the core game.

### 28.4 Technical

* Godot rules tests pass.
* Python rules tests pass where still maintained.
* UI smoke tests pass.
* Mobile export builds.
* Release build launches.
* No major frame drops during normal play.
* No bot calculation freezes the UI.
* No known information leaks through UI payload or animation.

### 28.5 Release

* Release notes written.
* Manual test log completed.
* Android build produced.
* Local desktop build produced.
* Optional web export verified if included.
* README updated to describe real-time mobile game rather than alternating-turn prototype.

---

## 29. Implementation plan

### Phase 1 — Rules canon and terminology

Goal:

Update documentation, user-facing strings and rules model to the final terminology.

Tasks:

* Rename visible terms to Essence, Locus, Ward, Attack, Fracture, Echo, Fade.
* Add Rules Canon document.
* Update README summary.
* Update help text.
* Ensure no final UI says peg, guess, code, black pin or white pin.
* Keep internal names only where changing them would be risky.

Acceptance:

* Game can still run.
* Tests still pass.
* UI uses final terminology.

### Phase 2 — Ruleset expansion

Goal:

Support final encounter structure.

Tasks:

* Expand loci support from 1–4 to 1–8.
* Add default locus names.
* Ensure scoring works for 1–8 loci.
* Add separate difficulty profiles.
* Keep encounter config separate from difficulty config.
* Add Last Stand fields.
* Add trait fields but keep traits simple.

Acceptance:

* Existing encounters still work.
* 8-locus test ruleset works in automated tests.
* Difficulty can be selected independently of encounter.

### Phase 3 — Real-time sim

Goal:

Replace alternating turns with real-time cast windows.

Tasks:

* Build authoritative real-time duel state.
* Add min/max cast timers.
* Add player cast gating.
* Add bot cast gating.
* Add auto-cast.
* Add simultaneous attack resolution.
* Add attack history records.
* Add pause-safe timer behaviour.
* Add real-time tests.

Acceptance:

* Human and bot cast independently.
* No one can cast before min time.
* Auto-cast happens at max time.
* Result states work.

### Phase 4 — Mobile duel UI

Goal:

Create mobile-first duel interface.

Tasks:

* Redesign main scene for portrait.
* Add attack builder.
* Add cast timer.
* Add enemy timer.
* Add attack count display.
* Add expandable history.
* Add auto-cast warning.
* Add pause/settings access.
* Add tutorial overlays.

Acceptance:

* Duel can be played comfortably on mobile viewport.
* UI smoke covers main path.
* No desktop-only interactions.

### Phase 5 — Attack and barrier animation

Goal:

Make the game feel like a magical duel.

Tasks:

* Add attack launch animation.
* Add essence bolt visuals.
* Add barrier impact animation.
* Add aggregate feedback reveal.
* Add ward break animation.
* Add Last Stand animation.
* Add result transitions.
* Ensure animation consumes sim events but does not control rules.

Acceptance:

* Every attack has satisfying visual feedback.
* Feedback remains aggregate and non-positional.
* Reduce motion setting works.

### Phase 6 — Production visual pass

Goal:

Replace placeholder identity with production visual language.

Tasks:

* Produce final essence icons.
* Produce final locus icons.
* Produce final barrier art.
* Produce final wizard portraits.
* Produce UI skin.
* Produce feedback icons.
* Add audio and haptics.
* Update art manifest.

Acceptance:

* Placeholder art no longer defines the look of the game.
* All core screens have consistent style.
* Game has a recognisable identity.

### Phase 7 — Content and tutorial pass

Goal:

Make the game understandable and replayable.

Tasks:

* Finalise encounter progression.
* Add tutorial text.
* Add help screen.
* Add difficulty descriptions.
* Add enemy trait descriptions.
* Add Last Stand explanation where used.
* Add result screen summaries.

Acceptance:

* New player can understand the game without external docs.
* Full game mode is available.
* Easy/Medium/Hard feel meaningfully different.

### Phase 8 — Mobile export and release QA

Goal:

Produce a finished mobile build.

Tasks:

* Configure Android export.
* Test portrait layout.
* Test on device.
* Optimise performance.
* Fix scaling issues.
* Complete manual QA checklist.
* Update README and release notes.
* Produce release build.

Acceptance:

* Android build launches and is playable.
* Release checklist complete.
* No critical gameplay, UI or information-leak bugs remain.

---

## 30. Cursor instruction summary

When implementing this PRD, Cursor should prioritise in this order:

1. Preserve correct hidden-pattern scoring.
2. Prevent visual/UI information leaks.
3. Implement real-time cast windows in the sim, not only the UI.
4. Keep mobile UX readable and touch-friendly.
5. Keep encounters config-driven.
6. Keep tests green after each phase.
7. Do not add extra RPG, mana, HP, shop, multiplayer or deck-building systems.
8. Replace placeholder visuals only after the real-time rules are stable.

The finished game should be a polished mobile real-time magical deduction duel, not a generic fantasy combat game and not an obvious Mastermind board.

