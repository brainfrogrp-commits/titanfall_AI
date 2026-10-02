# Talking to BT without SteamVR

The VR mod runs on OpenXR. OpenVR2Key (and OpenVR-InputEmulator, BVRTK) read controllers through
OpenVR/SteamVR, so they see nothing when the game runs on the Oculus or Virtual Desktop (VDXR)
OpenXR runtime. No finished tool exists that turns Quest controller buttons into keystrokes under
OpenXR, and the VR mod's DLL owns the controller input and has no rebindable talk button.

## Options, easiest first
1. **Hands-free (built in).** Settings page, Talk section: turn on "Listen for me".
   - Say **"hey BT"** (optionally followed by your question) to open a conversation. BT answers, and from
     then on he listens to everything you say, with no wake word needed each time.
   - Say **"thanks BT"** to end the conversation. BT goes back to ignoring everything except "hey BT".
   - Say **"goodbye BT"** at any time and BT says goodbye and the app closes itself.
   - A conversation that goes quiet for 2 minutes ends by itself (BT says so). Change or disable that on the page.
   - While a conversation is open, BT answers anything he hears, including you talking to other people,
     so say "thanks BT" when you are done. The phrases are editable on the page.
   - Tune **Sensitivity** with the mic meter: the red line should sit above the bar while you are
     quiet and below it when you speak.
   - Whisper runs on your CPU for every sentence it hears, so use `tiny.en` or `base.en` if the game stutters.
   - BT's own voice must not reach your mic (it would answer itself), so use the headset, not speakers.
2. **Any physical key.** The hold-to-talk key still works with anything that types a key: a USB foot
   pedal, a wireless presentation clicker, a Stream Deck, or a spare keyboard button.
3. **A custom OpenXR API layer** that watches a controller button and sends the key. This is the only
   way to get a true controller button, and it is a real C++ project that has to be tested with your
   headset. It is not built.
