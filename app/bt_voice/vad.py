"""Hands-free listening: detect speech on the mic, cut it into utterances,
and only act on ones addressed to BT ("BT, ..."). Needs no button, so it works
on any OpenXR runtime."""

import collections
import re
import threading
import time
from typing import List, Optional, Tuple

import numpy as np

SAMPLE_RATE = 16000
BLOCK = 1024  # about 64 ms per audio block
PREROLL_BLOCKS = 5  # keep ~0.3 s before speech starts so first syllables aren't clipped
MIN_SPEECH_S = 0.4
MAX_UTTERANCE_S = 15.0


class Segmenter:
    """Turns a stream of audio blocks into utterances using a loudness
    threshold. Pure logic, so it can be tested without a microphone."""

    def __init__(self, threshold: float, silence_s: float):
        self.threshold = threshold
        self.silence_s = silence_s
        self._preroll = collections.deque(maxlen=PREROLL_BLOCKS)
        self._buf: List[np.ndarray] = []
        self._active = False
        self._last_voice = 0.0
        self._started = 0.0

    def reset(self) -> None:
        self._preroll.clear()
        self._buf = []
        self._active = False

    def feed(self, block: np.ndarray, now: float) -> Optional[np.ndarray]:
        loud = float(np.sqrt(np.mean(block * block))) >= self.threshold
        if not self._active:
            self._preroll.append(block)
            if loud:
                self._active = True
                self._started = self._last_voice = now
                self._buf = list(self._preroll)
            return None
        self._buf.append(block)
        if loud:
            self._last_voice = now
        if now - self._last_voice >= self.silence_s or now - self._started >= MAX_UTTERANCE_S:
            speech_s = self._last_voice - self._started
            audio = np.concatenate(self._buf)
            self.reset()
            return audio if speech_s >= MIN_SPEECH_S else None
        return None


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


def parse_wake_words(setting: str) -> List[str]:
    words = [_normalize(w) for w in (setting or "").split(",")]
    return sorted({w for w in words if w}, key=len, reverse=True)  # longest first


def _after_prefix(original: str, normalized_prefix: str) -> str:
    """The original text after the words that normalize to the wake word,
    so punctuation like apostrophes in the question survives."""
    for i in range(1, len(original) + 1):
        if _normalize(original[:i]) == normalized_prefix:
            return original[i:].lstrip(" ,.:;!?-").strip()
    return ""


def extract_question(transcript: str, wake_words: List[str], wake_required: bool) -> Tuple[bool, str]:
    """Returns (addressed_to_bt, what_to_answer). With a wake word required,
    only transcripts that START with it count, and the wake word is removed."""
    cleaned = _normalize(transcript)
    if not cleaned:
        return False, ""
    if not wake_required:
        return True, transcript.strip()
    for word in wake_words:
        if cleaned == word or cleaned.startswith(word + " "):
            rest = _after_prefix(transcript, word)
            return True, rest or "The Pilot is getting your attention."
    return False, ""


class VoiceListener:
    def __init__(self, engine):
        self.engine = engine
        self.level = 0.0
        self.running = False
        self.error = ""
        self._stream = None
        self._seg: Optional[Segmenter] = None
        self._cfg = {}
        self._cfg_at = 0.0
        self._pending: "collections.deque" = collections.deque(maxlen=3)
        self._wake = threading.Event()
        self._worker: Optional[threading.Thread] = None

    def apply(self, cfg: dict) -> None:
        if cfg["handsfree_enabled"] and not self.running:
            self.start()
        elif not cfg["handsfree_enabled"] and self.running:
            self.stop()

    def start(self) -> None:
        try:
            import sounddevice as sd

            self._refresh_cfg(force=True)
            self._seg = Segmenter(self._cfg["vad_threshold"], self._cfg["vad_silence_s"])
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="float32", blocksize=BLOCK, callback=self._callback
            )
            self._stream.start()
            self.running, self.error = True, ""
            self._worker = threading.Thread(target=self._work, daemon=True)
            self._worker.start()
            self.engine.note("info", "Hands-free listening on. Say 'BT, ...' to talk.")
        except Exception as e:
            self.running, self.error = False, f"Hands-free mic error: {e}"
            self.engine.note("error", self.error)

    def stop(self) -> None:
        self.running = False
        self._wake.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self.level = 0.0
        self.engine.note("info", "Hands-free listening off.")

    def _refresh_cfg(self, force: bool = False) -> None:
        from bt_voice import config

        if force or time.monotonic() - self._cfg_at > 2.0:
            self._cfg = config.load()
            self._cfg_at = time.monotonic()
            if self._seg:
                self._seg.threshold = self._cfg["vad_threshold"]
                self._seg.silence_s = self._cfg["vad_silence_s"]

    def _callback(self, indata, frames, time_info, status) -> None:
        block = indata[:, 0].copy()
        self.level = float(np.sqrt(np.mean(block * block)))
        self._refresh_cfg()
        now = time.monotonic()
        # don't listen while BT is thinking or talking (his own voice leaks into the mic)
        if self.engine.is_busy() or now - self.engine.last_done < 0.8:
            self._seg.reset()
            return
        audio = self._seg.feed(block, now)
        if audio is not None:
            self._pending.append(audio)
            self._wake.set()

    def _work(self) -> None:
        while self.running:
            self._wake.wait(timeout=1.0)
            self._wake.clear()
            while self._pending and self.running:
                audio = self._pending.popleft()
                try:
                    self._handle(audio)
                except Exception as e:
                    self.engine.note("error", f"Listening error: {e}")

    def _handle(self, audio: np.ndarray) -> None:
        from bt_voice import speech_io

        cfg = self._cfg
        started = time.monotonic()
        text = speech_io.transcribe(audio, cfg["whisper_model_size"])
        stt_s = time.monotonic() - started
        if not text:
            return
        addressed, question = extract_question(
            text, parse_wake_words(cfg["wake_words"]), cfg["wake_word_required"]
        )
        if not addressed:
            self.engine.note("info", f'Heard "{text}" (not addressed to BT, ignored)')
            return
        self.engine.hear(question, stt_s)
