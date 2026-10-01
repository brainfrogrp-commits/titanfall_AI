# BT-7274 Voice (Titanfall 2 VR)

Talk to BT in Titanfall 2 VR. Hold a key, speak, and BT answers in a voice from
Inworld. BT can also comment on what you're doing in game.

This is a companion app that runs next to the game. It does not modify
CircuitLord's Titanfall 2 VR mod.

## Run (Windows)
1. Install Python 3.10+.
2. Double-click `app/run.bat`. First run installs dependencies (and downloads a
   small speech model on your first question).
3. The settings page opens at http://127.0.0.1:5757. Enter your **Inworld** and
   **OpenRouter** keys, pick a voice, press **Set key** to choose the talk key,
   then **Save settings**.
4. Start the game in VR as usual. Map a controller button to the same key with
   OpenVR2Key. Hold it, speak, release.

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

## Status
Built and checked: settings API, key handling, event intake. **Not yet tested
end to end** (needs Windows, a mic, and live keys): global hotkey, mic capture,
Whisper, Inworld voice list endpoint, playback.
