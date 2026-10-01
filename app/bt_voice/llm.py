"""OpenRouter chat completions (OpenAI-compatible)."""

import json
from typing import Iterator, List

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class LlmError(RuntimeError):
    pass


# one shared connection pool: reusing the TLS connection saves a handshake per request
_session = requests.Session()


def _headers(cfg: dict) -> dict:
    if not cfg["openrouter_api_key"]:
        raise LlmError("No OpenRouter API key set. Add it on the settings page.")
    return {
        "Authorization": f"Bearer {cfg['openrouter_api_key']}",
        "Content-Type": "application/json",
    }


def chat(cfg: dict, messages: List[dict], max_tokens: int = 200) -> str:
    resp = _session.post(
        OPENROUTER_URL,
        headers=_headers(cfg),
        json={"model": cfg["openrouter_model"], "messages": messages, "max_tokens": max_tokens},
        timeout=30,
    )
    if resp.status_code != 200:
        raise LlmError(f"OpenRouter failed ({resp.status_code}): {resp.text[:300]}")
    try:
        return resp.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as e:
        raise LlmError(f"Unexpected OpenRouter response: {resp.text[:300]}") from e


def chat_stream(cfg: dict, messages: List[dict], max_tokens: int = 200) -> Iterator[str]:
    """Yields the reply in small fragments as the model writes it."""
    resp = _session.post(
        OPENROUTER_URL,
        headers=_headers(cfg),
        json={"model": cfg["openrouter_model"], "messages": messages, "max_tokens": max_tokens, "stream": True},
        stream=True,
        timeout=30,
    )
    if resp.status_code != 200:
        raise LlmError(f"OpenRouter failed ({resp.status_code}): {resp.text[:300]}")
    resp.encoding = "utf-8"  # event streams carry no charset; the default would garble dashes and accents
    try:
        for line in resp.iter_lines(decode_unicode=True):
            if not line or line.startswith(":"):  # blank lines and keep-alive comments
                continue
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload == "[DONE]":
                break
            try:
                event = json.loads(payload)
            except ValueError:
                continue
            if "error" in event:
                raise LlmError(f"OpenRouter error: {str(event['error'])[:300]}")
            choices = event.get("choices") or [{}]
            text = (choices[0].get("delta") or {}).get("content")
            if text:
                yield text
    finally:
        resp.close()
