"""Is Titanfall 2 running? Lets the app tell "the game is not running" apart from
"the game is running but sending nothing" (a problem with the sensor mod)."""

import os
import subprocess
import time
from typing import Optional

_NAMES = ("titanfall2.exe", "titanfall2vrlauncher.exe")
_cache = {"at": 0.0, "value": None}


def game_running() -> Optional[bool]:
    """True/False on Windows; None where we can't tell. Cached for a few seconds."""
    if os.name != "nt":
        return None
    now = time.monotonic()
    if now - _cache["at"] < 5.0:
        return _cache["value"]
    try:
        out = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=5,
            creationflags=0x08000000,  # CREATE_NO_WINDOW: no console flash
        ).stdout.lower()
        value = any(name in out for name in _NAMES)
    except Exception:
        value = None
    _cache.update(at=now, value=value)
    return value
