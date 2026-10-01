"""Persistent settings, stored in the user's home folder (never in the repo)
so API keys can't be committed by accident."""

import json
import os
import threading
from pathlib import Path

CONFIG_DIR = Path(os.path.expanduser("~/.titanfall_bt"))
CONFIG_PATH = CONFIG_DIR / "config.json"

SECRET_FIELDS = ("inworld_api_key", "openrouter_api_key")

DEFAULTS = {
    "inworld_api_key": "",
    "inworld_voice_id": "",
    "inworld_model_id": "inworld-tts-1.5-max",
    "inworld_base_url": "https://api.inworld.ai",
    "speaking_rate": 1.0,
    "openrouter_api_key": "",
    "openrouter_model": "anthropic/claude-haiku-4.5",
    "whisper_model_size": "base",
    "hotkey": "f9",
    "volume": 1.0,
    "proactive_enabled": True,
    "proactive_cooldown_s": 45,
    "persona_extra": "",
}

_lock = threading.Lock()


def load() -> dict:
    cfg = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            cfg.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pass
    return cfg


def update(changes: dict) -> dict:
    """Merges known fields into the saved config. A blank secret means
    'leave the saved key alone', so the page never has to echo keys back."""
    with _lock:
        cfg = load()
        for key, value in changes.items():
            if key not in DEFAULTS:
                continue
            if key in SECRET_FIELDS and not value:
                continue
            cfg[key] = type(DEFAULTS[key])(value) if not isinstance(DEFAULTS[key], bool) else bool(value)
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return cfg


def public_view(cfg: dict) -> dict:
    """Config safe to send to the browser: secrets become has_* booleans."""
    out = {k: v for k, v in cfg.items() if k not in SECRET_FIELDS}
    for k in SECRET_FIELDS:
        out["has_" + k] = bool(cfg.get(k))
    return out
