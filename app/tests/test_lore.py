"""Run with:  python -m unittest discover -s tests   (from the app folder)

Proves BT's spoiler gate: no mission's prompt contains terms that are only
introduced by a later mission.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bt_voice import lore  # noqa: E402


class LoreGate(unittest.TestCase):
    def test_no_future_terms_in_any_prompt(self):
        for chapter in lore.CHAPTERS:
            for proactive in (False, True):
                prompt = lore.build_system_prompt(chapter["id"], "(none)", "", proactive)
                self.assertEqual(
                    lore.leaked_terms(prompt, chapter["id"]), [],
                    f"{chapter['name']} prompt leaks later-mission terms",
                )

    def test_unknown_mission_prompt_has_no_plot(self):
        prompt = lore.build_system_prompt(None, "(none)")
        for chapter in lore.CHAPTERS:
            for pattern in chapter["introduces"]:
                self.assertNotRegex(prompt, pattern, f"unknown-mission prompt contains {pattern}")

    def test_each_mission_adds_its_own_terms(self):
        # guards against a typo in `introduces` silently disabling the gate
        for chapter in lore.CHAPTERS:
            prompt = lore.build_system_prompt(chapter["id"], "(none)")
            for pattern in chapter["introduces"]:
                self.assertRegex(prompt, pattern, f"{chapter['name']} never mentions {pattern}")

    def test_knowledge_accumulates(self):
        last = lore.build_system_prompt("foldweapon", "(none)")
        for chapter in lore.CHAPTERS:
            self.assertIn(f"[Mission {chapter['number']}, {chapter['name']}]", last)

    def test_maps_resolve_and_are_unique(self):
        seen = set()
        for chapter in lore.CHAPTERS:
            for m in chapter["maps"]:
                self.assertNotIn(m, seen)
                seen.add(m)
                self.assertEqual(lore.chapter_for_map(m), chapter["id"])
        self.assertIsNone(lore.chapter_for_map("sp_tf2vr_memory"))
        self.assertIsNone(lore.chapter_for_map("mp_forwardbase_kodai"))

    def test_core_persona_has_no_late_plot(self):
        for chapter in lore.CHAPTERS:
            for pattern in chapter["introduces"]:
                self.assertNotRegex(lore.CORE_PERSONA, pattern)
                self.assertNotRegex(lore.EVENT_GUIDE, pattern)


if __name__ == "__main__":
    unittest.main()
