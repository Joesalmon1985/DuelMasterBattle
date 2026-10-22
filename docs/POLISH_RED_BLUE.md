# Red team / blue team: readability and usability of every screen (branch `feature/polish-watching-feel`)

The owner asked (22 Oct 2026) for a red team to criticise the visual display for readability, usability and looks across every menu and screen
the game can show, with player visions (screenshots from the headed runs, the same picture a phone shows at 720 x 1280), and a blue team to fix
what it finds, round after round. Screens come from `client/tests/run_hybrid_minigames.gd` (the village, the conversation card, a table per
widget, the Games page) and `run_menu_routes.gd` (the main menu); older shots in `WizardRTSHybrid/docs/evidence/{minigames,opening_rpg,lan}`
cover the opening, the Trial, the duel board and the LAN screens. Evidence of each round: `WizardRTSHybrid/docs/evidence/polish/`.

Red findings are numbered R*, blue fixes B*. A finding without a fix is parked with a reason.

## Round 1

### Red team (the first polish build, 0.5.1)

| # | Screen | Finding |
|---|---|---|
| R1 | Any table | Score line "you 0 - Skebok Hardfist 0": the player's seat is lower-case "you" beside capitalised names. |
| R2 | Knock-out Whist | "You 0 tricks   Serra of the White Road 0 tricks   another contestant 0 tricks" wraps mid-score on a phone. |
| R3 | Guess Who | Faces are 96 px: names cut ("Mormund Iron..", "Serra of the Wh..") and the traits are 9 px, unreadable on a phone. Ten faces leave a void between the board and the message. |
| R4 | Sliding blocks | A 6 x 6 board of 44 px cells uses a third of the panel's width. |
| R5 | Every table, every card | "(Esc)" and "1." key hints on a phone, which has no keys. |
| R6 | Conversation card, Games page | Long choice lists and long pages scroll, but nothing says so: the last choice shows as a sliver, the Games page's Back button is a 6 px line at the bottom. |
| R7 | Games page | Back is a choice at the end of the scrolling list, not a footer. |
| R8 | Village HUD | "Games found: 0 of 18 (menu: The village's games)" wraps onto two lines in the top-right status block; the block also stays up over tables and cards. |
| R9 | Conversation card | The card looked translucent over water. Turned out to be the screenshot timing: 4 frames into the 0.22 s pop-in. |
| R10 | Games page | `[x]` / `[ ]` ASCII boxes look crude; wrapped lines lose their indent. |
| R11 | Pause menu, Games page | The top bar (menu button, "Wizard RTS", Magic) shows through under the modal card. |
| R12 | Guess Who | Two faces with no sprite fall back to an initial in a circle ("S", "A"). |
| R13 | Main menu | The player's figure (a boxy 16 px character) is crude beside the detailed wizard. |

### Blue team

| # | Fix |
|---|---|
| B1 (R1) | The table renders the seat named "you" as "You" (`_who`). |
| B2 (R2) | A score line longer than 34 characters, or with more than three rows, becomes the two-column slate. |
| B3 (R3) | Faces are laid in a `GridContainer`, three to a row (four when more than twelve), each as wide as the panel allows (about 195 px on a phone); the name wraps to two lines at the space nearest its middle; name 11 to 17 px, traits 10 to 15 px; the grid's height is exact, so no void. |
| B4 (R4) | The grid's cell is sized from the panel's width (36 to 72 px). |
| B5 (R5) | No "(Esc)" and no "1." prefixes when `OS.has_feature("mobile")` (table and conversation card). |
| B6 (R6) | `client/ui/scroll_cue.gd`: a dark band and a bobbing gold chevron along the bottom of a scrolling body while content is hidden under it, fading as the reader reaches the end; on the conversation card, the pause menu and the table. |
| B7 (R7) | The Games page's Back is a footer button (always under the list); the pause menu's card listens to footer presses. |
| B8 (R8) | "Games found: n of 18"; the status block steps aside with the HUD while a card, a table, the menu or a duel has the screen. |
| B9 (R9) | Screenshots are taken 16 frames after the step, so tweens have settled (a test change, not a product one). |
| Parked R10 | The default font may lack a tick glyph; a glyph the font cannot draw is worse than ASCII. Revisit with a bundled font. |
| Parked R11 | The top bar is the Overworld's UI layer, shared with the touch pad; hiding it under modals touches the adventure's base scene. Next round if time allows. |
| Parked R12, R13 | Art, not layout: a hooded silhouette for sprite-less faces and a better player figure need drawing time. |

## Round 2

Round 1 verified on screen (`05_guesswho_table.png`: sixteen faces four to a row at about 150 px, names on two lines, traits readable, the chevron
cue under the grid; `99_games_page.png`: Back under the list, the cue over the last line; `01_rps_offer.png`: the cue under the fifth choice;
`03_slide_table.png`: the board across the panel, the slate for out/moves). Headed run `HYBRID_MINIGAMES_OK` over seven games.

### Red team

| # | Screen | Finding |
|---|---|---|
| R14 | Hanabi, Oh Hell | Thirteen buttons "Tell Skebok Hardfist their Flames / Frosts / Lights / 1s / 2s …" in three columns, each wrapping to three lines: a wall. Oh Hell's bids "Bid 0" to "Bid 7" the same way. |
| R15 | Any table | The HUD toast ("Rats in the Central Warehouse: 5 of them…") stays up over a table. |
| R16 | Guess Who, Rummikub | No host figure beside "with Hrunlag Blackback": a resident's row has no `definition` the art catalogue knows; the world draws them from their `figure`. |
| R17 | Pause menu, Games page, tables | The top strip (menu button, "Wizard RTS", Magic) stays under modal cards (R11 again, now with the code read). |
| R18 | Rummikub | Forty-pixel tallies with 13 to 20 on the rack; fine to read, cramped to tap. |
| R19 | Games page | Wrapped entries lose their indent. |

### Blue team

| # | Fix |
|---|---|
| B10 (R14) | Actions whose text shares a prefix (everything before the last word), three or more of them, are grouped under one small label ("Tell Skebok Hardfist their …", "Bid …") with a grid of short buttons (four columns for words of up to seven letters, three up to twelve, else two); the rest stay as full-width buttons. Number keys still count through in order. |
| B11 (R15) | The toast steps aside with the HUD while anything covers the world, and comes back if its time is not up. |
| B12 (R16) | The host picture uses a resident's `figure` as the worker definition, exactly as the world draws them. |
| B13 (R17) | The Overworld's top strip hides while a card, a table, the menu or a duel has the screen. |
| Parked R18 | A rack of twenty at 48 px would wrap to three rows; the tiles are tappable at 40 px on a 720-wide phone (about 7 mm). Watch on the device. |
| Parked R19 | Plain text in a RichTextLabel with bbcode off; a hanging indent needs bbcode or a table. Later. |

## Round 3

Round 2 verified on screen (`01_hanabi_table.png`: two labelled rows of short buttons instead of thirteen tall ones; `03_ohhell_table.png`:
"Bid …" with five short buttons; `02_guesswho_table.png`: the sawyer's figure beside his name; the top strip gone under every table).
Headed run `HYBRID_MINIGAMES_OK` over Hanabi, Guess Who, Oh Hell and RPS.

### Red team

| # | Screen | Finding |
|---|---|---|
| R20 | Oh Hell (desktop) | Grouped bids read "1. 0", "2. 1", "3. 2": the key number beside the bid number is a trap. |
| R21 | Oh Hell, Whist | "On the table" is an empty heading at the start of a trick; nothing says it is empty on purpose. |
| R22 | Oh Hell, Whist, Hanabi | A hand of five cards at 48 px, the face-down "??" captions at 11 px: readable, but small to tap, with half the row unused. |
| R23 | Guess Who | Two sprite-less people still fall back to a letter in a circle (R12, parked). |

### Blue team

| # | Fix |
|---|---|
| B14 (R20) | Grouped buttons carry no key number; the keys still work in order. |
| B15 (R21) | A cards row with nothing in it shows "(nothing yet)" in the small face. |
| B16 (R22) | Cards grow to the width the row has (up to 88 px, never below what the host asked), so a hand of five is five 88 px cards and a hand of thirteen wraps at the host's size. |

## Round 4

(after the round 3 evidence: the Settings overlay and the pause menu are the next screens on the list)
