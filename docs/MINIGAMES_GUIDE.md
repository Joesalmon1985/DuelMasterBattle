# The village's games: a guide

Eighteen games the people of the village play with the apprentice, each tied to the work of the person who plays it. Nothing is won or lost but
the game itself: no ware, no coin, no magic, no standing moves because of a game (the owner's brief). Plan: `docs/PLAN_VILLAGE_MINIGAMES.md`;
progress: `docs/ledger/MINIGAMES_PROGRESS.md`.

## Playing

Walk up to a person and talk (E, the action button, or tap them and choose Talk). Among what they have to say is the offer of their game
("Teach me the game of three colours.", "What is the game you play with the dice?"). Take it: they explain the game in their own words, and
**Lay out the game** puts the table on the screen. The person waits while you play (they are held, the way a conversation holds them); the world
goes on around you. On the table: the areas of the game (cards, dice, tallies, a board, faces), the host's last words, and the moves you can make
as buttons (1 to 9 on a keyboard) or by tapping the pieces themselves. **Leave the table** (Escape) at any time: unfinished is unfinished, and the
host says so. When the game ends, the host's closing line comes back on the conversation card, with the offer to play again. The pause menu's
**The village's games** page lists what you have found and played and where every game is.

A building's inspect card says which games are played there ("Played here: ..."). A due rung of the magic ladder waits until the table is closed.

## The developer's village of games

Every host in one village, no stranger, nothing to interrupt: the developer menu (`DMB_DEV_MENU=1`, or `--dmb-dev`) has **GAMES VILLAGE**, and on a phone
(which cannot reach the developer menu) Settings has **Developer: the village of games**. Either starts a
private single-player session on its own saves folder (`dmb_runs/games_village`, never the player's world), built fresh on seed 507 with the early
buildings the start lacks (a farm, a tavern, a bakery, a fisher's hut), the mother, the warehouse keeper, a sawyer at the sawmill, a water-carrier at
the well, and a Rollkeeper with two contestants at a fire on the green. The apprentice begins beside the warehouse; the status line counts the games
found. On the host's command line the same village is `--games-village` (or `HYBRID_GAMES_VILLAGE=1`).

Headed test: `client/tests/run_hybrid_minigames.gd` starts the village itself and plays the games named in `HYBRID_GAMES` (default: one per widget);
`HYBRID_SHOT_DIR` collects screenshots. Python: `py -3 -m pytest WizardRTSHybrid/tests/test_minigames_rules.py WizardRTSHybrid/tests/test_minigames_village.py -q`.

## The games, who plays them, and the rules in the villagers' words

| Game | Host | Rules as played here |
| --- | --- | --- |
| **Three colours, no knots** (Rock Paper Scissors) | the mentor | Flame burns Vine, Vine drinks Frost, Frost kills Flame. Best of five. The mentor leans on the sign that beats your last throw, sometimes. |
| **The Ward you cannot see** (Hanabi) | the mentor, with Mira | Three players, five colours (Flame, Frost, Vine, Light, Stone), ones to fives. Your cards face away from you. A turn: play a card, discard one for a clue token (eight at most), or spend a token to tell someone every card of one colour or one number they hold. A wrong play is a fracture; three and the Ward breaks. The last card gives everyone one more turn. Eighteen built wins. |
| **Felling the big one** (Can't Stop) | the lumberjack | Four dice, paired as you like; each pair's sum is a trunk (2 to 12). Strokes on at most three trunks a turn. Bank your cuts or throw again; a throw that fits none of your trunks splits the trunk and the turn's cuts are lost. A trunk cut through is yours. Three trunks win. |
| **Which sapling is new?** (memory) | the forester | Today's plantings: three, then four, then five. Each time one is new; point at it. Point at an old one and it stops. Fourteen named is a forester's eye. |
| **Knucklebones** (Yahtzee) | the stonemason | Five carved stones, three throws a turn, hold by tapping. Thirteen orders on the slate (singles to sixes with the bonus of 35 at 63, three and four of a face, a full course, a short and a long run of ashlar, five of a face, rubble). The better slate wins. |
| **Clearing the face** (sliding blocks) | the stonemason; **The fussy sheep** at the farm | Blocks (or sheep) slide one cell at a time, never over each other. Each leaves through the gate of its chalk colour on the rim. Tap a block, then a free cell in line with it, or the rim; the arrow keys work too. Every board can be cleared; the par is shown. |
| **Tracks** (reaction) | the hunter | A sign, then another. Same beast or different? Say it fast: two points quick and right, one slow and right, nothing wrong. Twelve signs. |
| **Skins** (five-card draw) | the hunter | Pebbles for pelts. An ante each, five cards, bet (check, bet, call, raise, fold), throw away up to three by tapping and take fresh, bet again, show. Five hands. More pebbles than you came with wins. |
| **Who ordered the planks?** (Guess Who) | the sawyer | The faces are the village's real people. Tap the one you think of; the sawyer has the one who ordered in mind. Ask yes-or-no questions about trade, tribe, what they carry, where they work, hat, beard, hair; the faces that cannot be it turn down. Name them by tapping a face. A wrong name loses. The sawyer asks too. |
| **Twenty-one feet** (Blackjack) | the sawyer | Cards are plank lengths: cut to twenty-one, not an inch over. Two pebbles a hand; the sawyer stands on seventeen; a natural pays three to two; double on two cards; split a pair once. Five hands. |
| **The windlass** (Roulette) | the water-carrier | Thirty-seven notches, one green. A pebble a spin on red or black rope, odd or even, low or high, a dozen, or a notch (35 to 1). Eight spins. |
| **The tally board** (Rummikub) | the warehouse keeper | Tallies one to thirteen in four colours, no jokers, fourteen each. Lay runs of a colour or sets of a number (three or more); open the ledger with thirty points from your rack; afterwards add a tally to any meld. Lay nothing and you draw. Empty rack wins; a dry pool ends on the lighter rack. Tap tallies to select, then lay or add. |
| **Under the cloth** (Skull) | a carrier | Three carriers, three flowers and a rat skull each on covered carts. Lay a cart face down; then lay another or bid how many carts you dare uncover. Raise or pass. The bidder uncovers their own first, then anyone's, one at a time: a skull costs a cart and the round; the bid made is a point; two points win. |
| **The carriers' pot** (Texas Hold'em) | a carrier | Heads up, fixed limit, blinds one and two. Two cards each, the flop, the turn and the river on the road, a round of betting on each; best five of seven. Six hands. |
| **Bid your bouts** (Oh Hell) | the Rollkeeper, with two contestants | Hands of five, four, three, two, one, two, three; trumps turned. Bid your tricks; the dealer may not make the bids come out even. Exactly your bid scores ten plus the bid; anything else nothing. |
| **Knocked out** (Knock-out Whist) | a contestant | Seven cards, then six, down to one. Trumps turned, then chosen by whoever took most tricks. Take no trick and you are out, except once: a dog's life, one card next hand to play on any trick you choose. Last standing. |
| **The stew carrots** (Take the Last Carrot) | the mother | Three rows of carrots. Take one, two or three from one row. Whoever takes the last carrot peels the lot. |
| **The same bolt** (Pairs) | the mother | Sixteen swatches face down, each with a twin. Turn two; a pair is kept and you go again; a miss turns back. Most pairs when the basket is empty. |

## For the next developer

* An engine is one module in `WizardRTSHybrid/wizard_rts/minigames/` following `base.py` (`new`, `actions`, `act`, `bot`, `view`; `prepare` when it reads the
  world). Register it in `catalogue.ENGINES`; its words go in `data/narrative/minigames.json` (`host`, `offer`, `intro`, `lines`, `opts`, `skin`).
* The client draws whatever the view's `areas` say (`text`, `score`, `signs`, `cards`, `dice`, `tiles`, `grid`, `faces`, `choices`) and offers the
  view's `actions`; a `hidden` action is one the pieces themselves send. A `timed` view makes the table send `ms` with every action.
* The table is per apprentice seat (`world.narrative["minigames"]`), dropped with its conversation and on a load. `minigame_act` keeps the conversation
  from going idle; walking away ends both.
