"""Spotting slurs in chat so BT never reads them aloud.

The built-in list is stored ROT13-encoded so the source file doesn't spell the
words out. Matching is built to resist the usual evasions: capital letters,
symbols and digits standing in for letters (n!gg3r), look-alike letters from
other alphabets, accents, full-width letters, extra repeated letters, and
spaces or dots between letters. It is also built to avoid blocking innocent
words that merely contain a slur's letters, such as place names and ordinary
English words, by requiring word boundaries where that matters.

This is a safety net, not a guarantee: add anything else you want skipped to the
"never read" list on the settings page."""

import codecs
import functools
import re
import unicodedata
from typing import Iterable, List, Pattern

# word (ROT13), how the end of the word is treated, whether single separators
# between its letters count ("n i g g e r")
#   open  : anything may follow (plurals and extensions), but nothing alphabetic may precede
#   variant: endings like -s, -z, -h, but not a longer word such as an ordinary English one
#   word  : a whole word, with an optional -s or -ed
_ENTRIES = [
    ("avttre", "open", True),
    ("avttn", "variant", True),
    ("snttbg", "word", True),
    ("snt", "word", False),
    ("xvxr", "word", False),
    ("puvax", "word", False),
    ("fcvp", "word", False),
    ("tbbx", "word", False),
    ("jrgonpx", "word", True),
    ("genaal", "word", True),
    ("pbba", "word", False),
    ("cnxv", "word", False),
    ("ergneq", "word", True),
    ("ornare", "word", True),
]

# characters people use in place of letters
_LOOKALIKES = {"i": "i1!|ı", "e": "e3", "a": "a4@", "o": "o0", "s": "s5$", "t": "t7"}

# letters from other alphabets that look like Latin ones
_HOMOGLYPHS = str.maketrans({
    "а": "a", "е": "e", "о": "o", "і": "i", "ї": "i", "с": "c", "р": "p", "х": "x", "ѕ": "s",
    "ј": "j", "һ": "h", "ɡ": "g", "ı": "i", "ǀ": "l", "ո": "n",
})

_GAP = r"[^a-z0-9]?"  # at most one separator character between letters
_LEFT = r"(?<![a-z0-9])"


def normalize(text: str) -> str:
    """Lowercase, undo accents, full-width letters and look-alike alphabets, drop invisible characters."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c) and unicodedata.category(c) != "Cf")
    return re.sub(r"\s+", " ", text.lower().translate(_HOMOGLYPHS))


def _letter(ch: str) -> str:
    if ch in _LOOKALIKES:
        return "[" + re.escape(_LOOKALIKES[ch]) + "]+"
    return re.escape(ch) + "+"  # + allows stretched letters: "baaad"


def _pattern(word: str, separators: bool, ending: str) -> Pattern:
    body = (_GAP if separators else "").join(_letter(ch) for ch in word)
    tail = {"open": "", "variant": r"[szh]*(?![a-z0-9])", "word": r"(?:s|ed)?(?![a-z0-9])"}[ending]
    return re.compile(_LEFT + body + tail)


_BUILTIN: List[Pattern] = [_pattern(codecs.decode(w, "rot13"), sep, end) for w, end, sep in _ENTRIES]


def contains_slur(text: str) -> bool:
    cleaned = normalize(text or "")
    return any(p.search(cleaned) for p in _BUILTIN)


@functools.lru_cache(maxsize=256)
def _custom(phrase: str) -> Pattern:
    words = normalize(phrase).split()
    if not words:
        return re.compile(r"(?!)")  # an empty entry must match nothing, not everything
    body = r"\s+".join("".join(_letter(ch) for ch in w) for w in words)
    return re.compile(_LEFT + body + r"(?![a-z0-9])")


def matches_any(text: str, phrases: Iterable[str]) -> bool:
    """Whether the text contains any of your own blocked words (whole words, with the same
    resistance to symbols, look-alikes and stretched letters as the built-in list)."""
    cleaned = normalize(text or "")
    return any(_custom(p).search(cleaned) for p in phrases if p.strip())


def builtin_words() -> List[str]:
    """The decoded built-in list. For tests only."""
    return [codecs.decode(w, "rot13") for w, _, _ in _ENTRIES]
