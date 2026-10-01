"""Local web UI + API. Bound to 127.0.0.1 only; API keys never leave this PC
except to Inworld/OpenRouter."""

import logging
import threading

from flask import Flask, jsonify, request, send_from_directory

from bt_voice import config, inworld, lore
from bt_voice.bt import engine, hotkey

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
app = Flask(__name__, static_folder="web", static_url_path="")


@app.get("/")
def index():
    return send_from_directory("web", "index.html")


@app.get("/api/config")
def get_config():
    return jsonify(config.public_view(config.load()))


@app.post("/api/config")
def set_config():
    before = config.load()
    cfg = config.update(request.get_json(force=True) or {})
    if cfg["hotkey"] != before["hotkey"] or hotkey.key is None:
        hotkey.bind(cfg["hotkey"])
    return jsonify(config.public_view(cfg))


@app.get("/api/voices")
def voices():
    try:
        return jsonify({"voices": inworld.list_voices(config.load())})
    except Exception as e:
        return jsonify({"voices": [], "error": str(e)}), 200


@app.post("/api/preview")
def preview():
    body = request.get_json(force=True) or {}
    voice = body.get("voice_id", "")
    text = body.get("text") or "Pilot, this is my voice. Protocol three: protect the pilot."

    def run():
        try:
            engine.speak(config.load(), text, voice)
        except Exception as e:
            engine.note("error", str(e))
        finally:
            engine.status = "idle"

    threading.Thread(target=run, daemon=True).start()
    return jsonify(ok=True)


@app.post("/api/ask")
def ask():
    question = (request.get_json(force=True) or {}).get("text", "").strip()
    if not question:
        return jsonify(ok=False, error="empty"), 400
    engine.ask_text(question)
    return jsonify(ok=True)


@app.post("/api/event")
def event():
    """Game mod posts here: {"type": "embark", "text": "Pilot embarked BT", "data": {...}}"""
    body = request.get_json(force=True, silent=True) or {}
    if not body.get("type") and not body.get("text"):
        return jsonify(ok=False, error="need type or text"), 400
    return jsonify(ok=True, commenting=engine.game_event(body))


@app.get("/api/chapters")
def chapters():
    cid = engine.chapter_id()
    return jsonify(
        chapters=lore.chapters_summary(),
        mode=config.load()["chapter_mode"],
        detected=engine.detected_chapter,
        active=cid,
        active_name=lore.CHAPTER_BY_ID[cid]["name"] if cid in lore.CHAPTER_BY_ID else None,
    )


@app.get("/api/status")
def status():
    return jsonify(
        status=engine.status,
        hotkey=hotkey.key,
        hotkey_error=hotkey.error,
        context=engine.context.describe(),
        log=list(engine.log),
    )


if __name__ == "__main__":
    hotkey.bind(config.load()["hotkey"])
    print("BT-7274 voice companion: open http://127.0.0.1:5757")
    app.run(host="127.0.0.1", port=5757, threaded=True)
