# Polish: a world that is satisfying to watch (0.5.1, branch `feature/polish-watching-feel`)

The owner's brief (22 Oct 2026): make the game satisfying to **watch**, not only to play. The player should be able to sit back and feel that the
world is working: cause and effect visible, a productive rhythm, tiny celebrations for completed processes, state changes animated, anticipation
before reward, and a sound mix that could run for ten minutes without being muted. The same brief asked for the minigame tables and the menus to
be polished, reusing the parent games' assets where they help.

Everything here is **presentation only**. Nothing in `client/hybrid/ambience.gd` or the table's effects feeds anything back to the Python
simulation; the sim's snapshots are read, never written. The content roster stays frozen: no new buildings, units, wares or items.

## What was done

### The world: `client/hybrid/ambience.gd` (owned by `hybrid_world.gd`)

A watching layer that diffs each snapshot against the last and turns the economy's small completions into small moments. Everything is drawn;
the only loaded images are the Widelands ware icons the art catalogue already carries (asset reuse).

| Event (from the snapshot) | Visual feedback | Audio feedback | Level |
|---|---|---|---|
| A carrier or worker sets a ware down (`cargo`/`carrying` goes empty) | five dust squares at the feet; the ware's own Widelands icon drifts up and fades into the building | by the material: wood `clack`, stone and metal `tock`, food and drink `pat` | Low |
| A carrier picks a ware up | a small pale ring at the hands | none | Low |
| A building is working (`working`) | chimney smoke: a puff every 1.35 s (faster at a higher time scale), rising, drifting, growing, fading over 2 to 3 s | none | Low |
| A building under construction | a thin gold arc over the site fills with `hp / max_hp` (anticipation before the reward) | none | Low |
| Construction finishes (`constructing` goes away) | a gold ring spreads from the building and fourteen sparks fly up; the HUD names it ("Lumberjack's hut is finished.") | `complete`, a soft rising chime | Medium |
| A tree is felled (its `stage` becomes `felled`) | nine wood chips fly from the trunk | `chop` | Low |
| A sapling is planted (a new `sapling` row) | four green motes rise | none | Low |
| A new unit appears | a white ring where it stepped out | none | Low |
| A building is waiting (its status says waiting, no road, needs, lacks) for six seconds or more | a faint hollow crate pulses over it (restrained: alpha 0.28 to 0.5) | none | Medium |
| The forest stands | every standing tree sways on its own phase (`hybrid_art.gd` shears it about its base; felled trees and stumps do not move) | none | Low |
| The world's totals rise (`economy_totals`) | one quiet HUD line every three seconds, "+3 log · +1 granite", brightening then fading (`campaign_hud.gd stock_tick`) | none | Low |
| The day passes (`game_ms`) | a `CanvasModulate` over the world only: morning at the start, a blue dusk eight minutes later, never dark enough to hide anything; the UI layers and the Trial's zones keep their colours | none | Low |

Rationing (section 9 of the brief): a sound only for an event inside the camera's view, at most one every 0.28 s and three a second; at most
360 particles alive; smoke only for buildings in view. `HYBRID_NO_AMBIENCE=1` turns the layer off (for profiling).

Not done (left for a later pass): sway on farms, road-wear and traffic density, ambient camera drift, an ambient bed (wind, birds). None of these needed a simulation change either; they were out of the three-and-a-half-hour budget.

### The minigame table: `client/minigames/minigame_table.gd`, `table_fx.gd`, the widgets

| Moment | Polish |
|---|---|
| The table is laid | the panel pops in (fade from 0, settles from 96 % about its centre); the host's own standing picture sits beside "with X" (an `AtlasTexture` of the sprite the world draws for them) |
| A card, die, tile, face or grid is tapped | a gold ring spreads from the widget (`table_fx.gd`), before the host's reply redraws the table |
| A move lands | the host's message brightens for 0.4 s so the eye goes to what changed; the pieces of the new view arrive with a 25 ms stagger (a deal, not a blink) |
| A die is thrown | the die tumbles (random pips every 50 ms for 0.38 s) before settling on the host's value; held dice do not tumble |
| A refused move | the panel shivers sideways and the message turns red (reset on the next view) |
| The result | a banner on a dark gold-edged band over the table ("You win!", "Not this time", "A draw") scales in and fades after 1.5 s; a win showers 42 gold sparks from the top of the screen, a loss settles with one faint ring; the table stays to look at |

### Menus and cards: `client/scripts/visual_theme.gd`, `client/ui/narrative_card.gd`, `client/scripts/main_menu.gd`

| Moment | Polish |
|---|---|
| Any themed button is pressed | `press_feel`: dips to 96 % while held, springs back with a small overshoot (every button styled by the theme, so the main menu, the cards, the table, the HUD) |
| A conversation card opens | `pop_in` on the panel; the next page of a card that is already up only fades its body (no second arrival) |
| A main-menu overlay opens | `pop_in` on its panel and a short `swish` |
| The main menu stands | `client/ui/menu_backdrop.gd`: 42 motes of gold and violet rise behind the title on their own drifts, and a soft glow breathes behind the buttons |

## Where the code is

- `godot_project/client/hybrid/ambience.gd` (new), wired in `client/scenes/hybrid_world.gd` (`ambience.setup/observe/step/draw`; `view_bounds` set in `_draw`;
  `_note_stock`/`_stock_tick` for the HUD's gains line, `_daylight_tick` for the day's light); `client/hybrid/hybrid_art.gd` `_sway`; `client/ui/campaign_hud.gd` `stock_tick`.
- `godot_project/client/minigames/table_fx.gd` (new); `minigame_table.gd` (`_fx`, `_flash_message`, `_celebrate`, `_animate_widgets`, `widget_act(action, from)`), `die_widget.gd` (`start_roll`), the other widgets pass themselves to `widget_act`.
- `godot_project/client/scripts/visual_theme.gd` (`press_feel`, `pop_in`, `fade_in`, `shake`), `client/ui/narrative_card.gd`, `client/scripts/main_menu.gd` (`_show_overlay`).
- `godot_project/client/scripts/sfx.gd`: `clack`, `tock`, `pat`, `chop`, `complete`, `swish` (procedural, no audio files; the "sound" setting still rules).
- `godot_project/client/ui/menu_backdrop.gd` (new), added by `main_menu.gd` behind the title.

## Evidence

- Headed `client/tests/run_hybrid_minigames.gd` gained two checks: the village shows signs of life after 240 frames (smoke, dust or a ware set down,
  `MINIGAMES_AMBIENCE` prints the layer's counters) and a finished game has its result banner up. Screenshots: `WizardRTSHybrid/docs/evidence/polish/`.
- Progress and the session log: `docs/ledger/POLISH_PROGRESS.md`.

## Testing on the phone

The player-facing guide is `docs/MINIGAMES_GUIDE.md`; the install steps are at the end of `docs/ledger/POLISH_PROGRESS.md`.
