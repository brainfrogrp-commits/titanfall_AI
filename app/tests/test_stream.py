"""Run with:  python -m unittest discover -s tests   (from the app folder)"""

import os
import sys
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bt_voice import bt, config, llm, pipeline, streaming  # noqa: E402

CFG = dict(config.DEFAULTS, volume=1.0)


class Sentences(unittest.TestCase):
    def test_splits_across_fragment_boundaries(self):
        out = list(streaming.sentences(["Hello", " there.", " I am", " BT. Next", " one"]))
        self.assertEqual(out, ["Hello there.", "I am BT.", "Next one"])

    def test_decimals_are_not_sentence_ends(self):
        self.assertEqual(list(streaming.sentences(["Version 3.5 is ok", ". Yes."])), ["Version 3.5 is ok.", "Yes."])

    def test_no_final_punctuation_still_emitted(self):
        self.assertEqual(list(streaming.sentences(["SKIP"])), ["SKIP"])

    def test_closing_quote_stays_with_sentence(self):
        self.assertEqual(list(streaming.sentences(['He said "go." Then left.'])), ['He said "go."', "Then left."])


class FakeResponse:
    def __init__(self, lines, status=200):
        self.status_code, self._lines, self.closed, self.encoding = status, lines, False, None
        self.text = ""

    def iter_lines(self, decode_unicode=True):
        return iter(self._lines)

    def close(self):
        self.closed = True


class StreamParsing(unittest.TestCase):
    def run_stream(self, lines):
        resp = FakeResponse(lines)
        with mock.patch.object(llm._session, "post", return_value=resp):
            return list(llm.chat_stream(CFG | {"openrouter_api_key": "k"}, [])), resp

    def test_collects_deltas_and_ignores_noise(self):
        out, resp = self.run_stream([
            ": OPENROUTER PROCESSING", "",
            'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            'data: {"choices":[{"delta":{"role":"assistant"}}]}',
            'data: {"choices":[{"delta":{"content":" Pilot."}}]}',
            "data: [DONE]",
            'data: {"choices":[{"delta":{"content":"IGNORED"}}]}',
        ])
        self.assertEqual(out, ["Hello", " Pilot."])
        self.assertEqual(resp.encoding, "utf-8")
        self.assertTrue(resp.closed)

    def test_error_event_raises(self):
        with self.assertRaises(llm.LlmError):
            self.run_stream(['data: {"error":{"message":"rate limited"}}'])

    def test_response_closed_when_reader_stops_early(self):
        resp = FakeResponse(['data: {"choices":[{"delta":{"content":"a"}}]}'] * 5)
        with mock.patch.object(llm._session, "post", return_value=resp):
            gen = llm.chat_stream(CFG | {"openrouter_api_key": "k"}, [])
            next(gen)
            gen.close()
        self.assertTrue(resp.closed)


class Pipeline(unittest.TestCase):
    def test_plays_in_order_and_starts_before_the_model_finishes(self):
        played, model_done = [], []

        def sentences():
            yield "First one."
            time.sleep(0.4)  # the model is still writing
            yield "Second one."
            model_done.append(time.monotonic())

        def fake_synth(cfg, text, voice=""):
            time.sleep(0.02)
            return text.encode()

        def fake_play(mp3, volume):
            played.append((mp3.decode(), time.monotonic()))
            time.sleep(0.02)

        with mock.patch.object(pipeline.inworld, "synthesize_chunk", fake_synth), \
                mock.patch.object(pipeline.speech_io, "play_mp3", fake_play):
            pipeline.speak(CFG, sentences())
        self.assertEqual([t for t, _ in played], ["First one.", "Second one."])
        self.assertLess(played[0][1], model_done[0], "speech should start before the model finishes")

    def test_synthesis_error_is_raised_after_earlier_audio_played(self):
        played = []

        def fake_synth(cfg, text, voice=""):
            if "boom" in text:
                raise RuntimeError("tts down")
            return text.encode()

        with mock.patch.object(pipeline.inworld, "synthesize_chunk", fake_synth), \
                mock.patch.object(pipeline.speech_io, "play_mp3", lambda m, v: played.append(m)):
            with self.assertRaises(RuntimeError):
                pipeline.speak(CFG, iter(["Fine.", "boom."]))
        self.assertEqual(played, [b"Fine."])


class EngineFlow(unittest.TestCase):
    def setUp(self):
        self.engine = bt.Engine()
        self.spoken = []
        patches = [
            mock.patch.object(bt.config, "load", lambda: dict(config.DEFAULTS, proactive_cooldown_s=0)),
            mock.patch.object(pipeline.inworld, "synthesize_chunk", lambda c, t, v="": t.encode()),
            mock.patch.object(pipeline.speech_io, "play_mp3", lambda m, v: self.spoken.append(m.decode())),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def stub_llm(self, text):
        return mock.patch.object(bt.llm, "chat_stream", lambda cfg, msgs, mt=200: iter([text[:5], text[5:]]))

    def test_respond_speaks_logs_history_and_reports_speed(self):
        with self.stub_llm("Affirmative, Pilot. Proceeding."):
            reply = self.engine.respond("status?", stt_s=1.2)
        self.assertEqual(reply, "Affirmative, Pilot. Proceeding.")
        self.assertEqual(self.spoken, ["Affirmative, Pilot.", "Proceeding."])
        self.assertEqual(list(self.engine.history), [("status?", reply)])
        speed = [l["text"] for l in self.engine.log if l["text"].startswith("Speed:")]
        self.assertTrue(speed and "speech recognition 1.2s" in speed[0] and "first sound" in speed[0])

    def test_skip_stays_silent(self):
        with self.stub_llm("SKIP"):
            self.engine._comment({"type": "embark", "text": "x"})
        self.assertEqual(self.spoken, [])
        self.assertTrue(any("stayed quiet" in l["text"] for l in self.engine.log))

    def test_comment_speaks_when_not_skipped(self):
        with self.stub_llm("Pilot, I am here."):
            self.engine._comment({"type": "embark", "text": "x"})
        self.assertEqual(self.spoken, ["Pilot, I am here."])


class GameState(unittest.TestCase):
    def test_state_events_update_context_without_flooding_events(self):
        ctx = bt.GameContext()
        for _ in range(40):
            ctx.add({"type": "state", "data": {"location": "indoors", "in_titan": False, "bt_distance_m": 12}})
        ctx.add({"type": "embark", "text": "The Pilot embarked.", "data": {"in_titan": True}})
        text = ctx.describe()
        self.assertEqual(len(ctx.events), 1)
        self.assertIn("embarked in you", text)
        self.assertIn("indoors", text)

    def test_description_reads_naturally(self):
        text = "\n".join(bt.describe_state({
            "in_titan": False, "bt_distance_m": 30, "location": "outdoors", "health_pct": 40,
            "weapon": "mp_weapon_rspn101", "enemies_near": 3, "enemy_titans_near": 1, "action": "wallrunning"}))
        for expected in ("on foot", "30 meters", "outdoors", "40 percent", "R-201 Carbine", "3, including 1 Titan", "wallrunning"):
            self.assertIn(expected, text)

    def test_unknown_weapon_is_tidied(self):
        self.assertEqual(bt.weapon_name("mp_weapon_some_new_gun"), "some new gun")

    def test_sensor_errors_are_reported_once_and_not_stored_as_state(self):
        engine = bt.Engine()
        with mock.patch.object(bt.config, "load", lambda: dict(config.DEFAULTS, proactive_enabled=False)):
            for _ in range(2):
                engine.game_event({"type": "state", "data": {"map": "sp_beacon", "sensor_errors": ["enemy scan: boom"]}})
        errors = [l for l in engine.log if l["kind"] == "error"]
        self.assertEqual(len(errors), 1)
        self.assertNotIn("sensor_errors", engine.context.state)
        self.assertEqual(engine.detected_chapter, "beacon")
        self.assertIsNotNone(engine.game_connected_seconds())


if __name__ == "__main__":
    unittest.main()


class ModContract(unittest.TestCase):
    """Keeps the Squirrel mod and the app in agreement about the data fields."""

    NUT = os.path.join(os.path.dirname(__file__), "..", "..", "mod", "TF2VR.BTVoice", "mod", "scripts",
                       "vscripts", "bt_voice_sensors.nut")

    def test_every_field_the_mod_sends_is_understood_by_the_app(self):
        import re

        with open(self.NUT, encoding="utf-8") as f:
            source = f.read()
        sent = set(re.findall(r'\\"([a-z_]+)\\":', source)) - {"type", "text", "data"}
        understood = {"map", "sensor_errors", "location", "in_titan", "health_pct", "bt_distance_m",
                      "bt_health_pct", "weapon", "enemies_near", "enemy_titans_near", "action"}
        self.assertEqual(sent - understood, set(), "the mod sends a field the app doesn't describe")
        self.assertEqual(understood - sent, set(), "the app expects a field the mod no longer sends")

    def test_a_payload_in_the_mods_format_reaches_the_model_as_sentences(self):
        import json

        payload = ('{"type":"state","text":"state update","data":{"map":"sp_beacon","location":"indoors",'
                   '"in_titan":false,"health_pct":55,"bt_distance_m":8,"bt_health_pct":90,'
                   '"weapon":"mp_weapon_hemlok","enemies_near":2,"enemy_titans_near":0,'
                   '"action":"crouching","sensor_errors":[]}}')
        engine = bt.Engine()
        with mock.patch.object(bt.config, "load", lambda: dict(config.DEFAULTS, proactive_enabled=False)):
            engine.game_event(json.loads(payload))
        text = engine.context.describe()
        for expected in ("on foot", "8 meters", "indoors", "55 percent", "Hemlok", "2.", "crouching"):
            self.assertIn(expected, text)
        self.assertEqual(engine.detected_chapter, "beacon")

    def test_the_state_message_that_reveals_the_mission_is_described_as_arriving(self):
        engine = bt.Engine()
        seen = []
        with mock.patch.object(bt.config, "load", lambda: dict(config.DEFAULTS, proactive_cooldown_s=0)), \
                mock.patch.object(bt.Engine, "_comment", lambda self, event: seen.append(event)):
            engine.game_event({"type": "state", "text": "state update", "data": {"map": "sp_s2s"}})
            time.sleep(0.2)
        self.assertEqual(seen[0]["type"], "map_change")
        self.assertIn("The Ark", seen[0]["text"])
