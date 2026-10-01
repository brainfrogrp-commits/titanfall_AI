"""Inworld TTS client. Request/response shape is the one already working in
the WoW Reading project: POST /tts/v1/voice:stream with HTTP Basic auth,
newline-delimited JSON back, base64 MP3 under result.audioContent."""

import base64
import json
import re
from typing import Iterator, List

import requests

SYNTHESIZE_PATH = "/tts/v1/voice:stream"
VOICES_PATH = "/tts/v1/voices"
MAX_CHUNK_CHARS = 250


class InworldError(RuntimeError):
    pass


_session = requests.Session()  # reused connection: skips a TLS handshake per sentence


def _headers(cfg: dict) -> dict:
    if not cfg["inworld_api_key"]:
        raise InworldError("No Inworld API key set. Add it on the settings page.")
    return {
        "Authorization": f"Basic {cfg['inworld_api_key']}",
        "Content-Type": "application/json",
    }


def split_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> List[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks, current = [], ""
    for sentence in sentences:
        if current and len(current) + len(sentence) + 1 > max_chars:
            chunks.append(current.strip())
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        chunks.append(current.strip())
    return chunks


def synthesize_chunk(cfg: dict, text: str, voice_id: str = "") -> bytes:
    voice = voice_id or cfg["inworld_voice_id"]
    if not voice:
        raise InworldError("No voice selected. Pick one on the settings page.")
    resp = _session.post(
        cfg["inworld_base_url"].rstrip("/") + SYNTHESIZE_PATH,
        headers=_headers(cfg),
        json={
            "text": text,
            "voice_id": voice,
            "audio_config": {"audio_encoding": "MP3", "speaking_rate": cfg["speaking_rate"]},
            "temperature": 1,
            "model_id": cfg["inworld_model_id"],
        },
        stream=True,
        timeout=60,
    )
    if resp.status_code != 200:
        raise InworldError(f"Inworld TTS failed ({resp.status_code}): {resp.text[:300]}")
    mp3 = bytearray()
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.strip():
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        result = parsed.get("result")
        audio = (result or {}).get("audioContent") if isinstance(result, dict) else None
        audio = audio or parsed.get("audioContent")
        if audio:
            mp3.extend(base64.b64decode(audio))
    if not mp3:
        raise InworldError("Inworld returned no audio.")
    return bytes(mp3)


def synthesize(cfg: dict, text: str, voice_id: str = "") -> Iterator[bytes]:
    for part in split_text(text):
        yield synthesize_chunk(cfg, part, voice_id)


def list_voices(cfg: dict) -> list:
    """Voices available to this account. The exact list endpoint isn't
    confirmed against live docs, so the page also accepts a typed Voice ID."""
    resp = requests.get(cfg["inworld_base_url"].rstrip("/") + VOICES_PATH, headers=_headers(cfg), timeout=20)
    if resp.status_code != 200:
        raise InworldError(f"Couldn't list voices ({resp.status_code}): {resp.text[:300]}")
    data = resp.json()
    voices = data.get("voices", data if isinstance(data, list) else [])
    out = []
    for v in voices:
        vid = v.get("voiceId") or v.get("voice_id") or v.get("name") or ""
        if vid:
            out.append({
                "id": vid,
                "name": v.get("displayName") or v.get("display_name") or vid,
                "description": v.get("description", ""),
                "languages": v.get("languages", []),
            })
    return out
