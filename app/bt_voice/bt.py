"""The BT-7274 engine: push-to-talk -> speech-to-text -> LLM -> Inworld voice,
plus game awareness so BT knows what is happening and can comment unprompted."""

import collections
import logging
import threading
import time
from typing import Optional, Tuple

from bt_voice import config, inworld, llm, lore, pipeline, speech_io, streaming

log = logging.getLogger("bt")

# Event types BT is allowed to react to unprompted. Anything else is just
# recorded as context.
NOTABLE_EVENTS = {"embark", "disembark", "map_change", "objective", "low_health", "boss", "death", "kill_streak"}

# Friendly names for common weapon class names; others are tidied automatically.
WEAPON_NAMES = {
    "mp_weapon_rspn101": "R-201 Carbine", "mp_weapon_rspn101_og": "R-101C Carbine", "mp_weapon_car": "CAR SMG",
    "mp_weapon_hemlok": "Hemlok", "mp_weapon_vinson": "Flatline", "mp_weapon_g2": "G2A5",
    "mp_weapon_lmg": "Spitfire", "mp_weapon_shotgun": "EVA-8", "mp_weapon_mastiff": "Mastiff",
    "mp_weapon_sniper": "Kraber", "mp_weapon_dmr": "Longbow DMR", "mp_weapon_wingman": "Wingman",
    "mp_weapon_semipistol": "P2016", "mp_weapon_autopistol": "RE-45", "mp_weapon_smart_pistol": "Smart Pistol",
    "mp_weapon_softball": "Softball", "mp_weapon_rocket_launcher": "Archer", "mp_weapon_defender": "Charge Rifle",
    "mp_weapon_alternator_smg": "Alternator", "mp_weapon_epg": "EPG", "mp_weapon_pulse_lmg": "Devotion",
    "mp_weapon_frag_grenade": "frag grenade", "mp_weapon_thermite_grenade": "thermite grenade",
    "mp_weapon_grenade_emp": "arc grenade", "mp_weapon_grenade_gravity": "gravity star",
    "mp_weapon_grenade_electric_smoke": "electric smoke", "mp_weapon_grenade_sonar": "pulse blade",
    "tf2vr_empty_hands": "nothing (empty hands)",
}


def weapon_name(class_name: str) -> str:
    if class_name in WEAPON_NAMES:
        return WEAPON_NAMES[class_name]
    name = class_name
    for prefix in ("mp_titanweapon_", "mp_weapon_", "melee_"):
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name.replace("_", " ")


def describe_state(state: dict) -> list:
    """The latest sensor readings as plain sentences for the model."""
    lines = []
    if "in_titan" in state:
        if state["in_titan"]:
            lines.append("The Pilot is embarked in you, piloting you as a Titan.")
        else:
            distance = state.get("bt_distance_m", -1)
            where = f", and you are about {distance} meters away" if isinstance(distance, int) and distance >= 0 else ""
            lines.append(f"The Pilot is on foot, outside the Titan{where}.")
    place = state.get("location")
    if place:
        lines.append({
            "indoors": "The Pilot is indoors, with solid cover overhead.",
            "under cover": "The Pilot is under partial overhead cover.",
            "outdoors": "The Pilot is outdoors, with open sky overhead.",
        }.get(place, f"Location: {place}."))
    if "health_pct" in state:
        lines.append(f"The Pilot's health is about {state['health_pct']} percent.")
    if "bt_health_pct" in state and state.get("bt_health_pct", -1) >= 0:
        lines.append(f"Your own health is about {state['bt_health_pct']} percent.")
    if state.get("weapon"):
        lines.append(f"The Pilot is holding: {weapon_name(state['weapon'])}.")
    if "enemies_near" in state:
        n, t = state["enemies_near"], state.get("enemy_titans_near", 0)
        if n == 0:
            lines.append("No enemies are detected nearby.")
        else:
            lines.append(f"Enemies detected nearby: {n}" + (f", including {t} Titan{'s' if t != 1 else ''}." if t else "."))
    if state.get("action") and state["action"] != "standing":
        lines.append(f"The Pilot is currently {state['action']}.")
    known = {"in_titan", "bt_distance_m", "location", "health_pct", "bt_health_pct", "weapon",
             "enemies_near", "enemy_titans_near", "action", "map"}
    lines += [f"{k}: {v}" for k, v in state.items() if k not in known]
    return lines


class GameContext:
    def __init__(self, keep: int = 25):
        self.events = collections.deque(maxlen=keep)
        self.state = {}
        self.state_t = 0.0

    def add(self, event: dict) -> None:
        now = time.time()
        if isinstance(event.get("data"), dict):
            self.state.update(event["data"])
            self.state_t = now
        if event.get("type") == "state":
            return  # frequent sensor snapshots update the state but don't flood the event list
        self.events.append(dict(event, t=now))

    def describe(self) -> str:
        now = time.time()
        lines = describe_state(self.state)
        if lines and now - self.state_t > 20:
            lines.append(f"(These readings are {int(now - self.state_t)} seconds old.)")
        for e in list(self.events)[-12:]:
            lines.append(f"- {int(now - e['t'])}s ago: {e.get('text') or e.get('type')}")
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
        self.detected_chapter = None  # chapter id last seen from the game's map name
        self.last_done = 0.0  # monotonic time the last request finished
        self.last_event_t = 0.0  # wall time of the last message from the game
        self._seen_sensor_errors = set()

    def chapter_id(self, cfg: dict = None):
        """Chapter BT's knowledge is gated to: the manual choice, else the
        last mission detected from the game, else None (unknown)."""
        mode = (cfg or config.load())["chapter_mode"]
        return self.detected_chapter if mode == "auto" else mode

    def game_connected_seconds(self) -> Optional[int]:
        """Seconds since the game last sent anything, or None if it never has."""
        return int(time.time() - self.last_event_t) if self.last_event_t else None

    # --- logging for the web page ---
    def note(self, kind: str, text: str) -> None:
        self.log.append({"t": time.time(), "kind": kind, "text": text})
        log.info("%s: %s", kind, text)

    # --- core pipeline ---
    def _system(self, cfg: dict, proactive: bool = False) -> str:
        return lore.build_system_prompt(
            self.chapter_id(cfg), self.context.describe(), cfg["persona_extra"], proactive
        )

    def speak(self, cfg: dict, text: str, voice_id: str = "") -> None:
        self.status = "speaking"
        pipeline.speak(cfg, iter(inworld.split_text(text)), voice_id)

    def _stream_reply(self, cfg: dict, messages: list, max_tokens: int, allow_skip: bool = False
                      ) -> Tuple[Optional[str], dict]:
        """Streams the model's reply and starts speaking at the first sentence.
        Returns (reply, timings); reply is None if BT chose to stay silent."""
        t0 = time.monotonic()
        marks = {}
        parts = []
        skipped = []

        def fragments():
            for fragment in llm.chat_stream(cfg, messages, max_tokens):
                marks.setdefault("first_words", time.monotonic() - t0)
                parts.append(fragment)
                yield fragment

        def sentences():
            first = True
            for sentence in streaming.sentences(fragments()):
                if first and allow_skip and sentence.upper().startswith("SKIP"):
                    skipped.append(True)
                    return
                first = False
                yield sentence

        def audio_started():
            marks.setdefault("first_audio", time.monotonic() - t0)
            self.status = "speaking"

        pipeline.speak(cfg, sentences(), "", on_first_audio=audio_started)
        return (None if skipped else "".join(parts).strip()), marks

    def _note_timing(self, marks: dict, stt_s: Optional[float]) -> None:
        bits = []
        if stt_s is not None:
            bits.append(f"speech recognition {stt_s:.1f}s")
        if "first_words" in marks:
            bits.append(f"model's first words {marks['first_words']:.1f}s")
        if "first_audio" in marks:
            bits.append(f"first sound {marks['first_audio']:.1f}s after the question was understood")
        if bits:
            self.note("info", "Speed: " + ", ".join(bits))

    def respond(self, question: str, stt_s: Optional[float] = None) -> Optional[str]:
        cfg = config.load()
        messages = [{"role": "system", "content": self._system(cfg)}]
        for user_text, bt_text in self.history:
            messages += [{"role": "user", "content": user_text}, {"role": "assistant", "content": bt_text}]
        messages.append({"role": "user", "content": question})
        self.status = "thinking"
        reply, marks = self._stream_reply(cfg, messages, 200)
        if reply:
            self.history.append((question, reply))
            self.note("bt", reply)
        self._note_timing(marks, stt_s)
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
            self.last_done = time.monotonic()
            self._busy.release()

    def is_busy(self) -> bool:
        return self._busy.locked()

    def hear(self, question: str, stt_s: Optional[float] = None) -> None:
        """A question picked up by hands-free listening (already transcribed)."""
        self.ask_text(question, stt_s)

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
        started = time.monotonic()
        question = speech_io.transcribe(audio, cfg["whisper_model_size"])
        stt_s = time.monotonic() - started
        if not question:
            self.note("info", "Didn't catch anything.")
            return
        self.note("you", question)
        self.respond(question, stt_s)

    def ask_text(self, question: str, stt_s: Optional[float] = None) -> None:
        """Same pipeline without the mic, for testing from the web page."""
        self.note("you", question)
        threading.Thread(target=self._run_guarded, args=(self.respond, question, stt_s), daemon=True).start()

    # --- game events ---
    def game_event(self, event: dict) -> bool:
        """Records an event; returns True if BT will comment on it."""
        self.last_event_t = time.time()
        data = dict(event.get("data") or {})
        for err in data.pop("sensor_errors", []):  # the game mod reports sensors that failed
            if err not in self._seen_sensor_errors:
                self._seen_sensor_errors.add(err)
                self.note("error", f"Game sensor problem: {err}")
        event["data"] = data
        self.context.add(event)
        cfg = config.load()
        entered = lore.chapter_for_map(data.get("map", ""))
        if entered and entered != self.detected_chapter:
            self.detected_chapter = entered
            name = lore.CHAPTER_BY_ID[entered]["name"]
            self.note("info", f"Mission detected: {name}")
            event["type"] = "map_change"  # whatever message first revealed the mission, this is what happened
            event["text"] = f"The Pilot has arrived at the mission: {name}."
            event["comment"] = True
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
            + ". Decide whether BT would speak. If so, make one brief spoken remark to your Pilot, in character."
        )
        self.status = "thinking"
        reply, marks = self._stream_reply(cfg, [
            {"role": "system", "content": self._system(cfg, proactive=True)},
            {"role": "user", "content": prompt},
        ], 120, allow_skip=True)
        if reply is None:
            self.note("info", f"BT stayed quiet about: {event.get('text') or event.get('type')}")
            return
        self.note("bt", reply)
        self._note_timing(marks, None)


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
