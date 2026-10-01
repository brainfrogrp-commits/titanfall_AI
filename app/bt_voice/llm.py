"""OpenRouter chat completions (OpenAI-compatible)."""

from typing import List

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class LlmError(RuntimeError):
    pass


def chat(cfg: dict, messages: List[dict], max_tokens: int = 200) -> str:
    if not cfg["openrouter_api_key"]:
        raise LlmError("No OpenRouter API key set. Add it on the settings page.")
    resp = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {cfg['openrouter_api_key']}",
            "Content-Type": "application/json",
        },
        json={"model": cfg["openrouter_model"], "messages": messages, "max_tokens": max_tokens},
        timeout=30,
    )
    if resp.status_code != 200:
        raise LlmError(f"OpenRouter failed ({resp.status_code}): {resp.text[:300]}")
    try:
        return resp.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as e:
        raise LlmError(f"Unexpected OpenRouter response: {resp.text[:300]}") from e
