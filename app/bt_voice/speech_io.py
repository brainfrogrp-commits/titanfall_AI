"""Mic capture, local speech-to-text and audio playback. Heavy audio
libraries are imported lazily so the settings page still opens (and can
report a clear error) if one isn't installed."""

import threading

SAMPLE_RATE = 16000  # what Whisper expects


class MicRecorder:
    def __init__(self):
        self._frames = []
        self._stream = None

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    def start(self) -> None:
        import sounddevice as sd

        if self._stream is not None:
            return
        self._frames = []
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32",
            callback=lambda indata, frames, t, status: self._frames.append(indata.copy()),
        )
        self._stream.start()

    def stop(self):
        import numpy as np

        if self._stream is None:
            return np.zeros(0, dtype="float32")
        self._stream.stop()
        self._stream.close()
        self._stream = None
        if not self._frames:
            return np.zeros(0, dtype="float32")
        return np.concatenate(self._frames, axis=0).flatten()


_whisper = {}
_whisper_lock = threading.Lock()


# words the model should expect, so "BT" and the game's names are heard correctly
VOCAB_HINT = "BT, BT-7274, Pilot, Cooper, Titan, Typhon, IMC, Militia, Apex Predators."


def _model(model_size: str):
    if model_size not in _whisper:
        from faster_whisper import WhisperModel

        _whisper[model_size] = WhisperModel(model_size, device="cpu", compute_type="int8")
    return _whisper[model_size]


def preload(model_size: str) -> None:
    """Load (and download, the first time) the speech model ahead of the first question."""
    with _whisper_lock:
        _model(model_size)


def transcribe(audio, model_size: str) -> str:
    if audio.size == 0:
        return ""
    with _whisper_lock:
        segments, _ = _model(model_size).transcribe(
            audio, language="en", beam_size=1, condition_on_previous_text=False, initial_prompt=VOCAB_HINT
        )
        return " ".join(s.text.strip() for s in segments).strip()


def play_mp3(mp3_data: bytes, volume: float = 1.0) -> None:
    import miniaudio
    import numpy as np
    import sounddevice as sd

    decoded = miniaudio.decode(mp3_data)
    samples = np.frombuffer(decoded.samples, dtype=np.int16)
    if volume != 1.0:
        samples = np.clip(samples.astype(np.float32) * volume, -32768, 32767).astype(np.int16)
    if decoded.nchannels > 1:
        samples = samples.reshape(-1, decoded.nchannels)
    sd.play(samples, decoded.sample_rate)
    sd.wait()
