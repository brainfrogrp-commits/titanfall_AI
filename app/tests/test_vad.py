"""Run with:  python -m unittest discover -s tests   (from the app folder)"""

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bt_voice.vad import BLOCK, Segmenter  # noqa: E402


def run(blocks):
    """blocks: list of (loudness, seconds). Feeds them in and returns utterances."""
    seg, out, now = Segmenter(threshold=0.02, silence_s=0.8), [], 0.0
    for level, seconds in blocks:
        for _ in range(int(seconds / 0.064)):
            block = np.full(BLOCK, level, dtype="float32")
            audio = seg.feed(block, now)
            now += 0.064
            if audio is not None:
                out.append(audio)
    return out


class Segmentation(unittest.TestCase):
    def test_speech_between_silence_is_one_utterance(self):
        self.assertEqual(len(run([(0.0, 1.0), (0.1, 1.5), (0.0, 2.0)])), 1)

    def test_quiet_room_makes_nothing(self):
        self.assertEqual(run([(0.005, 5.0)]), [])

    def test_short_click_is_ignored(self):
        self.assertEqual(run([(0.0, 1.0), (0.2, 0.15), (0.0, 2.0)]), [])

    def test_two_sentences_with_a_long_pause_are_two(self):
        self.assertEqual(len(run([(0.1, 1.0), (0.0, 1.5), (0.1, 1.0), (0.0, 1.5)])), 2)

    def test_short_pause_does_not_split(self):
        self.assertEqual(len(run([(0.1, 1.0), (0.0, 0.4), (0.1, 1.0), (0.0, 1.5)])), 1)


if __name__ == "__main__":
    unittest.main()
