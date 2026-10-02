"""Spoken conversation control: "hey BT" opens a conversation, BT then listens
to everything you say until "thanks BT", and "goodbye BT" shuts the app down.
Pure logic (no audio or network), so it can be tested directly."""

import difflib
import re
from typing import List, Optional, Tuple

FUZZY = 0.84  # how close a heard phrase must be to count (speech recognition mishears "BT")

# things speech recognition invents out of room noise or silence
NOISE = {"you", "thank you", "thanks", "bye", "okay", "ok", "the", "uh", "um", "hmm", "mm", "huh", "oh", "so",
         "thanks for watching", "thank you for watching"}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", text.lower())).strip()


def parse_phrases(setting: str) -> List[List[str]]:
    """'hey bt, hey b t' -> [['hey','bt'], ['hey','b','t']] (longest first)."""
    phrases = {tuple(normalize(p).split()) for p in (setting or "").split(",")}
    return [list(p) for p in sorted((p for p in phrases if p), key=len, reverse=True)]


def is_noise(text: str) -> bool:
    cleaned = normalize(text)
    return not cleaned or cleaned in NOISE


def _close(heard: List[str], phrase: List[str]) -> bool:
    if len(heard) != len(phrase):
        return False
    a, b = " ".join(heard), " ".join(phrase)
    return a == b or difflib.SequenceMatcher(None, a, b).ratio() >= FUZZY


def _text_after(original: str, words: List[str]) -> str:
    """The original text (punctuation intact) after the leading words."""
    target = " ".join(words)
    for i in range(1, len(original) + 1):
        if normalize(original[:i]) == target:
            return original[i:].lstrip(" ,.:;!?-").strip()
    return ""


def _text_before(original: str, words: List[str]) -> str:
    target = " ".join(words)
    for i in range(len(original), -1, -1):
        if normalize(original[i:]) == target:
            return original[:i].rstrip(" ,.:;!?-").strip()
    return ""


def match_start(text: str, phrases: List[List[str]]) -> Optional[str]:
    """If the text starts with one of the phrases, the rest of it; else None."""
    words = normalize(text).split()
    for phrase in phrases:
        if _close(words[: len(phrase)], phrase):
            return _text_after(text, words[: len(phrase)])
    return None


def match_end(text: str, phrases: List[List[str]]) -> bool:
    """True if the text ENDS with a phrase ("ok, thanks BT"), or is just the phrase,
    or starts with it followed by at most two more words ("thanks BT, bye")."""
    words = normalize(text).split()
    for phrase in phrases:
        k = len(phrase)
        if len(words) >= k and _close(words[-k:], phrase):
            return True
        if len(words) >= k and len(words) - k <= 2 and _close(words[:k], phrase):
            return True
    return False


class Conversation:
    """Tracks whether BT is currently in a conversation with the Pilot."""

    def __init__(self):
        self.active = False
        self.last_activity = 0.0  # time.monotonic()

    def touch(self, now: float) -> None:
        self.last_activity = max(self.last_activity, now)

    def reset(self) -> None:
        self.active = False

    def handle(self, text: str, cfg: dict, now: float) -> Tuple[str, str]:
        """What to do with a transcribed sentence: ('quit'|'end'|'start'|'ask'|'ignore', text)."""
        if match_end(text, parse_phrases(cfg["quit_phrases"])):
            return "quit", ""
        always_on = not cfg["wake_word_required"]
        if self.active or always_on:
            if self.active and match_end(text, parse_phrases(cfg["end_phrases"])):
                self.active = False
                return "end", ""
            if is_noise(text):
                return "ignore", text
            self.touch(now)
            return "ask", text
        rest = match_start(text, parse_phrases(cfg["wake_phrases"]))
        if rest is None:
            return "ignore", text
        self.active = True
        self.touch(now)
        return "start", rest

    def timed_out(self, now: float, cfg: dict) -> bool:
        """True once, when an open conversation has been quiet for too long."""
        limit = cfg["session_timeout_s"]
        if self.active and limit > 0 and now - self.last_activity > limit:
            self.active = False
            return True
        return False
