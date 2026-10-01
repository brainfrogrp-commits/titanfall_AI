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
1. Close the game and the app is fine to leave running.
2. Run `mod\install_mod.bat "C:\path\to\your\Titanfall2 folder"` (the folder that contains
   `Titanfall2VRLauncher.exe`), or copy `mod\TF2VR.BTVoice` into `<Titanfall2>\TF2VR\mods\` yourself.
3. The game must be launched with **`-allowlocalhttp`**, because Northstar blocks scripts from talking to
   localhost otherwise. The install script puts it in `<Titanfall2>\ns_startup_args.txt`. If the
   Game connection line never turns green, add `"-allowlocalhttp"` to the `arguments` list in
   `<Titanfall2>\TF2VR\tools\launch.json` instead (a VR mod update may overwrite that file).
4. Start the app, then the game. In the app's **Game awareness** section, "Game connection" should say
   "(connected)" a few seconds after the level loads, and "What BT currently knows" should fill in.

## If it does not work
- **"nothing received from the game yet"**: the launch flag is missing or not applied, or the mod did not
  load. Look in the game's console/log for `[BTVoice] started`. Without that line the mod did not load.
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
