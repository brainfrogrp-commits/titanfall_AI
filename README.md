# BT-7274 Voice (Titanfall 2 VR)

Talk to BT in Titanfall 2 VR. Hold a key, speak, and BT answers in a voice from
Inworld. BT can also comment on what you're doing in game.

This is a companion app that runs next to the game. It does not modify
CircuitLord's Titanfall 2 VR mod.

## Run (Windows)
1. Install Python 3.10+.
2. Double-click **`START_BT_VOICE.bat`** in this folder. If double-clicking a `.bat` does nothing on your PC, double-click
   **`START_BT_VOICE.vbs`** instead: it opens the same window another way. Both start the app and open its page.
   To install the game mod, double-click `INSTALL_BT_MOD.vbs` (or `mod\install_mod.bat`); to diagnose it, `CHECK_BT_MOD.vbs`. First run installs dependencies (and downloads a
   small speech model on your first question).
3. The settings page opens at http://127.0.0.1:5757. Enter your **Inworld** and
   **OpenRouter** keys, pick a voice, press **Set key** to choose the talk key,
   then **Save settings**.
4. Start the game in VR as usual. Either turn on **Hands-free** (say "hey BT", talk, then "thanks BT" when done, or "goodbye BT" to close the app) or hold your talk key.
   OpenVR2Key only works with SteamVR; see `docs/CONTROLLER_INPUT.md` for OpenXR.

Settings and keys are stored in `%USERPROFILE%\.titanfall_bt\config.json`, outside
this repo. The server only listens on localhost.

## How it works
`key held -> mic -> faster-whisper (local) -> OpenRouter LLM (BT persona + game
context) -> Inworld TTS -> your speakers`

## Game awareness
The app exposes `POST http://127.0.0.1:5757/api/event` with JSON like
`{"type":"embark","text":"The Pilot embarked into BT.","data":{"map":"sp_boomtown"}}`.
Events become context for every answer. Types in `NOTABLE_EVENTS`
(`app/bt_voice/bt.py`) can also make BT speak unprompted, rate-limited by the
cooldown on the settings page. Use **Send a test event** to try it.

The Northstar script mod that sends real events from the game is the next
phase and is not built yet.

## Game awareness
The `mod/TF2VR.BTVoice` Northstar mod tells the app where you are, whether you are in the Titan,
health, weapon, nearby enemies and more. See `docs/GAME_AWARENESS.md` (includes install steps).

## If double-clicking a .bat file does nothing
Open PowerShell in this folder and run the files by name instead:

    cd C:\Users\skate\Desktop\VResources\titanfall_AI
    .\START_BT_VOICE.bat
    .\mod\install_mod.bat
    .\mod\check_mod.bat

To find out why double-clicking fails, run `cmd /c assoc .bat` (should print `.bat=batfile`) and
`cmd /c ftype batfile` (should print `batfile="%1" %*`). If the files came from a download, `Get-ChildItem -Recurse *.bat | Unblock-File`
removes Windows' "downloaded from the internet" block.

## Twitch chat
BT can read the latest messages from your live chat on request. See `docs/TWITCH.md`.

## BT's personality and spoiler gating
See `docs/BT_PERSONA.md`. BT only knows what has happened up to your current mission, and the
settings page lets you pick the mission manually until the game mod reports it.

## Status
Built and checked: settings API, key handling, event intake, mission gating (unit-tested). **Not yet tested
end to end** (needs Windows, a mic, and live keys): global hotkey, mic capture,
Whisper, Inworld voice list endpoint, playback.
