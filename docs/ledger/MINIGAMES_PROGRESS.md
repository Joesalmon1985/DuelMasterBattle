# Village minigames: progress ledger

Plan: `docs/PLAN_VILLAGE_MINIGAMES.md` (approved by the owner 20 October 2026 with the defaults: five-card draw, a due rung waits for the table, version
0.5.0 / protocol 4 / Android code 5 at the end, no APK until asked, solo tables only). Branch `feature/village-minigames` from
`feature/player-stress-and-progression` at `336d3dec`. Merging is the owner's call.

Legend: `[ ]` not started, `[~]` in progress, `[x]` done.

## M0 Scaffold and the first game end to end
- [x] Engine contract `wizard_rts/minigames/base.py` (new, actions, act, bot, view; seeded `rng` by seed and move count; `Illegal`; `find` matches an action
  by id and by every extra key the request carries).
- [x] `minigames/table.py`: one table per apprentice seat in `world.narrative["minigames"]`, the bots' seats played between the human's moves (cap 400),
  `begin`/`act`/`leave`/`view`, the table dropped with its conversation (`on_conversation_end`) and on a load (`drop_all`), the journal's Games page
  (`journal`), one `minigame_played` log entry per finished game, `minigame_abandoned` for a table left early.
- [x] `minigames/catalogue.py` + `data/narrative/minigames.json`: all eighteen entries (host, building, offer, intro, win/lose/draw/quit/again lines, opts,
  skin; the sliding blocks carry the farm's sheep variant). Only a game with an engine in `ENGINES` is offered (`playable`).
- [x] `narrative/conversation.py`: `game:<id>` choices slotted before the goodbye for every host (residents and workers), `begin_game` (the intro, `ends`,
  the `minigame` extra), `after_game` (the closing line for win/lose/draw/quit and the choices again, "again" wording once played), a table keeps its
  conversation from going idle, `inspect_building` lists the games played there (`games`).
- [x] Ops `minigame_act`, `minigame_leave`, `minigame_view` in `narrative/ops.py`, `story.WIZARD_OPS` (and the dispatcher leaves their `view` alone),
  `protocol.PLAYER_OPS`/`PASSTHROUGH_OPS`, `session._passthrough` (refused on a PvP board). `progression.deliverable`: a rung waits while a table is open.
- [x] `narrative/games_village.py` + host `--games-village` / `HYBRID_GAMES_VILLAGE=1` (and the Android args): the farm, tavern, bakery and fisher's hut
  placed operational and joined by road; the mother, the keeper (with the rats), a sawyer at the sawmill, a water-carrier at the well, a Rollkeeper and
  two contestants on the green (graph `dialogue/games.json`); opening seen, essential lessons done; `campaign.explore_due` never due; the apprentice
  stood beside the warehouse. Idempotent.
- [x] Client: `client/minigames/minigame_table.gd` (own canvas layer 15, the dim, the areas, the action grid, Esc/1-9, `widget_act`) and the five
  widgets (`card_widget`, `die_widget`, `tile_widget`, `grid_widget`, `face_widget`, all drawn, no PNG); `story_ui.gd` "Lay out the game" keeps the
  conversation open under the table and shows the closing line after; `hybrid_world.gd` `open_minigame`/`minigame_open`; `lan_session.gd`
  `games_village` (its own `games_village` saves folder, `--games-village`); `lan_menu.gd` seed 507 and the "village of games" page; `dev_menu.gd`
  "GAMES VILLAGE (developer)"; `wizard_labels.gd` "Played here: ...".
- [x] Rock Paper Scissors with the mentor (`minigames/rps.py`, "Three colours, no knots", the ring in the mentor's words, best of five, the villager leans on
  the sign that beats your last throw 40% of the time).
- [x] Tests: `tests/test_minigames_rules.py` (every engine: self-play to the end, deterministic by seed, JSON-clean, illegal moves refused, the catalogue
  complete; the RPS ring) and `tests/test_minigames_village.py` (the village's hosts and buildings, idempotence, the building panel, the whole RPS
  conversation through `story.dispatch` with a world fingerprint that must not change, quit, the table going with the conversation, not idle, dropped
  on load, the ops registered, a `MultiplayerSession` game with the rung waiting for the table, refusals without a table and when dead): 14 pass.
  `test_wizard_tutorial` updated (the mentor's choice list now carries `game:rps` before the goodbye). Godot: `run_menu_routes.gd` (the developer entry
  and its flags; `MENU_ROUTES_OK`) and the headed `run_hybrid_minigames.gd` (starts the games village through the real launcher, teleports to the host,
  talks, "Lay out the game", plays on the table's buttons, leaves, sees the closing line; `HYBRID_MINIGAMES_OK`; shots in
  `WizardRTSHybrid/docs/evidence/minigames/`). Regression run of the narrative suites: 132 pass; `test_narrative_conversation::test_a_conversation_has_a_beginning_responses_and_a_declared_end`
  fails on the base branch too (four lumberjack topics since the tribe topics; not this work).

## M1 The quick games (seven)
- [x] `minigames/cards.py` (the deck, card items, the five-card poker ranking and best-of-seven for M3), `nim.py` (misere with a take cap; the mother
  plays the full search of the small game), `pairs.py` (the twin is kept and the turn goes on; a miss turns back on the next move; the mother remembers
  every swatch turned), `memory.py` (one new sapling each round, a repeat ends it; win at the cap, draw at three or more named), `reaction.py` (same or
  different, scored two quick / one slow / nothing wrong from the client's `ms`; the view's `timed` flag makes the table send it), `roulette.py`
  (European wheel, the outside bets as buttons and the 37 notches as tiles, 35 to 1), `blackjack.py` (stands on 17 soft or hard, 3 to 2 on a natural,
  double, one split, a fixed number of hands), `yahtzee.py` (thirteen orders, the upper bonus, hold by tapping a stone, the mason holds the commonest
  face and fills the best-paying order). All eight registered in `catalogue.ENGINES`.
- [x] Tests: `test_minigames_rules.py` 25 pass (self-play, determinism and refusals for every engine; the misere strategy, pairs' turn rules, the memory
  rounds, reaction scoring, roulette bets and payouts, blackjack totals and the dealer's rule, yahtzee's categories and bonus); `test_minigames_village.py`
  10 pass (every engine has a host). Headed `run_hybrid_minigames.gd` with `HYBRID_GAMES=rps,nim,pairs,memory,reaction,roulette,blackjack,yahtzee`:
  all eight played on the real table to a result, `HYBRID_MINIGAMES_OK`, shots in `docs/evidence/minigames/`.
- [x] Table fixes seen in the shots: whole numbers from JSON shown as integers; a long slate laid in two columns without wrapping.

## M2 Push-your-luck and tiles (three)
- [x] `cantstop.py` (four dice, the three pairings, a pairing that fits both of its trunks must take both, three runners a turn, the bust clears the
  runners, banking claims a topped trunk; the lumberjack banks after two good throws or a topped runner), `rummikub.py` (no jokers; runs and sets;
  thirty from the rack to open and a short opening comes back; add a tally to a meld; a turn that lays nothing draws; an empty rack wins, a dry pool with
  two passes ends on the lighter rack; the human selects tallies on the rack and lays or adds, the keeper lays every meld she finds and adds what fits),
  `slide.py` (a 6x6 board, dominoes, trominoes, elbows, singles and a square, three gates of two cells; built backwards so every board is solvable
  and the construction's reverse is kept as the solution and the par; an exit needs the gate of the block's colour; a move cap of four times par plus
  twenty ends a stuck attempt; the farm's skin says sheep, pen and field). All three in `catalogue.ENGINES`.
- [x] The grid widget is the board's input (tap a block, then a free cell in line with it or the rim; the arrow keys too); the board's moves are
  hidden actions, which the headed driver uses when no button is visible.
- [x] Tests: 44 pass (`test_minigames_rules.py` 34: Can't Stop's pairings, the runner limit, the bust and the bank; Rummikub's melds, the thirty, a
  short opening coming back, two full games with a keeper-like human; every sliding board's solution replayed in exactly par moves, wrong-gate exits
  never legal; `test_minigames_village.py` 10). Headed `HYBRID_GAMES=cantstop,rummikub,slide`: `HYBRID_MINIGAMES_OK`, shots in the evidence folder.

## M3 Trick-taking and betting (four)
- [ ] Knock-out Whist, Oh Hell, five-card draw, Texas Hold'em; the shared deck and hand-ranking module.

## M4 Hidden information and deduction (three)
- [ ] Skull, Hanabi, Guess Who.

## M5 The village complete, evidence, documents
- [ ] Every host; the Games page reachable in Wizard World; the headed run over three widgets; `docs/MINIGAMES_GUIDE.md`; handoff; versions.

## Session log
- 20 Oct 2026: plan approved ("go", defaults); M0 built and verified; M1 built and verified; M2 built and verified.
