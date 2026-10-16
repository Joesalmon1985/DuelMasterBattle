# The two-phone checklist for 0.3.0 (the brief's scenarios A to H as the plan maps them)

Read `README_ANDROID_TWO_PHONES.md` first (build, install, host, join: unchanged). `docs/MOBILE_LAN_MULTIPLAYER.md` section 10 is
the LAN checklist of 0.1.0/0.2.0 and still applies. This file adds the opening-RPG programme (`docs/PLAN_OPENING_RPG_AND_DEATHTRAP.md`).
Nothing here has been run on a phone by the implementer: every line was proven on the PC (Python tests through real sessions and
headed Godot runs with screenshots, listed in `docs/ledger/OPENING_RPG_PROGRESS.md`). Tick what the phones confirm; write down what
they do not.

Both phones on the same APK (0.3.0, version code 3; a 0.2.0 phone is refused with "different game version"). Phone A hosts.

## A. Immediate murder, and the body (M1)

1. Both in the world. Phone A walks up to Phone B, taps **⚔ Duel**; B accepts. Both lock a Ward; play until one Ward breaks. Each wizard's first three duels have three colours, the fourth has four (the invitation says "4 colours"). Duels between wizards have no wait between casts; in story duels (rats, the Trial's creatures) the cast button charges for two seconds instead of five; Mira thinks for 2.5 to 6 seconds a cast.
2. The loser's screen: "You are dead." banner, the avatar gone, a body on the ground where they stood, a **Watch <name>** button that follows
   the survivor with the camera. The winner's screen: the body row, no standing avatar for the loser.
3. The loser taps nothing for a while: the world goes on (workers move), no Game Over.
4. Record: did the body appear on both phones within a second?

## B. Resurrection, and the mother (M1)

1. The winner's mother walks over and opens a conversation on her own (a card the winner did not ask for). Choose **protest** then **will_do**.
2. The winner walks out of the village: a step past its edge is refused with the mother's words as a toast ("Not one step further").
3. The winner taps the body (or ✦ beside it) → **Bring them back**. A ring draws around the body for about six seconds; the loser's banner says
   "Bringing you back…"; the loser stands up where the body lay. The grounding lifts.
4. Mira (single player only): challenge her three times; the third is accepted with her provoked line.
5. Record: the channel's length on the phone; whether walking away cancels it (it should).

## C. The warehouse rats (M4)

1. Walk to the home warehouse: five small creatures scurry beside it (crawler sprites, one bigger).
2. Talk to the keeper: the complaint. Stand beside a rat, tap it → **Drive it off** → a small Ward duel (two colours) on the real board.
3. A win: the rat breaks apart (sound, toast with how many are left). A loss: "It got away… one cast fewer next time", and the next duel's board shows one cast fewer.
4. Single player: after the keeper has complained to you, Mira walks to a rat and fights it (her line arrives as a notice).
5. After the last rat: the keeper's thanks. Record how long the five took and whether the food stock line in the keeper's talk changed.

## D. The free opening (M3)

1. A new world: no objective is shown; the journal is not offered in Wizard World. Talk to the mentor or do not.
2. Skip the lessons entirely (never talk to the mentor): after a while the stranger arrives anyway; if you are not there, the mentor dies alone
   (the aftermath talk of the villagers says so).
3. Take the lessons: the stranger's confrontation is a scene with a judgement page that mentions what you did (kills, duels, deaths). Choose to
   challenge him or let him go.
4. Record: minutes from the world's start to the stranger on a phone, and whether a scene card ever blocked the other phone.

## E. Into the Trial unprepared (M5)

1. Walk east from the village (eighteen to thirty tiles) to the arch with two torches: "The Trial of Champions". The Rollkeeper and five
   contestants stand beside it.
2. Talk to the Rollkeeper with no lesson taken: the unprepared line, the choice "I am going in".
3. Tap the gate (or ✦ beside it): the cave tiles replace the map, the pocket strip appears, **Leave the Trial** shows in the doorway.
4. Walk: a wall refuses; the exit at the top of the entrance leads into the Footprint Fork (a new zone, the name at the top).
5. Record: the time the zone took to appear on the phone, and the walking feel (a step is validated by the host; a refused step snaps back).

## F. Shared items, and the other wizard inside (M5)

1. Phone A takes Sukumvit's box (✦ beside it): the card reads the note, the strip shows the note. Phone B enters and finds a second box
   beside the first with their own name (one box per apprentice); every other pickup is gone for the second.
2. Both in the same zone: each sees the other with a name label, moving. In different zones: not drawn.
3. Phone A faces the Giant Fly on the east loop: the introduction card, **Begin the duel**, the real board with the fly's own face. A loss wounds;
   a win removes the fly for both.
4. Record: whether the other wizard's steps glide or jump on the phone.

## G. Death in the Trial, and the next contestants (M5, M6)

0. (Added after the first phone playtest.) Inside the Trial the other wizard (Mira in single player) can be challenged when she stands within two tiles
   in the same zone: the **Duel** button appears there too; the loser dies where they stood and the winner can bring them back. The stranger's scene is
   never shown inside the dungeon: it waits and opens when you walk out of the gate. Zoom (pinch or +/-) keeps your wizard in the middle of the screen.

1. Phone A loses to the Trialmastiff in the galleries: dead inside the zone, the body drawn where they fell, the zone stays on screen.
2. Phone B walks to the body (same zone, within two tiles), taps it → **Bring them back**: A stands up beside the body with their pockets.
3. Both die inside (two lethal losses): the ending card for both; the run ends. Phone A: **A new apprentice** → enter the Trial again: a new run, the
   two bodies lie where they fell ("a body, long cold"), their pockets can be searched; the creatures are back.
4. The second half: the Dwarf's tests on the card (Stone learned), Throm on the board, the false eye's guardian, the mirrors, the gems, Igbut's door
   (a wrong order bites; the right one opens on daylight: both phones are let out at the gate).
5. Record: whether a phone that was resurrected inside came back at the right tile.

## H. The permanent world across sessions (M2)

1. Phone A leaves the game (pause menu); wait a real hour (or set the clock forward); **Continue as <name>**: the lobby shows "catching up"
   with the owed minutes; **Enter now** is allowed. The world is further along (new buildings, the era line).
2. The host's apprentice dead: **A new apprentice** retires them; the new one arrives a generation later; the mother's lines mention the previous
   one; the mentor, if dead, is dead.
3. Settings → **Start a new world…**: two confirmations; a fresh world.
4. **Phone measurement (M0, owed):** the catch-up rate on the host phone in simulated minutes per real second while catching up (the lobby page
   shows the progress), and the frame rate inside a Trial zone with both wizards in it. Write both into `docs/ledger/OPENING_RPG_PROGRESS.md` M0.

## What to send back

The ticks, the recorded numbers, the phone models, and screenshots of anything that looked wrong. The implementer's PC evidence for every
step above is under `WizardRTSHybrid/docs/evidence/opening_rpg/m1..m6/`.
