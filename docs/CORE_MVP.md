# Duel Master Battle — Core MVP

The playable foundation. One duel, end to end, on a phone.

## The game as shipped on this branch

| Rule | Value |
|---|---|
| Ward size | 4 loci |
| Spells | 6: Flame ▲, Frost ❄, Stone ■, Light ☀, Vine ●, Arcane ★ (repeats allowed) |
| Casts per side | 10 |
| Cast window | opens 5 s after the previous cast, auto-casts at 60 s |
| Feedback | aggregate only: Fracture (right spell, right locus) · Echo (right spell, wrong locus) · Fade (not in Ward) |
| Win | break the rival's Ward first, or the rival runs out of casts |
| Lose | rival breaks your Ward first, or you run out of casts |
| Clash / Stalemate | both break / both exhaust in the same instant |

Constants live in `sim/constants.gd` (`CORE_*`) and the ruleset in `sim/encounters.gd` (`core_duel`).

## Flow

1. **Main menu** — pick Apprentice / Adept / Archmage, Start Duel. How-to-play and settings (sound,
   vibration, reduce motion) behind small buttons.
2. **Set your Ward** — tap spells to fill the glowing locus; selection auto-advances; double-tap a
   filled locus to clear it; Random / Clear; Lock button reads "Choose 4 spells" → "Pick N more" → "Lock Ward".
   A feedback legend is shown here so the first cast result makes sense.
3. **Duel** — rival panel (name, status, progress to its next cast, casts left, hidden Ward, last result),
   your-last-cast banner (spells + pips + plain-English result), tabbed history (yours / rival's, tap a
   past cast to copy it into the builder), guess builder, one big **CAST** button that is also the timer:
   cyan ring filling while locked ("weaving 4…"), gold ring draining once open with "Ns left", red
   pulse + ticks under 10 s, sub-label explains why it's blocked ("fill 2 loci"). Tapping a blocked
   button shakes and flashes the empty loci.
4. **Result** — both Wards revealed, reason ("You broke the rival's Ward" / "You ran out of casts"…),
   Play again / Menu. Play again resets everything and reseeds the rival.

## Rival AI (`sim/solver_bot.gd`)

* Maintains the set of all 1296 Wards consistent with its feedback; every guess is consistent
  ("candidate_filter"), or the consistent guess that best splits the remainder ("capped_minimax").
* Planning is incremental: `begin_planning()` at window open, `think(3 ms)` per frame, so the hard
  rival never stalls a frame (worst case ~77 ms of work split over ~20 frames).
* Casts at a random moment inside a difficulty band, clamped to the 5–60 s window, only once its
  plan is ready. Apprentice adds a 40% "forgetful" (legal but inconsistent) cast.
* `tools/run_balance_probe.sh`: all three solve ~100% of Wards within 10 casts; average casts
  easy 5.4 / medium 4.6 / hard 4.5. The think band (apprentice ~37 s, adept ~23 s, archmage ~15 s
  per cast) is the main difficulty lever. New personalities plug into `sim/bot_factory.gd`.

## What changed from the previous project

* **Default encounter** is `core_duel` (4×6×10, 5–60 s). The menu offers difficulty only; the
  Blue Apprentice → Eightfold Warden ladder is still in `encounters.gd` (`all_encounters()`) but not
  offered (`playable_encounters()`).
* **Sim fixes**: exhaustion is now decided per side (you lose when *you* run out, win when *they*
  do — previously only a both-exhausted stalemate existed); a cast requires a complete guess (the old
  sim let you cast blanks); rival timing is difficulty-driven instead of always auto-casting at max
  time; the bot's feedback is registered on its own casts (was registering the player's); events
  carry `reason`; `reset()` fully reseeds.
* **Client rebuilt** around one code-built portrait layout (`game_board.gd`) with three small
  components (`spell_slot`, `feedback_pips`, `cast_button`). Removed: popup picker above locus,
  drag-and-drop, FTUE arrows, ward barrier prop, separate timer widget, history bottom sheet.
  These are parked in `client/legacy/` (see its README) rather than deleted.
* **Spell icons regenerated** (`tools/generate_essence_icons.py`): 10 unique silhouettes on solid
  colour discs so spells are distinguishable without colour. Palette in `colour_data.gd`.
* **Sound**: small procedural SFX autoload (`sfx.gd`) — place, clear, ready chime, cast, rival
  cast, result chords, warning ticks. Haptics kept (`playability_haptics.gd`).
* **Windows entry points**: `Play Duel Master Battle.bat`, `Run Tests.bat`; shell tools now find
  Godot via `tools/find_godot.sh`.

## Tests performed

* `sim/tests/test_core_duel.gd` (19 cases): ruleset numbers; feedback with repeats (extra copies
  don't echo, swaps, full hit, full miss, mixed); window locked until 5.00 s, open after; cast
  refused with incomplete guess (+ reason string); auto-cast at 60 s keeps chosen loci and fills the
  rest legally; victory on exact guess; defeat when rival solves; defeat at 10 casts; victory when
  rival exhausts; stalemate at 10/10 same instant; clash same instant; rival guesses always
  consistent (random + minimax, 6 seeds); rival solves every 7th of the 1296 Wards within 10;
  rival never casts before 5 s or after 60 s on any difficulty and the duel ends with a passive
  player; incremental planning splits across frames; reset clears everything; pause freezes;
  feedback events carry only aggregate counts; load-previous-attack.
* Existing suites still pass (feedback fixtures, sequential game, solver bot, assets).
* `client/tests/run_ui_smoke.gd`: menu; full duel through the ui_* API — selection auto-advance,
  lock refused when incomplete, double-tap clear, cast button CHARGING/READY/BLOCKED/WARNING states,
  early cast ignored, history copy, clear, rival tab, reach victory, Ward reveal, result overlay,
  auto-cast at 60 s, play-again reset, second duel starts.
* `client/tools/realtime_playtest.gd`: real wall-clock, synthesised taps at button positions —
  window opens at ~4.98 s, tap casts, rival casts on its own (~10–12 s on Adept), blocked taps do
  nothing, WARNING state, auto-cast fires when the window expires, pause freezes `duel_time`.
* `client/tools/capture_visual_qa.gd`: 14 screenshots reviewed for clipping/overlap/readability;
  fixes made from that review (dropped decorative title behind the menu button, locus captions
  → 1–4, plain-English results, legend on setup, toast moved off the history list, larger text).

## Known issues / not done

* No Android build was produced in this pass (export preset unchanged); layout is 720×1280
  portrait with `canvas_items` / `expand` stretch. Needs a device pass for safe areas.
* Rival "thinking" is timing only — no personality text or animation beyond the wizard's cast pose.
* History rows for the rival are read-only by design; there is no per-spell elimination aid.
* Sound is procedural placeholder audio; no music.
* The legacy Python prototype still models the old 12-cast archmage rules.

## Future hooks preserved

* `DmbDuelRuleset` still carries slot count 1–8, pools, repeats flag, cast times, Last Stand,
  traits, tutorial flags — the client reads `slot_count`/pools so larger Wards need only layout work.
* `DmbEncounters.all_encounters()` / `all_encounters_including_boss()`: the encounter ladder.
* `DmbBotFactory.make_bot()` + `DmbDifficultyProfile` (`bot_logic`, mistake rate, think band).
* `DmbRealtimeDuelSim` Last Stand path (enabled by ruleset fields; exercised by Eightfold Warden).
* `client/legacy/` components (ward barrier states, FTUE overlay, drag tray, animation controller).
* `sim/game_state.gd` sequential (turn-based) variant.
