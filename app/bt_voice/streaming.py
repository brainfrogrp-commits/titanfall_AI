"""Turn a stream of text fragments into whole sentences, so speech can start
on the first sentence while the model is still writing the rest."""

import re
from typing import Iterable, Iterator

# sentence-ending punctuation, optional closing quote/bracket, then whitespace
_BOUNDARY = re.compile(r"""[.!?]+["')\]]*\s""")


def sentences(fragments: Iterable[str]) -> Iterator[str]:
    buf = ""
    for fragment in fragments:
        buf += fragment
        while True:
            match = _BOUNDARY.search(buf)
            if not match:
                break
            sentence, buf = buf[: match.end()].strip(), buf[match.end():]
            if sentence:
                yield sentence
    tail = buf.strip()
    if tail:
        yield tail
