# Plan: village minigames (eighteen games in the buildings and people of the early village)

Branch `feature/village-minigames`, cut from `feature/player-stress-and-progression` at `336d3dec` (20 Oct 2026), which holds everything on `main`
plus the 18 to 20 Oct stress, ladder and rats work. Written before any gameplay change, for the owner's approval. Merging is the owner's call. The content
roster stays frozen (D33): everything below is narrative residents, dialogue data, a games engine beside the narrative layer, and client interaction;
nothing is imported from Widelands, OpenRA or Mindustry. No game gives or takes anything in the world (owner's brief: no reward for winning or losing).

## 0. The brief, restated

Talking to a person, or inspecting a building, can offer a game. The eighteen games: Hanabi, Can't Stop, Yahtzee, Skull, Rock Paper Scissors, Take
the Last Carrot (Nim), Guess Who, Rummikub, Texas Hold'em, five-card draw ("5 stud draw" in the brief; section 8 asks which), Oh Hell, Knock-out Whist,
Blackjack, Roulette, the sliding-blocks puzzle with coloured gates, Pairs, the "new object" memory game, and the same-or-different reaction game. Each
game's conceit is tied to the place it is played and the work done there. A developer entry starts a village where every host is present and
reachable on foot, using the buildings a village has early rather than late.

## 1. Where the game stands (20 Oct 2026)

* The start village on seed 507 (`tests/_nh.world()`): a warehouse, a lumberjack's hut, a forester's hut, a sawmill, a quarry, a hunter's hut and a
  well (`world.py` `PRIMITIVE_SHOWCASE` plus the producer, sawmill and ranger every start has). Worker rows exist for the lumberjack, forester,
  stonemason and hunter; the sawmill and the well run without a person to talk to. Carriers walk the roads. The faction AI's next buildings, in order
  (`ai.py` line 287): fisher's hut, farm, well, tavern, bakery, then mines and the barracks.
* People the narrative layer adds: the mentor at the start (`tutorial.py`), the mother when a seat needs her (`mother.py` `ensure`), the warehouse
  keeper with the rats (`pests.py` `ensure_keeper`), the Rollkeeper and the contestants at the Trial gate (`trial/run.py`), Mira the AI apprentice
  (`net/ai_wizard.py`, no conversation of her own).
* A conversation is `narrative/conversation.py`: `talk` opens it, `choose` answers, the person is held (`hold.py`) until `end_talk`, walking away or
  idling closes it. Topics come from `data/narrative/dialogue/occupations.json` by role and tribe, with `when` facts; a dialogue graph's choice can
  run an effect (`graph.py` `EFFECTS`), and `begin_duel` is the precedent for "a choice opens a board": the reply carries a `duel_lease` extra, the
  client's `story_ui.gd` shows "Begin the duel" and `hybrid_world.open_story_duel` opens the board on the `DuelHost` canvas layer. The Trial
  (`trial_enter`, `trial_move`, `trial_interact`, `trial_choose`, `trial_leave`, `trial_view`) is the precedent for a server-run mode driven op by op
  with a `view` per reply.
* Ops are registered in three places: `story.WIZARD_OPS` and `narrative/ops.py` `OPS` (dispatch), `net/protocol.py` `PLAYER_OPS` and
  `PASSTHROUGH_OPS` (what a connected wizard may send), `session.py` `IDLE_OPS`/`DEAD_ALLOWED` (activity and death rules).
* The client: `wizard_labels.gd` is the inspect panel (a person: Talk; a building: who is inside, "Ask X to come out"); `story_ui.gd` the dialogue
  card (`ui/narrative_card.gd` `show_card(title, subtitle, body, choices, footer)`); the player menu is Wizard World only, the developer menu
  (`dev_menu.tscn`, `DMB_DEV_MENU=1`) holds the old entries; single player starts a Python host through `net/lan_session.gd` (`--seed`, `--map`,
  `--profile`, `--fresh`, `--runs-dir`). Headed tests teleport with `HYBRID_DEV_OPS=1`. Art loads through `asset_loader.gd`; there is no card, die
  or tile art in the repository (checked: nothing for any of the eighteen games exists in code, data or docs).
* Versions: `GAME_VERSION` 0.4.0, `PROTOCOL_VERSION` 3, Android code 4. Godot 4.5.1 and the venv's Python 3.11 are in `.dmb_windows_local.json`.

## 2. Design

### 2.1 Where the rules run: the Python host, one engine per game, the client a table

The rules of every game run in Python on the host (`WizardRTSHybrid/wizard_rts/minigames/`), the way the Trial and the dungeon puzzles do, and the
Godot client is one generic table that draws whatever `view` the host sends and offers whatever `actions` it lists. Reasons: the eighteen rule sets
get exhaustive, deterministic pytest coverage (the repository's strength: seeded self-play, invariants, exact rule cases); the bots that play the
villagers' seats are one piece of code each, beside their rules; one table scene with a handful of widgets replaces eighteen client implementations
and keeps the Android export's asset audit untouched; and if the owner later wants stakes, the host already holds the truth (nothing to verify from
a client report). Cost: one request per action, the same round trip as every `choose` today (local in single player and on a phone's in-process
Python). Two games need the client's clock: the reaction game and the memory game measure the time to answer on the client and send it with the
answer; the host records it and scores from it (no reward, so nothing to defend).

Engine contract (`minigames/base.py`), every engine a module of pure functions over JSON-serialisable dicts:

```
new(seed: int, opts: dict) -> state            # deterministic from the seed; seats listed in state["seats"] (seat 0 is the apprentice)
actions(state, seat) -> list[{"id", "text", ...}]   # the legal moves of this seat now (empty when it is not their turn)
act(state, seat, action: dict) -> state         # applies one move; raises Illegal for anything not in actions()
bot(state, seat, rng) -> action                 # the villager's move for a non-human seat
view(state, seat) -> dict                       # what this seat may see: hidden hands masked, plus "log" (the last events) and "over"/"result"
```

`minigames/table.py` runs a game at a conversation: it creates the state, plays the bots' moves until it is the human's turn or the game is over,
answers `minigame_act`, and ends on `minigame_leave`, on the conversation ending (walking away, idling, the person being removed) or at the result.
The game lives in `world.narrative["minigames"][seat]` (one table per apprentice seat; saved with the world like any narrative dict, abandoned on
load because the person is no longer held). The world clock is never touched: a game is a conversation that lasts, and the person stays held
(`conversation.tick` keeps `last_ms` fresh while a game is on the table).

### 2.2 How a game is offered: the catalogue

`data/narrative/minigames.json`, one entry per game: `id`, `title` (the villagers' name for it), `host` (a worker role, a resident role, a carrier,
or a building kind for buildings without a person), `offer` (the topic text in the conversation, e.g. "Show me the knucklebones."), `intro` (what
the host says as the table is laid), `lines` for `win`, `lose`, `draw`, `quit` and `again`, and `skin` (the names the table uses: what the cards,
dice, tiles, gates and faces are called and coloured at this place). `occupations.py` and the resident graphs read the catalogue: a host's
conversation shows the game as a topic (`game:<id>`), always available, no `when` facts; choosing it runs the `begin_minigame` effect
(`graph.EFFECTS`, repeatable), which puts a `minigame` extra on the reply, and the client opens the table on "Lay out the game" the way "Begin the
duel" opens the board. A building with no person (the sawmill, the well) gets a narrative resident standing at its door (the sawyer, the
water-carrier: `residents.create`, the same way the keeper stands at the warehouse), so every game is a conversation with somebody; the inspect
panel of a building names the game played there ("The sawyer's twenty-one is played here") so the owner can find them by walking up to buildings.

### 2.3 The eighteen games and their places (early buildings and people first)

| Game | Host | The conceit |
| --- | --- | --- |
| Rock Paper Scissors | the mentor | "Three colours, no knots": Flame beats Vine, Vine beats Frost, Frost beats Flame. The first thing the mentor ever teaches, best of five. |
| Hanabi | the mentor, with Mira's seat played by the host's bot | "The Ward you cannot see": you hold your cards facing out, like a hidden Ward. Five suits are the five colours of the ladder (Flame, Frost, Vine, Light, Stone), fuses are "fractures". |
| Can't Stop | the lumberjack | "Felling the big one": each roll is axe strokes on three trunks; bank your cuts or press on and the trunk may split (a bust). Columns are trees of different girth. |
| Memory game (the new object) | the forester (ranger) | "Which sapling is new?": the forester shows today's plantings, three, then four, and you point at the one that was not there before, until you point at an old one. |
| Yahtzee | the stonemason at the quarry | "Knucklebones": five chipped stones with carved faces; the categories are the mason's orders (a full course, a run of ashlar, five of a face). |
| Sliding blocks with coloured gates | the stonemason at the quarry; a second skin at the farm when one exists | "Clearing the face": oddly shaped granite blocks slid out of the pit through the gate of their chalk colour (the carts they are promised to). At the farm the same engine is fussy, oddly shaped sheep leaving a field through the gate of their pen. |
| Reaction game (same or different) | the hunter | "Tracks": the hunter flashes a sign (a print, a scat, a broken twig); say whether it is the same beast as the last one, as fast as you can. |
| Five-card draw | the hunter | "Skins": the hunters' bluffing game played for pelts, pebbles standing in for pelts. |
| Guess Who | the sawyer (a new resident at the sawmill) | A forgetful, half-deaf sawyer trying to remember who ordered the planks. The faces are the village's real people (their figure sprites and traits: trade, tribe, headwear, beard, what they carry); you ask yes-or-no questions, they ask you about yours. |
| Blackjack | the sawyer | "Twenty-one feet": cut planks to exactly twenty-one without overshooting; the sawyer deals plank lengths, stands on seventeen. |
| Roulette | the water-carrier (a new resident at the well) | "The windlass": spin the well's wheel and bet pebbles on where the bucket handle stops; red and black are the two rope colours, the numbers the notches on the drum. |
| Rummikub | the warehouse keeper | "The tally board": the keeper's stock tallies sorted into runs and sets of coloured tallies (logs, granite, meat, water); the thirty-point first meld is "opening the ledger". |
| Skull | a carrier at the warehouse | "Under the cloth": each carrier covers what is on their cart, a flower or a rat skull (the rats again); bid how many carts you dare uncover. |
| Texas Hold'em | a carrier at the warehouse | "The carriers' pot": pebbles for the next light load; the flop, turn and river are the three roads out of the yard. |
| Oh Hell | the Rollkeeper, with the contestants' seats as bots | At the Trial gate's waiting fire: bid how many bouts you will win; the Rollkeeper deals and keeps the roll. |
| Knock-out Whist | the contestants | The losers of each round are knocked out, as the Trial knocks out its contestants; trumps are drawn from the gate's lots. |
| Take the Last Carrot (Nim) | the mother | The stew carrots on the table, a children's game she still plays with the apprentice she still sees as a child: take one, two or three from a row; whoever takes the last carrot peels them all. |
| Pairs | the mother | "The same bolt": matching the swatches in her basket, two at a time, cut from the same cloth. |

Every host of the start village is covered (lumberjack, forester, stonemason, hunter, keeper, carriers, mentor, mother) plus the gate's people, who
the debug village brings to the green (section 2.5). Soldiers, the tavern, the bakery and the mines host nothing in this plan.

### 2.4 The client: one table, five widgets

`godot_project/client/minigames/minigame_table.gd` on its own full-rect canvas layer (the `DuelHost` pattern): a title band (the villagers' name for
the game, the host's name), a log line (the host's last words and the last event), the areas the view names, and the action buttons the view lists
(`ui/narrative_card.gd` styling, `visual_theme.gd` buttons, `sfx.gd` tap/place/victory/defeat). Widgets, all drawn procedurally (no new PNGs, so
the Android asset audit and the export probe are untouched): `card_widget.gd` (rank and suit, or colour and number, face up or down, with the skin's
colours and names), `die_widget.gd` (pips, held state), `tile_widget.gd` (Rummikub tallies, Skull discs, Nim carrots, Pairs swatches),
`grid_widget.gd` (the sliding board: tap a block, then tap a direction or drag; coloured gates on the rim; the same widget lays out the memory
objects and the reaction sign), `face_widget.gd` (Guess Who: the residents' figure sprites through `asset_loader.gd`, the ones `residents.py`
already uses, with the trait labels). Portrait phone first (720x1280), the responsive rules of `responsive_modal.gd`; Esc or Leave closes the table
(`minigame_leave`) and returns to the conversation, where the host says the `quit`, `win`, `lose` or `draw` line and offers "again".

### 2.5 The developer games village

`--games-village` on the host (and `HYBRID_GAMES_VILLAGE=1`), reachable from the developer menu as "GAMES VILLAGE (developer)" when `DMB_DEV_MENU=1`:
a private single-player session on profile `games` (its own runs folder, so the owner's campaign save is never touched), always `--fresh`, seed 507.
After the world is built the flag: places the early buildings the start lacks (fisher's hut, farm, tavern, bakery) through `construction.place_building`
already operational with their workers, on free tiles near the warehouse; creates every narrative host now (the mother, the keeper, the sawyer, the
water-carrier) and a Rollkeeper and two contestants at the village green (narrative residents of the games village only, not the Trial's); marks the
opening as seen and the first lessons done so the mentor talks games, not knots; sets the stranger's arrival off (`HYBRID_EXPLORE_FALLBACK_MS` to a
day) so nothing interrupts; and stands the apprentice at the warehouse. Mira comes as usual. A HUD line in this village lists the games not yet
found, and every building's inspect panel says what is played there. Nothing in the games village is a new roster entity: the four extra buildings
are existing kinds, and the people are narrative residents like the keeper.

### 2.6 What does not change

No wares, stock, clock, HP, relationship, ledger key, worldview or Aspect moves because of a game. A finished game writes one `events.log` entry
(`minigame_played`: game, host, result, turns) and a line in the journal's new "Games" page (which games the apprentice has found and played, no
score kept across sessions beyond that list). The magic ladder's rung card waits while a game is on the table and comes when the table closes
(the owner's rule says a due rung interrupts anything but a duel on the board; a table is treated like a board, section 8 asks).

## 3. Milestones

Each milestone ends with its tests green, a ledger entry and one commit; nothing is reported done without the test named beside it.

**M0 Scaffold and the first game end to end.** The engine contract, `table.py`, the catalogue with one entry, the `begin_minigame` effect, the
three ops (`minigame_begin` is the effect's work; `minigame_act`, `minigame_leave`, `minigame_view`) registered in `story.WIZARD_OPS`, `ops.OPS`,
`protocol.PLAYER_OPS`/`PASSTHROUGH_OPS`; the client table with the action buttons and the log; the games village flag, profile and menu entry;
Rock Paper Scissors with the mentor playable from the menu to the result and back to the conversation. Tests: `test_minigames_rules.py` (RPS),
`test_minigames_village.py` (the flag builds the village: every planned host present and reachable, the apprentice's stand tile, the stranger
off; `MultiplayerSession.dispatch` accepts the ops, refuses them dead or in a duel; a game never changes any stock, the clock or the ledger);
`run_menu_routes.gd` extended with the developer entry; a headed `run_hybrid_minigames.gd` that hosts the village, teleports to the mentor, plays
RPS and screenshots (`docs/evidence/minigames/`).

**M1 The quick games (seven).** Take the Last Carrot, Pairs, the memory game, the reaction game, Roulette, Blackjack, Yahtzee; the die, tile and
grid widgets; the sawyer and the water-carrier residents. Rule tests: Nim's winning strategy for the bot (it never loses from a winning position),
Pairs' matching, the memory sequence (always exactly one new object, a repeat ends it), reaction scoring from client times, Roulette's table of bets
and payouts (European wheel, single zero), Blackjack (dealer stands on soft 17, blackjack pays three to two in pebbles that mean nothing, split and
double offered), Yahtzee's thirteen categories and the upper bonus.

**M2 Push-your-luck and tiles (three).** Can't Stop, Rummikub, the sliding blocks (with the farm's sheep skin where a farm exists). Rule tests:
Can't Stop's three runners and the bust, Rummikub's sets and runs, the thirty-point opening, rearranging the table (the bot only lays from hand,
stated), the generator's boards solved by breadth-first search so every puzzle is solvable and the solution length is recorded.

**M3 Trick-taking and betting (four).** Knock-out Whist, Oh Hell, five-card draw, Texas Hold'em; the card widget; the hand-ranking module shared by
the two poker games. Rule tests: the ranking table against known hands (every category, kickers, ties), the betting round state machine (check,
bet, call, raise, fold, all-in, side pots not needed: pebbles are equal), Whist's knock-out and the dog's life rule, Oh Hell's hook (the dealer may
not make the bids add to the tricks) and the rising and falling hand sizes.

**M4 Hidden information and deduction (three).** Skull, Hanabi, Guess Who. Rule tests: Skull's bidding and challenge, losing a disc, the two-flower
win; Hanabi's clues, the fuse, the deck's last round, the score; Guess Who's trait questions over the village's real people (the traits derive from
the simulation and a seeded cosmetic pass, the bot asks the most halving question).

**M5 The village complete, evidence, documents.** Every host in the games village; the inspect panel's game line; the HUD list; the journal's Games
page; the headed run extended to walk three hosts of different widgets (cards, dice, grid) with screenshots; `docs/MINIGAMES_GUIDE.md` (how to start
the games village, each game's rules in the villagers' words, which host plays it, the keys); `docs/ledger/MINIGAMES_PROGRESS.md` closed;
`docs/NEXT_AGENT_HANDOFF.md` entry; `PROTOCOL_VERSION` 4 and `GAME_VERSION` 0.5.0 (Android code 5) if the owner agrees (section 8); no APK unless asked.

## 4. Files

New: `WizardRTSHybrid/wizard_rts/minigames/` (`__init__.py`, `base.py`, `table.py`, `catalogue.py`, `cards.py` for decks and poker ranking,
`rps.py`, `nim.py`, `pairs.py`, `memory.py`, `reaction.py`, `roulette.py`, `blackjack.py`, `yahtzee.py`, `cantstop.py`, `rummikub.py`, `slide.py`,
`whist.py`, `ohhell.py`, `draw_poker.py`, `holdem.py`, `skull.py`, `hanabi.py`, `guesswho.py`), `wizard_rts/data/narrative/minigames.json`,
`wizard_rts/narrative/games_village.py` (the developer village), `tests/test_minigames_rules.py`, `tests/test_minigames_village.py`,
`godot_project/client/minigames/` (`minigame_table.gd`, the five widgets), `client/tests/run_hybrid_minigames.gd`, `docs/MINIGAMES_GUIDE.md`,
`docs/ledger/MINIGAMES_PROGRESS.md`, `WizardRTSHybrid/docs/evidence/minigames/`.

Changed: `narrative/graph.py` (the effect), `narrative/occupations.py` and `conversation.py` (the game topic, the table held open),
`narrative/ops.py`, `story.py`, `net/protocol.py`, `net/session.py`, `net/host.py` (the flag), `narrative/residents.py` (two figures),
`client/hybrid/story_ui.gd`, `client/hybrid/wizard_labels.gd`, `client/scenes/hybrid_world.gd`, `client/net/lan_session.gd`,
`client/scripts/dev_menu.gd`, `client/tests/run_menu_routes.gd`, `docs/NEXT_AGENT_HANDOFF.md`, `CLAUDE.md` (one line).

## 5. Tests and commands

```
py -3 -m pytest WizardRTSHybrid/tests/test_minigames_rules.py WizardRTSHybrid/tests/test_minigames_village.py -q
py -3 -m pytest WizardRTSHybrid/tests/test_narrative_conversation.py WizardRTSHybrid/tests/test_village.py WizardRTSHybrid/tests/test_lan_multiplayer.py WizardRTSHybrid/tests/test_determinism.py -q
WizardRTSHybrid/scripts/run_lan_headed.sh minigames      (new entry; GODOT at the console exe)
"%GODOT%" --path godot_project --script res://client/tests/run_menu_routes.gd
```

The full suite (`py -3 -m pytest WizardRTSHybrid/tests -q`) before the last commit of M5. The determinism test runs every engine's self-play under two
`PYTHONHASHSEED`s (no decision by iterating a set of strings, no wall-clock time in a rule).

## 6. Rules kept

Content frozen (no importer, no new roster entity; residents and dialogue only). Never `git add -A`. `docs/release_notes.md` is never committed.
`external/`, `runtime/`, `dist/` are never committed. The owner's untracked files are never deleted. A defect the owner sees is fixed only when a
headed test shows it fixed. Merging into `main` is the owner's call.

## 7. Risks

* **Eighteen rule sets is a lot of surface.** Each engine is small and pure, tested by self-play; the client is one table. The order of milestones
  puts the widget-defining games first so the table is stable before the card games.
* **Guess Who needs enough distinct people.** The start village has about ten named bodies; the games village's extra buildings and residents raise
  it, and the engine draws the board from the twenty-four nearest people, repeating none, with cosmetic traits seeded per person.
* **The reaction game over a LAN** is scored from the client's own clock; the host trusts it. Stated, harmless without a reward.
* **A game in a saved world.** A table is abandoned on load (the person is not held), the catalogue line for `quit` is said next time. Simple and
  stated rather than resumed.

## 8. Questions for the owner (defaults in brackets)

1. "5 stud draw": five-card draw [default] or five-card stud (a dealt-up variant, same ranking module, a different betting rhythm)?
2. A due rung while a game is on the table: wait for the table to close [default], or interrupt and abandon the game as the rule for conversations does?
3. Version: bump to 0.5.0, protocol 4, Android code 5 in M5 [default], and no APK until asked?
4. The base: this branch is cut from `feature/player-stress-and-progression` (the newest line, not yet on `main`) [as asked, "the most up to date version"].
5. Two humans at one table (a LAN game of Hold'em between the two apprentices): not in this plan [default]; the engine contract has seats for it later.
