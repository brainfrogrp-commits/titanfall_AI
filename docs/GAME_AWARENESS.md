# Game awareness and speed

## What BT can know
The `TF2VR.BTVoice` mod reads the game every 1.5 seconds and sends the app only what changed
(plus a heartbeat every 15 s). BT gets it as plain sentences:

| What | How it is read |
|---|---|
| Mission | the map name (`sp_beacon` etc.), which also sets what BT is allowed to know |
| In the Titan or on foot | whether the player entity is a Titan |
| Indoors / under cover / outdoors | five rays fanned upward; counts how many hit something solid within about 15 m |
| Pilot health, BT's health | health divided by max health |
| How far away BT is (on foot) | distance to your Titan |
| Weapon in hand | the active weapon's class name, shown as a friendly name where known |
| Enemies nearby, and how many are Titans | NPCs on another team within about 60 m |
| Movement | wallrunning, sliding, airborne, crouching, standing |

Events that can make BT speak unprompted (rate-limited, and he may choose silence):
arriving at a mission, embarking, disembarking, health dropping below 30 percent, death.

**Indoors/outdoors is a guess.** The game has no such flag. A very high ceiling (a big hangar) reads as
outdoors, and an overhang reads as "under cover". Change `BTVOICE_COVER_RANGE` in the mod to tune it.

## Install the mod
1. Close the game completely (mods are only loaded when it starts).
2. Double-click **`mod\install_mod.bat`**. It finds your Titanfall 2 VR folder, copies the mod into
   `<Titanfall2>\TF2VR\mods\`, turns on the **`-allowlocalhttp`** launch flag, and then runs the checker.
   - The flag is needed because Northstar blocks game scripts from talking to localhost otherwise. It is added to
     `<Titanfall2>\TF2VR\tools\launch.json` (that is the file the VR launcher actually reads, with a backup saved
     as `launch.json.bak`) and to `ns_startup_args.txt`.
   - If it cannot find the game, give it the folder that contains `Titanfall2VRLauncher.exe`:
     `mod\install_mod.bat "C:\path\to\Titanfall2"`.
   - If Windows refuses to write to the game folder, run it again from a PowerShell opened with
     "Run as administrator".
3. Start the app, then start the game from the VR launcher as usual.
4. After a level loads, the banner at the top of the app's page should turn green ("Connected to the game").

**After a VR mod update**, run `install_mod.bat` again: the update can reset `launch.json`.

## When the banner says the app is receiving nothing
Double-click **`mod\check_mod.bat`** (with the app running and the game started at least once). It checks, and tells
you in plain words:
- whether the mod is installed where the game looks for it, and not switched off;
- whether the `-allowlocalhttp` flag is set;
- what the game's own log says: whether it shows `[BTVoice] started`, and any script or compile errors;
- whether the app itself has heard anything.

Reading the result: if the log shows the mod started but the app hears nothing, the flag is the usual cause. If the log
does not show it starting, the game did not load the mod (wrong folder, switched off, or a script error, which the
checker prints). Send me the checker's output and I can tell which.

## Reading the banner
The banner at the top of the settings page tells you what is going on:
- **Green, "Connected to the game"** and "BT thinks you are on: <mission>": all good.
- **Red, "Titanfall 2 is running, but this app has received nothing"**: the mod is not installed or not loading,
  or the game was launched without `-allowlocalhttp`.
- **"BT doesn't know which mission this is"**: BT will say so if asked, instead of guessing. Pick the mission
  under Game awareness, or fix the connection.

## If it does not work
- **"nothing received from the game yet"**: run `mod\check_mod.bat`; see above.
- **"Game sensor problem: ... sensor failed"** in the Conversation box: one sensor hit a script error
  (see the game console for the exact line). The others keep working. Send me that text.
- Updating the VR mod through CircuitLord's installer should leave the BTVoice folder alone, because
  it only removes files it installed, but check after an update.

## Not tested yet
I could not run the game here. The mod's script and its HTTP call were written against the Northstar
documentation (as summarized by search) and the VR mod's own scripts. Expect to fix something on first run.

## Speed
BT now starts speaking at the end of the first sentence instead of after the whole reply:
the model streams its answer, each sentence goes to Inworld as soon as it is complete, and the next
sentence is prepared while the current one plays. The speech model and the secure connections are
prepared at startup. After each answer the Conversation box shows a "Speed:" line with the time spent
on speech recognition, the model's first words, and the first sound.

Tuning, in order of effect:
1. **Speech recognition**: pick `base.en` (English only, faster and more accurate than `base`), or `tiny.en`
   if the game stutters.
2. **Pause that ends a sentence** (Talk section): 0.8 s by default; try 0.5 to 0.6 so BT starts sooner.
3. **Model**: the OpenRouter model slug is the next biggest piece. Smaller, faster models answer sooner.
