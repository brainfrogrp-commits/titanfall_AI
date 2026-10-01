"""The BT-7274 engine: push-to-talk -> speech-to-text -> LLM -> Inworld voice,
plus game-event awareness so BT can comment unprompted."""

import collections
import logging
import threading
import time
from typing import Optional

from bt_voice import config, inworld, llm, speech_io

log = logging.getLogger("bt")

PERSONA = (
    "You are BT-7274, a Vanguard-class Titan, speaking out loud to your Pilot "
    "in Titanfall 2. You are loyal, literal-minded and dry. You speak in short, "
    "plain, precise sentences, address the player as 'Pilot', and occasionally "
    "misread an idiom with perfect sincerity. You value the mission and your "
    "Pilot's survival, and you say 'Trust me' only when it matters. "
    "Reply in 1 to 3 short sentences, suitable for being spoken aloud: no "
    "markdown, no lists, no stage directions. Only mention what you actually "
    "know from the game context below; if you don't know, say so plainly. "
    "Never invent mission details."
)

# Event types BT is allowed to react to unprompted. Anything else is just
# recorded as context.
NOTABLE_EVENTS = {"embark", "disembark", "map_change", "objective", "low_health", "boss", "death", "kill_streak"}


class GameContext:
    def __init__(self, keep: int = 25):
        self.events = collections.deque(maxlen=keep)
        self.state = {}

    def add(self, event: dict) -> None:
        event = dict(event, t=time.time())
        self.events.append(event)
        if isinstance(event.get("data"), dict):
            self.state.update(event["data"])

    def describe(self) -> str:
        now = time.time()
        lines = []
        if self.state:
            lines.append("Current state: " + ", ".join(f"{k}={v}" for k, v in self.state.items()))
        for e in list(self.events)[-12:]:
            ago = int(now - e["t"])
            lines.append(f"- {ago}s ago: {e.get('text') or e.get('type')}")
        return "\n".join(lines) if lines else "(no game data received yet)"


class Engine:
    def __init__(self):
        self.context = GameContext()
        self.history = collections.deque(maxlen=8)  # recent (user, bt) turns
        self.log = collections.deque(maxlen=60)
        self.mic = speech_io.MicRecorder()
        self._busy = threading.Lock()
        self._last_comment = 0.0
        self.status = "idle"

    # --- logging for the web page ---
    def note(self, kind: str, text: str) -> None:
        self.log.append({"t": time.time(), "kind": kind, "text": text})
        log.info("%s: %s", kind, text)

    # --- core pipeline ---
    def _system(self, cfg: dict, extra: str = "") -> str:
        parts = [PERSONA]
        if cfg["persona_extra"]:
            parts.append(cfg["persona_extra"])
        parts.append("Game context:\n" + self.context.describe())
        if extra:
            parts.append(extra)
        return "\n\n".join(parts)

    def speak(self, cfg: dict, text: str, voice_id: str = "") -> None:
        self.status = "speaking"
        for mp3 in inworld.synthesize(cfg, text, voice_id):
            speech_io.play_mp3(mp3, cfg["volume"])

    def respond(self, question: str) -> str:
        cfg = config.load()
        messages = [{"role": "system", "content": self._system(cfg)}]
        for user_text, bt_text in self.history:
            messages += [{"role": "user", "content": user_text}, {"role": "assistant", "content": bt_text}]
        messages.append({"role": "user", "content": question})
        reply = llm.chat(cfg, messages)
        self.history.append((question, reply))
        self.note("bt", reply)
        self.speak(cfg, reply)
        return reply

    def _run_guarded(self, fn, *args) -> None:
        if not self._busy.acquire(blocking=False):
            self.note("info", "Still busy with the last request.")
            return
        try:
            fn(*args)
        except Exception as e:  # surface every failure on the page
            self.note("error", str(e))
        finally:
            self.status = "idle"
            self._busy.release()

    # --- push to talk ---
    def ptt_press(self) -> None:
        if self.mic.is_recording or self._busy.locked():
            return
        try:
            self.mic.start()
            self.status = "listening"
        except Exception as e:
            self.note("error", f"Mic error: {e}")

    def ptt_release(self) -> None:
        if not self.mic.is_recording:
            return
        audio = self.mic.stop()
        self.status = "thinking"
        threading.Thread(target=self._run_guarded, args=(self._handle_audio, audio), daemon=True).start()

    def _handle_audio(self, audio) -> None:
        cfg = config.load()
        question = speech_io.transcribe(audio, cfg["whisper_model_size"])
        if not question:
            self.note("info", "Didn't catch anything.")
            return
        self.note("you", question)
        self.respond(question)

    def ask_text(self, question: str) -> None:
        """Same pipeline without the mic, for testing from the web page."""
        self.note("you", question)
        threading.Thread(target=self._run_guarded, args=(self.respond, question), daemon=True).start()

    # --- game events ---
    def game_event(self, event: dict) -> bool:
        """Records an event; returns True if BT will comment on it."""
        self.context.add(event)
        cfg = config.load()
        notable = event.get("type") in NOTABLE_EVENTS or event.get("comment")
        now = time.time()
        if not (cfg["proactive_enabled"] and notable and not self._busy.locked()
                and now - self._last_comment >= cfg["proactive_cooldown_s"]):
            return False
        self._last_comment = now
        threading.Thread(target=self._run_guarded, args=(self._comment, event), daemon=True).start()
        return True

    def _comment(self, event: dict) -> None:
        cfg = config.load()
        prompt = (
            "Something just happened: " + (event.get("text") or event.get("type", "an event"))
            + ". Make one brief spoken remark to your Pilot about it, in character."
        )
        reply = llm.chat(cfg, [
            {"role": "system", "content": self._system(cfg)},
            {"role": "user", "content": prompt},
        ], max_tokens=120)
        self.note("bt", reply)
        self.speak(cfg, reply)


engine = Engine()


class Hotkey:
    """Global hold-to-talk key. OpenVR2Key (or any keyboard) just has to
    produce this key press."""

    def __init__(self, eng: Engine):
        self.engine = eng
        self._handles = []
        self.key: Optional[str] = None
        self.error = ""

    def bind(self, key: str) -> None:
        self.unbind()
        try:
            import keyboard

            self._handles = [
                keyboard.on_press_key(key, lambda e: self.engine.ptt_press()),
                keyboard.on_release_key(key, lambda e: self.engine.ptt_release()),
            ]
            self.key, self.error = key, ""
        except Exception as e:
            self.key, self.error = None, f"Couldn't bind '{key}': {e}"
            self.engine.note("error", self.error)

    def unbind(self) -> None:
        try:
            import keyboard

            for h in self._handles:
                keyboard.unhook(h)
        except Exception:
            pass
        self._handles = []


hotkey = Hotkey(engine)
