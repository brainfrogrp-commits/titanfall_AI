"""Run with:  python -m unittest discover -s tests   (from the app folder)"""

import os
import sys
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bt_voice import bt, config, lore, pipeline, session  # noqa: E402

CFG = dict(config.DEFAULTS)


def step(convo, text, now=0.0, cfg=CFG):
    return convo.handle(text, cfg, now)


class Phrases(unittest.TestCase):
    def test_hey_bt_opens_a_conversation_and_keeps_the_question(self):
        convo = session.Conversation()
        self.assertEqual(step(convo, "Hey BT, what's our objective?"), ("start", "what's our objective?"))
        self.assertTrue(convo.active)

    def test_hey_bt_alone_just_opens(self):
        convo = session.Conversation()
        self.assertEqual(step(convo, "Hey BT."), ("start", ""))

    def test_speech_recognition_variants_still_open(self):
        for heard in ("Hey B.T.", "hey bee tee", "Hey, Beatty", "hey betty what now", "Hey BT-7274 status", "hay bt"):
            convo = session.Conversation()
            self.assertEqual(step(convo, heard)[0], "start", heard)

    def test_talking_without_hey_bt_is_ignored_while_idle(self):
        convo = session.Conversation()
        for heard in ("what is our objective", "BT what is our objective", "hey bud look at that", "hey chat"):
            self.assertEqual(step(convo, heard)[0], "ignore", heard)
        self.assertFalse(convo.active)

    def test_everything_is_answered_while_the_conversation_is_open(self):
        convo = session.Conversation()
        step(convo, "hey BT")
        self.assertEqual(step(convo, "where are we going"), ("ask", "where are we going"))
        self.assertEqual(step(convo, "and what about the batteries?"), ("ask", "and what about the batteries?"))

    def test_thanks_bt_closes_it(self):
        for heard in ("thanks BT", "Okay, that's all. Thank you, BT.", "thanks bt bye", "thanks B.T."):
            convo = session.Conversation()
            step(convo, "hey BT")
            self.assertEqual(step(convo, heard)[0], "end", heard)
            self.assertFalse(convo.active)

    def test_thanks_in_the_middle_of_a_real_question_does_not_close_it(self):
        convo = session.Conversation()
        step(convo, "hey BT")
        self.assertEqual(step(convo, "thanks BT for the help earlier, now where is the battery")[0], "ask")
        self.assertTrue(convo.active)

    def test_after_thanks_the_next_sentence_is_ignored_again(self):
        convo = session.Conversation()
        step(convo, "hey BT"), step(convo, "thanks BT")
        self.assertEqual(step(convo, "what is our objective")[0], "ignore")

    def test_goodbye_bt_quits_in_any_state(self):
        for opened in (False, True):
            convo = session.Conversation()
            if opened:
                step(convo, "hey BT")
            self.assertEqual(step(convo, "goodbye BT")[0], "quit")
            self.assertEqual(step(convo, "Okay. Good bye, B.T.")[0], "quit")

    def test_goodbye_to_someone_else_does_not_quit(self):
        convo = session.Conversation()
        self.assertEqual(step(convo, "goodbye everyone")[0], "ignore")

    def test_noise_is_not_answered_in_a_conversation(self):
        convo = session.Conversation()
        step(convo, "hey BT")
        for noise in ("you", "Thank you.", "Thanks for watching!", "..."):
            self.assertEqual(step(convo, noise)[0], "ignore", noise)

    def test_always_on_mode_answers_everything(self):
        cfg = dict(CFG, wake_word_required=False)
        convo = session.Conversation()
        self.assertEqual(step(convo, "what is that", cfg=cfg), ("ask", "what is that"))

    def test_phrases_are_editable(self):
        cfg = dict(CFG, wake_phrases="computer", end_phrases="that is all", quit_phrases="shut down")
        convo = session.Conversation()
        self.assertEqual(step(convo, "computer, status", cfg=cfg), ("start", "status"))
        self.assertEqual(step(convo, "ok that is all", cfg=cfg)[0], "end")
        self.assertEqual(step(convo, "shut down", cfg=cfg)[0], "quit")


class Timeout(unittest.TestCase):
    def test_quiet_conversation_times_out_once(self):
        convo = session.Conversation()
        convo.handle("hey BT", CFG, now=100.0)
        self.assertFalse(convo.timed_out(150.0, CFG))
        self.assertTrue(convo.timed_out(100.0 + CFG["session_timeout_s"] + 1, CFG))
        self.assertFalse(convo.timed_out(1000.0, CFG))
        self.assertFalse(convo.active)

    def test_activity_extends_it_and_zero_means_never(self):
        convo = session.Conversation()
        convo.handle("hey BT", CFG, now=0.0)
        convo.touch(100.0)
        self.assertFalse(convo.timed_out(100.0 + CFG["session_timeout_s"] - 1, CFG))
        self.assertFalse(convo.timed_out(10 ** 6, dict(CFG, session_timeout_s=0)))


class EngineActions(unittest.TestCase):
    def setUp(self):
        self.engine = bt.Engine()
        self.spoken, self.synth_calls, self.quit_calls = [], [], []
        self.engine.on_quit = lambda: self.quit_calls.append(time.monotonic())

        def synth(cfg, text, voice=""):
            self.synth_calls.append(text)
            return text.encode()

        def play(mp3, volume):
            self.spoken.append((mp3.decode(), time.monotonic()))

        for p in (mock.patch.object(bt.config, "load", lambda: dict(CFG, inworld_voice_id="v", inworld_api_key="k")),
                  mock.patch.object(bt.inworld, "synthesize_chunk", synth),
                  mock.patch.object(bt.speech_io, "play_mp3", play),
                  mock.patch.object(pipeline.inworld, "synthesize_chunk", synth),
                  mock.patch.object(pipeline.speech_io, "play_mp3", play)):
            p.start()
            self.addCleanup(p.stop)

    def settle(self):
        for _ in range(50):
            if not self.engine.is_busy():
                return
            time.sleep(0.02)

    def test_start_without_a_question_says_a_listening_phrase(self):
        self.engine.voice_action("start", "")
        time.sleep(0.2)
        self.settle()
        self.assertEqual(len(self.spoken), 1)
        self.assertIn(self.spoken[0][0], bt.PHRASES["ack"])

    def test_fixed_phrases_are_only_synthesized_once(self):
        self.engine._phrase_cache.clear()
        for _ in range(3):
            self.engine._say_fixed(dict(CFG, inworld_voice_id="v"), "Standing by, Pilot.")
        self.assertEqual(self.synth_calls.count("Standing by, Pilot."), 1)
        self.assertEqual(len(self.spoken), 3)

    def test_prepare_phrases_covers_every_line_and_skips_without_a_voice(self):
        self.engine.prepare_phrases()
        every = {t for lines in bt.PHRASES.values() for t in lines}
        self.assertEqual(set(self.synth_calls), every)
        with mock.patch.object(bt.config, "load", lambda: dict(CFG, inworld_voice_id="")):
            before = len(self.synth_calls)
            self.engine.prepare_phrases()
            self.assertEqual(len(self.synth_calls), before)

    def test_end_and_timeout_say_their_lines(self):
        for kind in ("end", "timeout"):
            self.spoken.clear()
            self.engine.voice_action(kind, "")
            time.sleep(0.2)
            self.settle()
            self.assertIn(self.spoken[0][0], bt.PHRASES[kind])

    def test_quit_says_goodbye_then_exits_after_speaking(self):
        self.engine.voice_action("quit", "")
        for _ in range(100):
            if self.quit_calls:
                break
            time.sleep(0.02)
        self.assertTrue(self.quit_calls, "on_quit was never called")
        self.assertIn(self.spoken[0][0], bt.PHRASES["quit"])
        self.assertGreaterEqual(self.quit_calls[0], self.spoken[0][1])

    def test_quit_still_exits_if_the_voice_service_is_down(self):
        with mock.patch.object(bt.inworld, "synthesize_chunk", side_effect=RuntimeError("tts down")):
            self.engine._phrase_cache.clear()
            self.engine.voice_action("quit", "")
            for _ in range(100):
                if self.quit_calls:
                    break
                time.sleep(0.02)
        self.assertTrue(self.quit_calls)


class Honesty(unittest.TestCase):
    def test_unknown_mission_tells_bt_to_admit_it(self):
        prompt = lore.build_system_prompt(None, "(no game data received yet)")
        self.assertIn("cannot tell which mission", prompt)
        self.assertIn("SENSOR LINK OFFLINE", prompt)
        self.assertIn("Never say that things look good", prompt)

    def test_live_data_does_not_trigger_the_offline_notice(self):
        prompt = lore.build_system_prompt("bt7274", "The Pilot is outdoors.")
        self.assertNotIn("SENSOR LINK OFFLINE", prompt)
        self.assertIn("charged Titan battery", prompt)

    def test_mission_info_reports_where_the_belief_came_from(self):
        engine = bt.Engine()
        with mock.patch.object(bt.config, "load", lambda: dict(CFG)):
            self.assertEqual(engine.mission_info()["name"], None)
            engine.detected_chapter = "bt7274"
            self.assertEqual(engine.mission_info()["source"], "game")
        with mock.patch.object(bt.config, "load", lambda: dict(CFG, chapter_mode="beacon")):
            info = engine.mission_info()
            self.assertEqual((info["name"], info["source"]), ("The Beacon", "manual"))


class Guard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import server

        cls.client = server.app.test_client()

    def test_own_page_and_game_requests_are_allowed(self):
        ok = self.client.get("/api/version", headers={"Host": "127.0.0.1:5757"})
        self.assertEqual(ok.status_code, 200)
        page = self.client.get("/api/version", headers={"Host": "localhost:5757", "Origin": "http://localhost:5757"})
        self.assertEqual(page.status_code, 200)

    def test_other_websites_and_rebinding_hosts_are_refused(self):
        evil_origin = self.client.post("/api/ask", headers={"Host": "127.0.0.1:5757", "Origin": "https://evil.example"},
                                       data='{"text":"x"}')
        self.assertEqual(evil_origin.status_code, 403)
        rebinding = self.client.get("/api/status", headers={"Host": "evil.example:5757"})
        self.assertEqual(rebinding.status_code, 403)


if __name__ == "__main__":
    unittest.main()
