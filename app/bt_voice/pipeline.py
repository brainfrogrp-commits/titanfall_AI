"""Speak a stream of sentences with overlap: while one sentence plays, the
next is already being synthesized, so there are no gaps between them."""

import queue
import threading
from typing import Callable, Iterable, Optional

from bt_voice import inworld, speech_io


def speak(cfg: dict, sentence_iter: Iterable[str], voice_id: str = "",
          on_first_audio: Optional[Callable[[], None]] = None) -> None:
    ready: "queue.Queue" = queue.Queue(maxsize=2)  # bounded, so we don't synthesize far ahead
    stop = threading.Event()

    def produce() -> None:
        try:
            for sentence in sentence_iter:
                for part in inworld.split_text(sentence):
                    if stop.is_set():
                        return
                    ready.put(("audio", inworld.synthesize_chunk(cfg, part, voice_id)))
        except Exception as e:
            ready.put(("error", e))
        finally:
            ready.put(("done", None))

    threading.Thread(target=produce, daemon=True).start()
    failure = None
    first = True
    try:
        while True:
            kind, value = ready.get()
            if kind == "done":
                break
            if kind == "error":
                failure = value
                continue  # keep draining until "done"
            if first and on_first_audio:
                on_first_audio()
            first = False
            speech_io.play_mp3(value, cfg["volume"])
    finally:
        stop.set()
        while not ready.empty():  # unblock the producer if we left early
            try:
                ready.get_nowait()
            except queue.Empty:
                break
    if failure is not None:
        raise failure
