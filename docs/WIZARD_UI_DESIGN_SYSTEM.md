# Wizard Mode: UI design system

Status: implemented on `feature/wizard-mode-implementation` (polish milestone, 15 October 2026). One look for every narrative panel: arcane fantasy with
classic strategy-game chrome. It extends the two existing design files; it does not replace them and there is no second styling system.

| Existing file | What this milestone added to it |
| --- | --- |
| `godot_project/client/scripts/visual_theme.gd` | the narrative palette (`COLOR_CARD`, `COLOR_CARD_EDGE`, `COLOR_PARCHMENT`, `COLOR_GOLD`, `COLOR_CHOICE*`, `COLOR_HUD_BG`), `narr_card_style`, `narr_hud_style`, `narr_button_style`, `style_narr_button` |
| `godot_project/client/ui/responsive_modal.gd` | `window_info` (physical window, stretch scale, virtual viewport) and `metrics` (every narrative size, in physical pixels) |

New widgets, all built only from those two files: `client/ui/narrative_card.gd` (`DmbNarrativeCard`) and `client/ui/campaign_hud.gd` (`DmbCampaignHud`).

## 1. Look

* **Deep indigo cards** (`#161230`) with a **muted gold edge** (`#9a7b3f`), rounded corners, a soft shadow.
* **Parchment text** (`#efe6cf`; secondary `#c8bea4`). **Gold** (`#e2bb5e`) is for names, titles and the one primary action on a card, nowhere else.
* **Choices** are indigo buttons with a violet edge (`#5b4fb8`); the **primary action** (Continue, Begin the duel, Talk, Close) has a gold edge and gold text.
* Nothing floats over the world. People, buildings and trees show no labels; the world is inspected by clicking.
* People are drawn like every other worker. No rings, no name plates, no per-quest marks. The teacher has one small gold diamond while a lesson is waiting.

## 2. Sizes: physical pixels, converted

The project stretches a 720 x 1280 reference (`canvas_items`, aspect `expand`): the virtual viewport is the window divided by
`min(window.x / 720, window.y / 1280)`. Sizing in virtual pixels makes text tiny on a landscape monitor and huge on a phone, so every narrative size is chosen in
**physical pixels** (`DmbResponsiveModal.metrics`) and converted with `window_info(...).k` (virtual per physical pixel). Nothing is shrunk to fit: text stays
the size it is chosen to be and long content scrolls.

| Quantity | Rule (physical px) |
| --- | --- |
| Body text | `clamp(shorter side / 24, 16, 22)` |
| Title / small | body x 1.25 / body x 0.84 |
| Touch target | every button at least 48 px tall (`NARR_TOUCH_MIN`) |
| Margin | `clamp(shorter side x 0.03, 10, 24)` |
| Card width | at most 560 (sheet) or 600 (modal), 640 / 680 on windows 1500 px or wider; never wider than the window minus margins |
| Card height | modal: window minus margins; sheet: 70 % of a portrait window, 82 % of a landscape one; the body scrolls inside |

Window sizes 450 x 800, 720 x 1280, 800 x 450, 1280 x 720 and 1920 x 1080 are all checked by `client/tests/run_hybrid_ui.gd` (see section 6).

## 3. Components

`DmbNarrativeCard(kind)`: header (title, subtitle, optional progress), a scrolling body (text, then the choices), and a footer that stays visible.
`kind = "sheet"` sits at the bottom centre (conversations, inspect). `kind = "modal"` is centred (arrival, journal, pause menu). It is positioned
explicitly from its real size and is always inside the viewport. It re-lays itself out when the viewport changes (`relayout`), and fits its scroll area
over two frames after any content change (wrapped text only knows its height once it has a width).

| Panel | Where | Kind | Buttons |
| --- | --- | --- | --- |
| Arrival | `story_ui.gd` (`opening_card`) | modal | Skip, Continue / Begin (primary); `1 / 3` and dots show progress |
| Conversation | `story_ui.gd` (`dialog_card`) | sheet | the replies, then Leave (Esc), or one Continue / Begin the duel when the conversation has ended |
| Journal | `story_ui.gd` (`journal`) | modal | Close (J) |
| Inspect (person, building, tree, ...) | `wizard_labels.gd` (`panel`) | sheet | Talk, Ask <name> to come out, Burn it with fire magic, Close |
| Pause menu | `hybrid_world.gd` (`menu_card`) | modal | Continue, Save game, Load game, Save and quit; Load lists the three slots |
| Scene page (the stranger's arrival, the confrontation, the victory) | `campaign_ui.gd` (`scene_card`) | sheet | the speaker's name and role, the page, the apprentice's answers when the page asks for one (an Aspect check shows its Aspect and, afterwards, the figures: score, evidence, relationship against the threshold), `1 / 11` progress, one Continue (or Begin the duel on the last page); the world waits, the camera is guided to the speaker |
| Game over | `campaign_ui.gd` (`over_card`) | modal | New game (primary), Quit; nothing else reaches the dead apprentice's game (no pause menu, no Escape) |
| HUD | `campaign_hud.gd` | top left | the title (era and cycle) opens the full read-out; Journal (J) |

## 4. HUD

Objective first: **era and cycle** on the title line, the **current objective** under it (the next lesson, the open quest, or the outbreak in this region),
and what E does if someone is within reach. Victory points and era progress are behind the title (tap it). The HUD steps aside whenever a conversation, the
arrival, the journal, a menu or a duel owns the screen, so it never sits on a conversation. When a lesson is learned or a quest changes it flashes one line
("Lesson learned: ...", "New in your journal: ...").

## 5. Input

* Click or tap a thing: the press only remembers what is under the pointer; the click is taken **on release**, and not at all if a pinch or a drag happened
  between (so a pinch can never select anything). A click on empty ground puts the inspect card away.
* A card is modal for the keyboard: Escape leaves (or acknowledges, on a closing reply), Enter or Space takes the primary button, 1 to 9 pick a reply, and no
  other key reaches the game behind it. Escape, the Leave button and the acknowledge button all end a conversation the same way (`end_talk`).
* Camera: `+`, `=`, `-` and the numpad keys, the mouse wheel and a two-finger pinch zoom the world, never the interface. Zoom is stored as physical pixels per map tile
  (default 52, range 26 to 128) and remembered in the settings (`hybrid_zoom_px`); it is ignored while a card owns the screen. Zoom about the wizard, who is
  always in the middle of the picture (the world point under a pinch is not kept fixed: documented limitation).

## 6. Tests that hold it

| Test | What it proves |
| --- | --- |
| `run_hybrid_ui.gd` (`ui`) | at five window sizes: arrival, conversation (ordinary and very long), journal (very long), inspect (person, building, tree), pause menu and HUD are inside the viewport; no text or button sticks out; body text is at least 16 physical px; every button is at least 44 px; long content scrolls to its last line; the footer stays visible; the HUD steps aside; Escape, Leave and Continue behave the same |
| `run_hybrid_camera.gd` (`camera`) | default closeness; `+ = -` numpad; wheel; pinch zooms and selects nothing; limits; persistence; cards do not change size with zoom; nothing zooms behind a conversation; clicks pick the right figure at three zoom levels; the same closeness in another window |
| `run_hybrid_apprentice.gd` (`apprentice_win`, `apprentice_lose`) | the whole opening at the project's 450 x 800 window through the real UI and the real board: lessons, Aspect checks, worldview answers, exploration, the stranger's scenes, the mentor's death, the lethal duel, then the aftermath and the final objective, or Game Over and New game |
| `run_hybrid_conversation.gd` (`conversation`) | a moving lumberjack, forester, carrier and soldier stop and stand while others keep moving, and resume; death during a conversation closes it |
| `run_hybrid_tutorial.gd` (`tutorial`), `run_hybrid_launch.gd` (`launch`), `run_hybrid_wizard.gd` (`wizard`) | the whole opening, the lessons, both duels, the quest, save and load, fire magic, all through the real UI |

A real window cannot always be opened at every size (the window manager keeps this laptop's window within the screen), so `run_hybrid_ui.gd` sets each size on
the real window and, where the window did not take it, lays the panels out for that size with the same stretch maths (`meta "sim_window"`); it logs which
sizes were real and takes screenshots only of real windows.

A headed window that is not in front receives no draws, so canvas transforms and the art layer's gliding positions go stale. Click helpers must
`await RenderingServer.frame_post_draw` and click where `_art._vis` says a figure is drawn.
