# Talking to BT without SteamVR

The VR mod runs on OpenXR. OpenVR2Key (and OpenVR-InputEmulator, BVRTK) read controllers through
OpenVR/SteamVR, so they see nothing when the game runs on the Oculus or Virtual Desktop (VDXR)
OpenXR runtime. No finished tool exists that turns Quest controller buttons into keystrokes under
OpenXR, and the VR mod's DLL owns the controller input and has no rebindable talk button.

## Options, easiest first
1. **Hands-free (built in).** Settings page, Talk section: turn on "Listen for me". Say "BT, what is our
   objective?" The app listens to the Quest mic, detects speech, and answers only if you started with
   a wake word. It ignores everything else, and it does not listen while BT is speaking.
   - Tune **Sensitivity** with the mic meter: the red line should sit above the bar while you are
     quiet and below it when you speak.
   - Whisper runs on your CPU for every sentence it hears, so use the `tiny` or `base` model if the
     game stutters. Turning on "Only answer when I say a wake word" matters: without it BT answers
     everything, including you talking to other people.
2. **Any physical key.** The hold-to-talk key still works with anything that types a key: a USB foot
   pedal, a wireless presentation clicker, a Stream Deck, or a spare keyboard button.
3. **A custom OpenXR API layer** that watches a controller button and sends the key. This is the only
   way to get a true controller button, and it is a real C++ project that has to be tested with your
   headset. It is not built.
