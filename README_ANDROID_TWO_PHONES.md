# Duel Master Battle on two Android phones

There is one game, **Wizard World**: a living civilisation with a wizard's apprenticeship inside it. The main menu has four entries,
**Play Single Player**, **Host Multiplayer**, **Join Multiplayer** and **Settings**. Alone you play the same world with a fellow
apprentice, Mira, for company (an AI wizard who walks with you and will duel you for practice); with a friend you share it.
The notes below are about the two-phone game. (Version 0.3.0 replaces 0.2.0: install it on **both** phones, an older phone
cannot join a 0.3.0 host.)

**New in 0.3.0 (16 October 2026):** apprentices are mortal (a lost duel between apprentices is a death; the living one can bring the
dead one back; your mother has words), the world never starts over (Continue as, A new apprentice, a world that catches up on the
time it was closed), a free opening with no objective, the village's rats and disputes, and the Trial of Champions east of the
village: a shared dungeon drawn in the old pixel art, with the book's choices, Ward duels on the real board and a champion's door.
Read `docs/OPENING_RPG_PLAYER_GUIDE.md` (one page) and run `docs/OPENING_RPG_TWO_PHONE_CHECKLIST.md` on the phones: none of it has
been played on a phone yet.

Two people, two phones, one Wi-Fi, one living world. One phone runs the world and plays in it; the other joins. Nothing
needs the internet once the app is installed. Whether the game turns cooperative or competitive is up to the two of you:
wander the settlements together, talk to people, take on quests and outbreaks and watch the civilisation grow, or seek each
other out and settle it in a Ward duel.

What is on the phones is the Godot client plus the real Python simulation packed into the same app, so the host phone
needs no computer. The design and the code are described in `docs/MOBILE_LAN_MULTIPLAYER.md`.

## 1. What you need

- Two 64-bit Android phones (Android 7 or newer, arm64, which is every phone sold since about 2017). 32-bit phones cannot run the app.
- A Wi-Fi network both phones can join, or a hotspot on one of the phones (a hotspot is the most reliable: home routers
  are fine, but guest and campus networks often block phone-to-phone traffic).
- This Windows PC once, to build the app: Godot 4.5.1 (already here), Python 3 (already here), about 4 GB of free disk and
  an internet connection for the one-time tool download.

## 2. Build the app (once, on this PC)

1. Close the Godot editor if it is open.
2. Double-click **`Setup Android Build Tools.bat`**. It downloads JDK 17, the Android SDK command-line tools, the SDK
   packages Godot 4.5 asks for (platform-tools, build-tools 35, platform 35, NDK 28) and the Godot 4.5.1 export templates,
   about 3 GB in all, into your user profile (nothing system-wide), creates the debug signing key and points Godot at the
   tools. Part way through it asks you to accept the Android SDK licence: answer `y` to each prompt. Expect 15 to 30 minutes
   depending on your connection. It ends with `ANDROID_TOOLCHAIN_OK`. Safe to run again if it was interrupted.
3. Double-click **`Build Android APK.bat`**. The first build downloads Gradle, the Android Gradle plugin, Chaquopy and the
   Android CPython runtime (another 1 GB, 10 to 20 minutes); later builds take a couple of minutes. It ends with
   `ANDROID_APK_OK` and the file **`build\android\DuelMasterBattle-debug.apk`** (about 100 MB), then installs it on any phone
   that is plugged in with USB debugging on (section 3). Run `Build Android APK.bat noinstall` to only build.

If the build fails, the log is `build\android\export-debug.log`; section 6 lists the usual causes.

## 3. Install the app on both phones

Either way below works; do the same on each phone.

**By USB cable (recommended).**

1. On the phone: Settings > About phone > tap *Build number* seven times (this unlocks Developer options).
2. Settings > System > Developer options > switch *USB debugging* on.
3. Plug the phone into the PC. If the phone asks, choose *File transfer* and accept *Allow USB debugging from this computer*.
4. Double-click **`Install APK On Phones.bat`**. It installs the APK on every phone that is plugged in and prints
   `ANDROID_INSTALL_OK`. Repeat with the second phone (or plug both in at once).

**By copying the file.** Send `build\android\DuelMasterBattle-debug.apk` to the phone (USB file copy, Nearby Share, a
chat message to yourself, a cloud drive), open it in the phone's Files app, and allow installing from that app when
Android asks. Both phones must have the **same** APK: the game refuses to join a host built from a different version.

The app appears as **Duel Master Battle**. Updating later: build again and install again; the new build replaces the old one.

## 4. Play

Both phones on the same Wi-Fi (or one phone's hotspot, with the other phone connected to it). Mobile data can be off.

**Phone A (the host)**

1. Open Duel Master Battle > **Host Multiplayer**.
2. Type your name, keep or change the game name and the four-digit join code, choose the map (`small` is right for a
   first game), then **START HOSTING**. The world is built on the phone: 10 to 30 seconds.
3. The lobby shows your Wi-Fi address and the join code. Tell them to the other player.

**Phone B (the guest)**

4. Open Duel Master Battle > **Join Multiplayer**. Type your name and the join code.
5. Tap the game under *Games on this Wi-Fi*. If the list stays empty, type Phone A's Wi-Fi address and tap **JOIN**.
6. Both lobbies now show both names.

**Phone A:** tap **START THE WORLD**. Both phones enter the world beside the same settlement, each wizard centred on its own
screen, the other wizard visible with a name label. The line at the top reads `LAN host · 2 online` / `LAN joined · 2 online`.

**Cooperative play.** Walk with the pad. Walk up to anyone and tap **✦** to talk; the conversation appears only on the
phone that tapped, but what you decide changes the one shared world, and the quest line on both phones updates. Open the
journal from the top bar for the current objective. When an outbreak starts, the objective names it: walk inside the
purple outline and use **Treat** to clear it. Watch the settlements: workers, carts, new buildings, the era line, trade
caravans and the factions' wars are the same on both phones because one simulation runs them.

**Competitive play.** Walk up to the other wizard. When you are within two tiles, a **⚔ Duel** button appears above ✦.
Tap it; the other phone shows the challenge with **Accept** / **Decline**. On Accept both boards open: each of you sets a
Ward of three spells and taps **Lock**, then you both guess **at the same time**: there are no turns, so whoever thinks faster
makes more guesses while the other is still deciding, and the first guess that breaks the other's Ward wins at once. Each of you
has ten casts. The rival's Ward stays hidden (`?`) until the end; the host scores every cast, so neither phone can cheat. The result screen names the winner and shows both Wards; **Continue** on both
returns you to the world where you left it. The world is paused during a duel and resumes afterwards. The fire-magic
cooldown is per player.

**Single player.** **Play Single Player** builds a private Wizard World on the phone and opens it with the apprentice's
arrival. Mira keeps near you; walk up to her and tap **⚔ Duel Mira** for a practice Ward duel (she thinks for 5 to 11 seconds
between casts, so a quick player makes several guesses to her one). The pause menu has **Save game** and **Save and leave**; the
game also saves itself every five minutes and when the app goes to the background, and **Play Single Player** then offers
**Continue campaign**. The old Ashwell adventure is no longer part of the game.

**Leaving.** The pause menu (menu button, top left) has **Leave**. If the host leaves or the host phone sleeps for long,
the game ends for both: keep the host phone awake and in the app. A guest who loses Wi-Fi for a moment sees
`connection lost · reconnecting…` and is put back where it was when the connection returns.

## 5. Fallback: host the world on the PC

If the phone-hosted build gives trouble (section 7 says what is unverified), the same APK can join a world run on this PC.

1. Double-click **`Host LAN Game.bat`**, type a join code (Enter keeps `1234`). If Windows asks whether Python may
   communicate on networks, allow it on private networks (the game uses TCP 8765 and UDP 8767). The window prints a
   `HYBRID_HOST_READY` line whose `lan` list is this PC's Wi-Fi address.
2. Both phones: **Join Multiplayer**, the code, tap the game in the list (or type the PC's address). The first phone to join
   gets the **START THE WORLD** button. Play is identical from there.
3. Closing the window ends the game.

A client-only APK without the packed Python (`Build Android APK.bat client`, output `DuelMasterBattle-client.apk`) also
works for this; it is a plain Godot export and cannot host.

## 6. Troubleshooting

| What you see | What to do |
| --- | --- |
| *No games found yet* on the join screen | Both phones on the same Wi-Fi? Host phone still on its lobby screen? Some routers block discovery broadcasts: type the host's address, or use a phone hotspot. |
| *No game is answering at that address* | The host is not hosting any more, the address is wrong, or the network isolates clients. Use a hotspot. |
| *The host runs a different game version* | Install the same APK on both phones. |
| *The host did not answer in time* | Guest or client-isolation Wi-Fi: use a hotspot. |
| *This build cannot run the world on this device* on the Host screen | You installed the client-only APK, or the packed Python failed to start. Host on the PC (section 5) or rebuild the full APK. |
| *App not installed* / parse error when opening the APK | The phone is 32-bit, or an older build with a different signing key is installed: uninstall Duel Master Battle first. |
| The PC build says the toolchain is incomplete | Run `Setup Android Build Tools.bat` again; it lists what is still missing. |
| The gradle step fails with a Python version message | Chaquopy packages the same Python major.minor as the PC's `py -3`; that must be 3.11 to 3.15. `build_apk.ps1` passes it automatically. |
| The world is slow on the host phone | Choose the `small` map. The host phone also renders the world, which is the heaviest part today (`docs/MOBILE_LAN_MULTIPLAYER.md`, section 11). |
| The PC host is not reachable | Windows Firewall: allow Python on private networks, or add inbound rules for TCP 8765 and UDP 8767. |

## 7. Honest status

Verified on this PC on 15 October 2026 (Windows 11, Python 3.14, Godot 4.5.1): the LAN host, two clients, a complete
host-scored Ward duel, shared quests, reconnection (17 automated tests over real sockets), the Godot client against a
Python host with a scripted second human (headed acceptance with screenshots), the Python sources staged for the phone and
self-tested in isolation, the gradle template overlay, and **the APK itself**: `Setup Android Build Tools.bat` and
`Build Android APK.bat` were run on this PC on 15 October 2026 and produced `build\android\DuelMasterBattle-debug.apk`
(152 MB; arm64 only; signed with the debug key, APK signature scheme v2; CPython 3.14 and the packed game sources inside;
package `com.duelmasterbattle.game` 0.1.0 (the first build; the corrected build is 0.2.0, version code 2, see `docs/ANDROID_PLAYTEST_CORRECTIONS.md`), min SDK 24, target SDK 35). Not yet verified anywhere: the game on physical
phones (none was attached to this PC), so whether the packed Python starts on a real phone is the first thing the two-phone
session will tell. The apprentice campaign (lessons, the stranger) has been played single-player; two players inside it
over the LAN is untested, so expect the story beats to follow the host's wizard. Treat the first two-phone session as the
test it is: `docs/MOBILE_LAN_MULTIPLAYER.md` section 10 is the step-by-step checklist, and section 11 lists the known limits.

**0.3.0 (16 October 2026):** the opening-RPG programme (mortality, the permanent world, the free opening, the village, the Trial,
Mira) is proven on this PC by Python tests through real sessions and by headed Godot runs with screenshots
(`docs/ledger/OPENING_RPG_PROGRESS.md`), and the 0.3.0 APK is built with the asset audit and the exported-pack art probe extended
to the Trial's pixel art. **No phone has run 0.3.0.** The owner's run is `docs/OPENING_RPG_TWO_PHONE_CHECKLIST.md`.
